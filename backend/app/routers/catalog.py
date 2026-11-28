"""Room categories, physical rooms and amenities."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..audit import audit
from ..db import get_db
from ..security import require
from ..services import availability as av
from ..utils import new_id, paginate, ser, slugify, today, utcnow
from .common import literal_search_regex, partial

router = APIRouter(tags=["rooms"])
Status = Literal["draft", "published", "archived"]


# ---------------- amenities ----------------
class AmenityIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    icon: str = ""


@router.get("/amenities")
async def list_amenities(user: dict = Depends(require("rooms.view"))):
    return [ser(a) for a in await get_db().amenities.find({}).sort([("name", 1)]).to_list(None)]


@router.post("/amenities", status_code=201)
async def create_amenity(body: AmenityIn, user: dict = Depends(require("rooms.manage"))):
    db = get_db()
    if await db.amenities.find_one({"name_lower": body.name.lower()}):
        raise HTTPException(409, "Amenity already exists")
    d = {"_id": new_id(), **body.model_dump(), "name_lower": body.name.lower(), "created_at": utcnow()}
    await db.amenities.insert_one(d)
    await audit(user, "amenity.create", "amenity", d["_id"], after=body.model_dump())
    return ser(d)


@router.delete("/amenities/{aid}")
async def delete_amenity(aid: str, user: dict = Depends(require("rooms.manage"))):
    db = get_db()
    await db.amenities.delete_one({"_id": aid})
    await db.room_categories.update_many({}, {"$pull": {"amenity_ids": aid}})
    await audit(user, "amenity.delete", "amenity", aid)
    return {"ok": True}


# ---------------- room categories ----------------
class CategoryIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    slug: str | None = None
    short_description: str = ""
    full_description: str = ""
    default_rate_minor: int = Field(default=0, ge=0)
    max_occupancy: int = Field(default=2, ge=1, le=20)
    adult_capacity: int | None = Field(default=None, ge=1, le=20)
    children_capacity: int | None = Field(default=None, ge=0, le=20)
    included_guests: int | None = Field(default=None, ge=1, le=20)
    extra_guest_fee_minor: int = Field(default=0, ge=0)
    bed_configuration: str = ""
    room_size_sqm: float | None = Field(default=None, gt=0, le=1000)
    amenity_ids: list[str] = []
    featured: bool = False
    status: Status = "draft"
    main_media_id: str | None = None
    gallery_media_ids: list[str] = []
    sort_order: int = 0
    is_sample: bool = False


CategoryPatch = partial(CategoryIn)


async def _unique_slug(db, base: str, exclude: str | None = None) -> str:
    slug, i = slugify(base), 1
    while True:
        existing = await db.room_categories.find_one({"slug": slug})
        if not existing or existing["_id"] == exclude:
            return slug
        i += 1
        slug = f"{slugify(base)}-{i}"


@router.get("/room-categories")
async def list_categories(include_archived: bool = False, user: dict = Depends(require("rooms.view"))):
    db = get_db()
    q = {} if include_archived else {"status": {"$ne": "archived"}}
    cats = await db.room_categories.find(q).sort([("sort_order", 1), ("name", 1)]).to_list(None)
    counts: dict[str, int] = {}
    for r in await db.rooms.find({"archived": {"$ne": True}}, {"category_id": 1}).to_list(None):
        counts[r["category_id"]] = counts.get(r["category_id"], 0) + 1
    return [{**ser(c), "room_count": counts.get(c["_id"], 0)} for c in cats]


@router.get("/room-categories/{cid}")
async def get_category(cid: str, user: dict = Depends(require("rooms.view"))):
    c = await get_db().room_categories.find_one({"_id": cid})
    if not c:
        raise HTTPException(404, "Category not found")
    return ser(c)


@router.post("/room-categories", status_code=201)
async def create_category(body: CategoryIn, user: dict = Depends(require("rooms.manage"))):
    db = get_db()
    d = body.model_dump()
    d["slug"] = await _unique_slug(db, body.slug or body.name)
    d.update({"_id": new_id(), "created_at": utcnow(), "updated_at": utcnow()})
    await db.room_categories.insert_one(d)
    await audit(user, "category.create", "room_category", d["_id"], after=d)
    return ser(d)


@router.patch("/room-categories/{cid}")
async def update_category(cid: str, body: CategoryPatch, user: dict = Depends(require("rooms.manage"))):
    db = get_db()
    before = await db.room_categories.find_one({"_id": cid})
    if not before:
        raise HTTPException(404, "Category not found")
    patch = body.model_dump(exclude_unset=True)
    for k in ("name", "default_rate_minor", "max_occupancy", "status"):
        if k in patch and patch[k] is None:
            patch.pop(k)
    if "slug" in patch or "name" in patch and not before.get("slug"):
        patch["slug"] = await _unique_slug(db, patch.get("slug") or patch.get("name") or before["name"], cid)
    patch["updated_at"] = utcnow()
    await db.room_categories.update_one({"_id": cid}, {"$set": patch})
    after = await db.room_categories.find_one({"_id": cid})
    action = "price.change" if "default_rate_minor" in patch and patch["default_rate_minor"] != before.get("default_rate_minor") else "category.update"
    await audit(user, action, "room_category", cid, before=before, after=after)
    return ser(after)


@router.delete("/room-categories/{cid}")
async def archive_category(cid: str, user: dict = Depends(require("rooms.manage"))):
    db = get_db()
    c = await db.room_categories.find_one({"_id": cid})
    if not c:
        raise HTTPException(404, "Category not found")
    await db.room_categories.update_one({"_id": cid}, {"$set": {"status": "archived", "updated_at": utcnow()}})
    await audit(user, "category.archive", "room_category", cid, before={"status": c.get("status")})
    return {"ok": True}


# ---------------- physical rooms ----------------
RoomOp = Literal["active", "maintenance", "out_of_service"]


class RoomIn(BaseModel):
    number: str = Field(min_length=1, max_length=20)
    category_id: str
    floor: str = ""
    description: str = ""
    bed_configuration: str = ""
    max_occupancy_override: int | None = Field(default=None, ge=1, le=20)
    price_override_minor: int | None = Field(default=None, ge=0)
    operational_status: RoomOp = "active"
    photo_media_ids: list[str] = []
    internal_notes: str = ""
    is_sample: bool = False


RoomPatch = partial(RoomIn)


class BulkRooms(BaseModel):
    category_id: str
    floor: str = ""
    prefix: str = ""
    start: int = Field(ge=0, le=99999)
    end: int = Field(ge=0, le=99999)
    operational_status: RoomOp = "active"
    is_sample: bool = False


async def room_display_status(db, rooms: list[dict]) -> dict[str, str]:
    t = today().isoformat()
    rows = await db.room_nights.find({"date": t}).to_list(None)
    now = utcnow()
    held = {}
    for r in rows:
        if r.get("hold_expires_at") is not None and r["hold_expires_at"] < now:
            continue
        held[r["room_id"]] = r["kind"]
    out = {}
    for r in rooms:
        if r.get("archived"):
            out[r["_id"]] = "archived"
        elif r.get("operational_status", "active") != "active":
            out[r["_id"]] = r["operational_status"]
        elif held.get(r["_id"]) == "block":
            out[r["_id"]] = "maintenance"
        elif r.get("occupancy_status") == "occupied":
            out[r["_id"]] = "occupied"
        elif r.get("housekeeping_status", "ready") in ("dirty", "cleaning", "inspection"):
            out[r["_id"]] = r["housekeeping_status"]
        elif held.get(r["_id"]) in ("reservation", "hold"):
            out[r["_id"]] = "reserved"
        else:
            out[r["_id"]] = "available"
    return out


def _new_room(d: dict) -> dict:
    d.update({"_id": new_id(), "archived": False, "occupancy_status": "vacant", "housekeeping_status": "ready",
              "created_at": utcnow(), "updated_at": utcnow()})
    return d


@router.get("/rooms")
async def list_rooms(category_id: str | None = None, q: str | None = None, include_archived: bool = False,
                     user: dict = Depends(require("rooms.view"))):
    db = get_db()
    query: dict = {} if include_archived else {"archived": {"$ne": True}}
    if category_id:
        query["category_id"] = category_id
    if q:
        query["number"] = literal_search_regex(q)
    rooms = await db.rooms.find(query).sort([("number", 1)]).to_list(None)
    status = await room_display_status(db, rooms)
    cats = {c["_id"]: c["name"] for c in await db.room_categories.find({}).to_list(None)}
    return [{**ser(r), "display_status": status[r["_id"]], "category_name": cats.get(r["category_id"], "")} for r in rooms]


@router.post("/rooms", status_code=201)
async def create_room(body: RoomIn, user: dict = Depends(require("rooms.manage"))):
    db = get_db()
    if not await db.room_categories.find_one({"_id": body.category_id}):
        raise HTTPException(404, "Category not found")
    if await db.rooms.find_one({"number": body.number}):
        raise HTTPException(409, f"Room {body.number} already exists")
    d = _new_room(body.model_dump())
    await db.rooms.insert_one(d)
    await audit(user, "room.create", "room", d["_id"], after=d)
    return ser(d)


@router.post("/rooms/bulk", status_code=201)
async def bulk_create(body: BulkRooms, user: dict = Depends(require("rooms.manage"))):
    db = get_db()
    if body.end < body.start or body.end - body.start > 200:
        raise HTTPException(422, "Invalid range (max 200 rooms at once)")
    if not await db.room_categories.find_one({"_id": body.category_id}):
        raise HTTPException(404, "Category not found")
    numbers = [f"{body.prefix}{n}" for n in range(body.start, body.end + 1)]
    existing = [r["number"] for r in await db.rooms.find({"number": {"$in": numbers}}).to_list(None)]
    if existing:
        raise HTTPException(409, f"These room numbers already exist: {', '.join(existing[:10])}")
    docs = [_new_room({"number": n, "category_id": body.category_id, "floor": body.floor, "description": "", "bed_configuration": "",
                       "max_occupancy_override": None, "price_override_minor": None, "operational_status": body.operational_status,
                       "photo_media_ids": [], "internal_notes": "", "is_sample": body.is_sample}) for n in numbers]
    await db.rooms.insert_many(docs)
    await audit(user, "room.bulk_create", "room", None, after={"numbers": numbers, "category_id": body.category_id})
    return {"created": len(docs), "numbers": numbers}


@router.get("/rooms/{rid}")
async def get_room(rid: str, user: dict = Depends(require("rooms.view"))):
    db = get_db()
    r = await db.rooms.find_one({"_id": rid})
    if not r:
        raise HTTPException(404, "Room not found")
    st = await room_display_status(db, [r])
    return {**ser(r), "display_status": st[rid]}


@router.patch("/rooms/{rid}")
async def update_room(rid: str, body: RoomPatch, user: dict = Depends(require("rooms.manage"))):
    db = get_db()
    before = await db.rooms.find_one({"_id": rid})
    if not before:
        raise HTTPException(404, "Room not found")
    patch = body.model_dump(exclude_unset=True)
    if "number" in patch and patch["number"] != before["number"] and await db.rooms.find_one({"number": patch["number"]}):
        raise HTTPException(409, f"Room {patch['number']} already exists")
    if patch.get("category_id") and patch["category_id"] != before["category_id"]:
        if await db.reservation_rooms.find_one({"room_id": rid, "status": {"$in": ["reserved", "checked_in"]}}):
            raise HTTPException(409, "Room has active reservations; reassign them before changing category")
    if patch.get("operational_status") in ("maintenance", "out_of_service") and before.get("occupancy_status") == "occupied":
        raise HTTPException(409, "Room is occupied. Check the guest out or move them first.")
    patch["updated_at"] = utcnow()
    await db.rooms.update_one({"_id": rid}, {"$set": patch})
    after = await db.rooms.find_one({"_id": rid})
    await audit(user, "room.update", "room", rid, before=before, after=after)
    return ser(after)


@router.delete("/rooms/{rid}")
async def archive_room(rid: str, user: dict = Depends(require("rooms.manage"))):
    db = get_db()
    r = await db.rooms.find_one({"_id": rid})
    if not r:
        raise HTTPException(404, "Room not found")
    if await db.reservation_rooms.find_one({"room_id": rid, "status": {"$in": ["reserved", "checked_in"]}}):
        raise HTTPException(409, "Room has active or upcoming reservations. Reassign them first.")
    await db.rooms.update_one({"_id": rid}, {"$set": {"archived": True, "updated_at": utcnow()}})
    await audit(user, "room.archive", "room", rid, before={"number": r["number"]})
    return {"ok": True}


@router.post("/rooms/{rid}/restore")
async def restore_room(rid: str, user: dict = Depends(require("rooms.manage"))):
    await get_db().rooms.update_one({"_id": rid}, {"$set": {"archived": False}})
    await audit(user, "room.restore", "room", rid)
    return {"ok": True}


@router.get("/rooms/{rid}/history")
async def room_history(rid: str, user: dict = Depends(require("rooms.view", "reservations.view"))):
    db = get_db()
    rrs = await db.reservation_rooms.find({"room_id": rid}).to_list(None)
    out = []
    for rr in rrs:
        res = await db.reservations.find_one({"_id": rr["reservation_id"]})
        if res:
            out.append({"reservation_id": res["_id"], "reference": res["reference"], "guest": res["guest"].get("name"), "check_in": res["check_in"],
                        "check_out": res["check_out"], "status": rr["status"]})
    out.sort(key=lambda x: x["check_in"], reverse=True)
    return out
