"""Check-in/out, housekeeping, maintenance."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..db import get_db
from ..security import require
from ..services import operations as ops
from ..utils import paginate, ser, today

router = APIRouter(tags=["operations"])


async def _res(rid: str) -> dict:
    r = await get_db().reservations.find_one({"_id": rid})
    if not r:
        raise HTTPException(404, "Reservation not found")
    return r


@router.get("/check-in/arrivals")
async def arrivals(date: str | None = None, user: dict = Depends(require("checkin.manage", "reservations.view", any_of=True))):
    d = date or today().isoformat()
    items = await get_db().reservations.find({"check_in": d, "status": {"$in": ["confirmed", "pending", "checked_in"]}}).sort([("created_at", 1)]).to_list(None)
    return [ser({k: v for k, v in r.items() if k != "pricing_history"}) for r in items]


@router.get("/check-out/departures")
async def departures(date: str | None = None, user: dict = Depends(require("checkin.manage", "reservations.view", any_of=True))):
    d = date or today().isoformat()
    items = await get_db().reservations.find({"check_out": d, "status": {"$in": ["checked_in", "checked_out"]}}).to_list(None)
    return [ser({k: v for k, v in r.items() if k != "pricing_history"}) for r in items]


@router.get("/check-in/in-house")
async def in_house(user: dict = Depends(require("checkin.manage", "reservations.view", any_of=True))):
    items = await get_db().reservations.find({"status": "checked_in"}).sort([("check_out", 1)]).to_list(None)
    rrs = await get_db().reservation_rooms.find({"reservation_id": {"$in": [i["_id"] for i in items]}, "status": "checked_in"}).to_list(None)
    by = {}
    for r in rrs:
        by.setdefault(r["reservation_id"], []).append(r["room_number"])
    return [{**ser({k: v for k, v in r.items() if k != "pricing_history"}), "room_numbers": by.get(r["_id"], [])} for r in items]


class CheckInIn(BaseModel):
    id_verified: bool = False
    allow_early: bool = False
    override_payment: bool = False
    override_room_status: bool = False
    note: str = Field(default="", max_length=300)


@router.post("/check-in/{rid}")
async def check_in(rid: str, body: CheckInIn, user: dict = Depends(require("checkin.manage"))):
    manager = "reservations.manage" in user["_perms"]
    if (body.allow_early or body.override_payment or body.override_room_status) and not manager:
        raise HTTPException(403, "Overrides require manager approval")
    if not body.id_verified:
        raise HTTPException(400, "Confirm the guest's identity per hotel procedure before check-in")
    return ser(await ops.check_in(get_db(), await _res(rid), user, body.allow_early, body.override_payment, body.override_room_status, body.id_verified, body.note))


class CheckOutIn(BaseModel):
    allow_outstanding: bool = False
    reason: str = Field(default="", max_length=300)


@router.post("/check-out/{rid}")
async def check_out(rid: str, body: CheckOutIn, user: dict = Depends(require("checkin.manage"))):
    if body.allow_outstanding and "reservations.manage" not in user["_perms"]:
        raise HTTPException(403, "Checking out with an outstanding balance requires manager approval")
    if body.allow_outstanding and not body.reason:
        raise HTTPException(400, "A reason is required to check out with an outstanding balance")
    return ser(await ops.check_out(get_db(), await _res(rid), user, body.allow_outstanding, body.reason))


# ---------------- housekeeping ----------------
@router.get("/housekeeping/board")
async def board(user: dict = Depends(require("housekeeping.view"))):
    db = get_db()
    rooms = await db.rooms.find({"archived": {"$ne": True}}).sort([("number", 1)]).to_list(None)
    from .catalog import room_display_status

    ds = await room_display_status(db, rooms)
    return [{"id": r["_id"], "number": r["number"], "floor": r.get("floor", ""), "housekeeping_status": r.get("housekeeping_status", "ready"),
             "occupancy_status": r.get("occupancy_status", "vacant"), "operational_status": r.get("operational_status"), "display_status": ds[r["_id"]]} for r in rooms]


class HkIn(BaseModel):
    status: Literal["dirty", "cleaning", "clean", "inspection", "ready", "maintenance"]
    notes: str = ""


@router.patch("/housekeeping/rooms/{room_id}")
async def set_hk(room_id: str, body: HkIn, user: dict = Depends(require("housekeeping.manage"))):
    db = get_db()
    room = await db.rooms.find_one({"_id": room_id})
    if not room:
        raise HTTPException(404, "Room not found")
    return ser(await ops.set_housekeeping(db, room, body.status, user, body.notes))


@router.get("/housekeeping/tasks")
async def tasks(status: str | None = None, user: dict = Depends(require("housekeeping.view"))):
    q = {"status": status} if status else {"status": {"$in": ["open", "in_progress"]}}
    return [ser(t) for t in await get_db().housekeeping_tasks.find(q).sort([("created_at", -1)]).to_list(300)]


# ---------------- maintenance ----------------
class MaintIn(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    description: str = Field(default="", max_length=2000)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    room_ids: list[str] = Field(min_length=1)
    block_rooms: bool = True
    start_date: str | None = None
    end_date: str | None = None


class MaintUpdate(BaseModel):
    status: Literal["open", "in_progress", "done", "cancelled"]
    note: str = Field(default="", max_length=500)


@router.get("/maintenance")
async def list_maint(status: str | None = None, page: int = 1, page_size: int = 25, user: dict = Depends(require("maintenance.manage"))):
    return await paginate(get_db().maintenance_requests, {"status": status} if status else {}, [("created_at", -1)], page, page_size)


@router.post("/maintenance", status_code=201)
async def create_maint(body: MaintIn, user: dict = Depends(require("maintenance.manage"))):
    return ser(await ops.create_maintenance(get_db(), body.model_dump(), user))


@router.patch("/maintenance/{mid}")
async def update_maint(mid: str, body: MaintUpdate, user: dict = Depends(require("maintenance.manage"))):
    mr = await get_db().maintenance_requests.find_one({"_id": mid})
    if not mr:
        raise HTTPException(404, "Request not found")
    return ser(await ops.finish_maintenance(get_db(), mr, user, body.status, body.note))
