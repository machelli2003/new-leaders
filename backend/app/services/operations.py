"""Front-desk operations: check-in, check-out, housekeeping, maintenance blocks."""
from __future__ import annotations

from datetime import timedelta

from fastapi import HTTPException

from ..audit import audit
from ..hotel_settings import get_settings
from ..utils import new_id, parse_date, today, utcnow
from . import availability as av
from .finance import next_counter, recompute
from .notify import notify_staff

HK_STATUSES = ("dirty", "cleaning", "clean", "inspection", "ready", "maintenance")


async def check_in(db, res: dict, user: dict, allow_early: bool = False, override_payment: bool = False,
                   override_room_status: bool = False, id_verified: bool = False, note: str = "") -> dict:
    if res["status"] != "confirmed":
        raise HTTPException(409, f"Only confirmed reservations can be checked in (current: {res['status'].replace('_', ' ')})")
    t = today().isoformat()
    if t < res["check_in"] and not allow_early:
        raise HTTPException(409, f"Check-in date is {res['check_in']}. Early check-in needs manager approval.")
    if t >= res["check_out"]:
        raise HTTPException(409, "The stay dates have already passed")
    settings = await get_settings(db)
    req = settings["booking"].get("checkin_requires", "none")
    if not override_payment:
        if req == "full" and res["balance"] > 0:
            raise HTTPException(402, f"Full payment is required before check-in. Outstanding: {res['balance'] / 100:,.2f}")
        if req == "deposit" and res["amount_paid"] < res.get("confirm_threshold", 0):
            raise HTTPException(402, "The required deposit has not been paid")
    rrs = await db.reservation_rooms.find({"reservation_id": res["_id"], "status": "reserved"}).to_list(None)
    if not rrs:
        raise HTTPException(409, "No rooms to check in")
    for rr in rrs:
        room = await db.rooms.find_one({"_id": rr["room_id"]})
        if room.get("operational_status") != "active":
            raise HTTPException(409, f"Room {room['number']} is {room['operational_status'].replace('_', ' ')}. Reassign the guest first.")
        if room.get("occupancy_status") == "occupied":
            raise HTTPException(409, f"Room {room['number']} is still occupied")
        if room.get("housekeeping_status", "ready") in ("dirty", "cleaning", "inspection") and not override_room_status:
            raise HTTPException(409, f"Room {room['number']} is not ready ({room['housekeeping_status']}). Complete housekeeping or override.")
    now = utcnow()
    for rr in rrs:
        await db.reservation_rooms.update_one({"_id": rr["_id"]}, {"$set": {"status": "checked_in", "checked_in_at": now}})
        await db.rooms.update_one({"_id": rr["room_id"]}, {"$set": {"occupancy_status": "occupied"}})
    await db.reservations.update_one({"_id": res["_id"]}, {"$set": {"status": "checked_in", "checked_in_at": now, "updated_at": now,
                                                                     "id_verified": id_verified, "checkin_note": note}})
    await audit(user, "reservation.check_in", "reservation", res["_id"], note=note,
                after={"id_verified": id_verified, "override_payment": override_payment})
    return await recompute(db, res["_id"])


async def check_out(db, res: dict, user: dict, allow_outstanding: bool = False, reason: str = "") -> dict:
    if res["status"] != "checked_in":
        raise HTTPException(409, "Only checked-in reservations can be checked out")
    res = await recompute(db, res["_id"])
    if res["balance"] > 0 and not allow_outstanding:
        raise HTTPException(402, f"Outstanding balance of {res['balance'] / 100:,.2f} must be settled before check-out")
    now = utcnow()
    rrs = await db.reservation_rooms.find({"reservation_id": res["_id"], "status": "checked_in"}).to_list(None)
    for rr in rrs:
        await db.reservation_rooms.update_one({"_id": rr["_id"]}, {"$set": {"status": "checked_out", "checked_out_at": now}})
        await db.rooms.update_one({"_id": rr["room_id"]}, {"$set": {"occupancy_status": "vacant", "housekeeping_status": "dirty"}})
        await db.housekeeping_tasks.insert_one({"_id": new_id(), "room_id": rr["room_id"], "room_number": rr["room_number"], "type": "checkout_clean",
                                                "status": "open", "reservation_id": res["_id"], "created_at": now, "notes": ""})
    await av.release_nights(db, res["_id"], from_date=today().isoformat())  # early departure frees remaining nights
    seq = await next_counter(db, f"folio-{today().year}")
    final = {"number": f"FIN-{today().year}-{seq:06d}", "issued_at": now, "issued_by": user["name"], "total": res["total_amount"],
             "paid": res["amount_paid"], "balance": res["balance"], "outstanding_waived_reason": reason if res["balance"] > 0 else None}
    await db.reservations.update_one({"_id": res["_id"]}, {"$set": {"status": "checked_out", "checked_out_at": now, "updated_at": now, "final_receipt": final}})
    await audit(user, "reservation.check_out", "reservation", res["_id"], after=final, note=reason)
    return await recompute(db, res["_id"])


async def set_housekeeping(db, room: dict, status: str, user: dict, notes: str = "") -> dict:
    if status not in HK_STATUSES:
        raise HTTPException(400, "Invalid housekeeping status")
    upd: dict = {"housekeeping_status": status, "updated_at": utcnow()}
    if status == "maintenance":
        upd["operational_status"] = "maintenance"
    elif room.get("operational_status") == "maintenance":
        upd["operational_status"] = "active"
    await db.rooms.update_one({"_id": room["_id"]}, {"$set": upd})
    if status in ("clean", "ready"):
        await db.housekeeping_tasks.update_many({"room_id": room["_id"], "status": {"$in": ["open", "in_progress"]}},
                                                {"$set": {"status": "done", "completed_at": utcnow(), "completed_by": user["name"]}})
    elif status in ("dirty", "cleaning", "inspection"):
        open_t = await db.housekeeping_tasks.find_one({"room_id": room["_id"], "status": {"$in": ["open", "in_progress"]}})
        if not open_t:
            await db.housekeeping_tasks.insert_one({"_id": new_id(), "room_id": room["_id"], "room_number": room["number"], "type": "cleaning",
                                                    "status": "in_progress" if status == "cleaning" else "open", "created_at": utcnow(), "notes": notes})
    await audit(user, "housekeeping.update", "room", room["_id"], before={"status": room.get("housekeeping_status")}, after={"status": status})
    return await db.rooms.find_one({"_id": room["_id"]})


def _inclusive(start: str, end: str) -> list[str]:
    a, b = parse_date(start), parse_date(end)
    if b < a:
        raise HTTPException(400, "End date must be on or after start date")
    return [(a + timedelta(days=i)).isoformat() for i in range((b - a).days + 1)]


async def create_maintenance(db, data: dict, user: dict) -> dict:
    rooms = []
    for rid in data["room_ids"]:
        r = await db.rooms.find_one({"_id": rid})
        if not r:
            raise HTTPException(404, "Room not found")
        rooms.append(r)
    mid = new_id()
    mr = {"_id": mid, "title": data["title"], "description": data.get("description", ""), "priority": data.get("priority", "normal"),
          "status": "open", "room_ids": data["room_ids"], "room_numbers": [r["number"] for r in rooms], "block_rooms": bool(data.get("block_rooms", True)),
          "start_date": data.get("start_date"), "end_date": data.get("end_date"), "notes": [], "created_by": user["name"],
          "created_at": utcnow(), "updated_at": utcnow()}
    if mr["block_rooms"]:
        if not mr["start_date"] or not mr["end_date"]:
            raise HTTPException(400, "Start and end dates are required to block rooms")
        dates = _inclusive(mr["start_date"], mr["end_date"])
        done = []
        for r in rooms:
            if not await av.claim_room(db, r["_id"], dates, mid, "block"):
                for rid in done:
                    await av.release_nights(db, mid, room_id=rid)
                raise HTTPException(409, f"Room {r['number']} has reservations or another block in that period. Move the guests first.")
            done.append(r["_id"])
            await db.room_blocks.insert_one({"_id": new_id(), "maintenance_id": mid, "room_id": r["_id"], "start_date": mr["start_date"],
                                             "end_date": mr["end_date"], "reason": mr["title"], "created_at": utcnow()})
    await db.maintenance_requests.insert_one(mr)
    await audit(user, "maintenance.create", "maintenance", mid, after={"title": mr["title"], "rooms": mr["room_numbers"]})
    await notify_staff(db, "maintenance", f"Maintenance: {mr['title']}", f"Rooms {', '.join(mr['room_numbers'])}", "/admin/maintenance", "maintenance.manage")
    return mr


async def finish_maintenance(db, mr: dict, user: dict, status: str, note: str = "") -> dict:
    if status not in ("open", "in_progress", "done", "cancelled"):
        raise HTTPException(400, "Invalid status")
    upd: dict = {"status": status, "updated_at": utcnow()}
    push = {"notes": {"at": utcnow(), "by": user["name"], "text": note}} if note else None
    if status in ("done", "cancelled") and mr["status"] not in ("done", "cancelled"):
        await av.release_nights(db, mr["_id"])
        await db.room_blocks.delete_many({"maintenance_id": mr["_id"]})
        if status == "done":
            await db.rooms.update_many({"_id": {"$in": mr["room_ids"]}, "operational_status": "maintenance"}, {"$set": {"operational_status": "active", "housekeeping_status": "inspection"}})
            upd["completed_at"] = utcnow()
    op = {"$set": upd}
    if push:
        op["$push"] = push
    await db.maintenance_requests.update_one({"_id": mr["_id"]}, op)
    await audit(user, "maintenance.update", "maintenance", mr["_id"], before={"status": mr["status"]}, after={"status": status})
    return await db.maintenance_requests.find_one({"_id": mr["_id"]})
