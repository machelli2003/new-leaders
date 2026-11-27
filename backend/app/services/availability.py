"""Availability engine backed by the MongoDB `room_nights` document collection.

Each occupied night of a physical room is one document with _id "<room_id>|<YYYY-MM-DD>".
The unique _id key guarantees that two reservations/holds/blocks cannot own the
same room-night, even under concurrent requests. Check-out date is never inserted, so same-day
turnover works naturally.
"""
from __future__ import annotations

import random

from fastapi import HTTPException
from pymongo.errors import BulkWriteError, DuplicateKeyError

from ..utils import stay_dates, today, utcnow


def nid(room_id: str, d: str) -> str:
    return f"{room_id}|{d}"


async def purge_expired_holds(db, room_id: str | None = None, dates: list[str] | None = None) -> None:
    q: dict = {"hold_expires_at": {"$ne": None, "$lt": utcnow()}}
    if room_id:
        q["room_id"] = room_id
    if dates:
        q["date"] = {"$in": dates}
    await db.room_nights.delete_many(q)


async def busy_room_ids(db, dates: list[str]) -> set[str]:
    now = utcnow()
    rows = await db.room_nights.find({"date": {"$in": dates}}).to_list(None)
    busy = set()
    for r in rows:
        exp = r.get("hold_expires_at")
        if exp is not None and exp < now:
            continue  # expired hold, treated as free
        busy.add(r["room_id"])
    return busy


async def eligible_rooms(db, category_id: str | None = None) -> list[dict]:
    q: dict = {"archived": {"$ne": True}, "operational_status": "active"}
    if category_id:
        q["category_id"] = category_id
    rooms = await db.rooms.find(q).to_list(None)
    rooms.sort(key=lambda r: (r.get("floor") or "", r["number"]))
    return rooms


async def claim_room(db, room_id: str, dates: list[str], owner_id: str, kind: str,
                     hold_expires_at=None, reservation_room_id: str | None = None) -> bool:
    """Atomically claim every night for a room or claim nothing. Returns False on conflict."""
    await purge_expired_holds(db, room_id, dates)
    now = utcnow()
    rows = [
        {
            "_id": nid(room_id, d), "room_id": room_id, "date": d, "owner_id": owner_id,
            "reservation_room_id": reservation_room_id, "kind": kind,
            "hold_expires_at": hold_expires_at, "created_at": now,
        }
        for d in dates
    ]
    try:
        await db.room_nights.insert_many(rows, ordered=False)
        return True
    except (DuplicateKeyError, BulkWriteError):
        await db.room_nights.delete_many({"_id": {"$in": [r["_id"] for r in rows]}, "owner_id": owner_id})
        return False


async def release_nights(db, owner_id: str, room_id: str | None = None, dates: list[str] | None = None,
                         from_date: str | None = None) -> None:
    q: dict = {"owner_id": owner_id}
    if room_id:
        q["room_id"] = room_id
    if dates:
        q["date"] = {"$in": dates}
    if from_date:
        q["date"] = {"$gte": from_date}
    await db.room_nights.delete_many(q)


async def confirm_hold(db, owner_id: str) -> None:
    await db.room_nights.update_many({"owner_id": owner_id}, {"$set": {"hold_expires_at": None, "kind": "reservation"}})


async def allocate(db, selections: list[dict], dates: list[str], owner_id: str, kind: str,
                   hold_expires_at=None, public_only: bool = False) -> list[dict]:
    """selections: [{category_id, quantity, room_ids?}]. Returns [{category, room}] or raises 409.
    Auto mode picks eligible free rooms; manual mode uses the staff-selected rooms. All-or-nothing."""
    claimed: list[tuple[dict, dict]] = []

    async def rollback():
        await db.room_nights.delete_many({"owner_id": owner_id})

    busy = await busy_room_ids(db, dates)
    for sel in selections:
        cat = await db.room_categories.find_one({"_id": sel["category_id"]})
        if not cat or cat.get("status") == "archived" or (public_only and cat.get("status") != "published"):
            await rollback()
            raise HTTPException(404, "Room category not found")
        qty = int(sel["quantity"])
        manual = sel.get("room_ids") or []
        if manual:
            if len(manual) != qty:
                await rollback()
                raise HTTPException(400, "Number of selected rooms must match the quantity")
            for rid in manual:
                room = await db.rooms.find_one({"_id": rid})
                if (not room or room.get("archived") or room["category_id"] != cat["_id"]
                        or room.get("operational_status") != "active"):
                    await rollback()
                    raise HTTPException(409, "A selected room is not available for assignment")
                if not await claim_room(db, rid, dates, owner_id, kind, hold_expires_at):
                    await rollback()
                    raise HTTPException(409, f"Room {room['number']} is not available for those dates")
                claimed.append((cat, room))
                busy.add(rid)
            continue
        got = 0
        candidates = [r for r in await eligible_rooms(db, cat["_id"]) if r["_id"] not in busy]
        for room in candidates:
            if got >= qty:
                break
            if await claim_room(db, room["_id"], dates, owner_id, kind, hold_expires_at):
                claimed.append((cat, room))
                busy.add(room["_id"])
                got += 1
        if got < qty:
            await rollback()
            raise HTTPException(409, f"Not enough '{cat['name']}' rooms available for the selected dates")
    return [{"category": c, "room": r} for c, r in claimed]


def fits(cat: dict, rooms: int, adults: int, children: int) -> bool:
    mo = int(cat.get("max_occupancy") or 0)
    if mo and adults + children > rooms * mo:
        return False
    ac, cc = cat.get("adult_capacity"), cat.get("children_capacity")
    if ac and adults > rooms * int(ac):
        return False
    if cc is not None and cc != "" and children > rooms * int(cc) and int(cc) > 0:
        return False
    return True


async def category_availability(db, check_in: str, check_out: str, public_only: bool = True) -> list[dict]:
    dates = stay_dates(check_in, check_out)
    busy = await busy_room_ids(db, dates)
    q = {"status": "published"} if public_only else {"status": {"$ne": "archived"}}
    cats = await db.room_categories.find(q).to_list(None)
    cats.sort(key=lambda c: (c.get("sort_order", 0), c["name"]))
    out = []
    for c in cats:
        free = [r for r in await eligible_rooms(db, c["_id"]) if r["_id"] not in busy]
        out.append({"category": c, "available": len(free), "room_ids": [r["_id"] for r in free]})
    return out


def validate_stay(settings: dict, check_in: str, check_out: str, staff: bool = False) -> None:
    from ..utils import parse_date

    try:
        a, b = parse_date(check_in), parse_date(check_out)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if b <= a:
        raise HTTPException(400, "Check-out must be after check-in")
    t = today()
    if a < t and not staff:
        raise HTTPException(400, "Check-in date cannot be in the past")
    bk = settings["booking"]
    n = (b - a).days
    if n < int(bk["min_nights"]) or n > int(bk["max_nights"]):
        raise HTTPException(400, f"Stay must be between {bk['min_nights']} and {bk['max_nights']} nights")
    if not staff and (a - t).days > int(bk["max_advance_days"]):
        raise HTTPException(400, "Check-in date is too far in advance")
