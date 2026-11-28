"""Staff reservation management, availability calendar, guests, payments, refunds."""
from __future__ import annotations

from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

from ..audit import audit
from ..db import get_db
from ..security import require
from ..services import availability as av
from ..services import finance
from ..services import reservations as rs
from ..services.notify import notify_guest, notify_staff
from ..services.pricing import payment_options
from ..utils import paginate, parse_date, ser, stay_dates, today, utcnow
from ..hotel_settings import get_settings
from .common import literal_search_regex

router = APIRouter(tags=["reservations"])


# ---------------- availability ----------------
@router.get("/availability/calendar")
async def calendar(start: str | None = None, days: int = Query(14, ge=1, le=62), category_id: str | None = None, q: str | None = None,
                   user: dict = Depends(require("availability.view"))):
    db = get_db()
    a = parse_date(start) if start else today()
    dates = [(a + timedelta(days=i)).isoformat() for i in range(days)]
    rq: dict = {"archived": {"$ne": True}}
    if category_id:
        rq["category_id"] = category_id
    if q:
        rq["number"] = literal_search_regex(q)
    rooms = await db.rooms.find(rq).sort([("number", 1)]).to_list(None)
    ids = [r["_id"] for r in rooms]
    now = utcnow()
    rows = [r for r in await db.room_nights.find({"room_id": {"$in": ids}, "date": {"$in": dates}}).to_list(None)
            if not (r.get("hold_expires_at") and r["hold_expires_at"] < now)]
    res_ids = list({r["owner_id"] for r in rows if r["kind"] != "block"})
    reservations = {x["_id"]: x for x in await db.reservations.find({"_id": {"$in": res_ids}}).to_list(None)}
    blocks = {m["_id"]: m for m in await db.maintenance_requests.find({"_id": {"$in": [r["owner_id"] for r in rows if r["kind"] == "block"]}}).to_list(None)}
    cats = {c["_id"]: c["name"] for c in await db.room_categories.find({}).to_list(None)}
    cells = []
    for r in rows:
        if r["kind"] == "block":
            cells.append({"room_id": r["room_id"], "date": r["date"], "kind": "maintenance", "label": blocks.get(r["owner_id"], {}).get("title", "Blocked")})
        else:
            x = reservations.get(r["owner_id"], {})
            st = "occupied" if x.get("status") == "checked_in" else ("hold" if r["kind"] == "hold" else "reserved")
            cells.append({"room_id": r["room_id"], "date": r["date"], "kind": st, "reservation_id": r["owner_id"], "reference": x.get("reference"),
                          "guest": (x.get("guest") or {}).get("name"), "status": x.get("status")})
    from .catalog import room_display_status

    ds = await room_display_status(db, rooms)
    return {"dates": dates, "rooms": [{"id": r["_id"], "number": r["number"], "category_id": r["category_id"], "category": cats.get(r["category_id"], ""),
                                       "floor": r.get("floor", ""), "operational_status": r.get("operational_status"), "display_status": ds[r["_id"]]} for r in rooms],
            "cells": cells}


@router.get("/availability/rooms")
async def free_rooms(check_in: str, check_out: str, category_id: str | None = None, user: dict = Depends(require("availability.view"))):
    db = get_db()
    dates = stay_dates(check_in, check_out)
    if not dates:
        raise HTTPException(400, "Invalid dates")
    busy = await av.busy_room_ids(db, dates)
    cats = {c["_id"]: c["name"] for c in await db.room_categories.find({}).to_list(None)}
    rooms = [r for r in await av.eligible_rooms(db, category_id) if r["_id"] not in busy]
    return [{"id": r["_id"], "number": r["number"], "category_id": r["category_id"], "category": cats.get(r["category_id"], ""),
             "housekeeping_status": r.get("housekeeping_status", "ready")} for r in rooms]


# ---------------- reservations ----------------
class StaffSelection(BaseModel):
    category_id: str
    quantity: int = Field(ge=1, le=10)
    room_ids: list[str] = []


class GuestStaffIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr | None = None
    phone: str = Field(default="", max_length=30)
    country: str = "Ghana"


class StaffBookIn(BaseModel):
    check_in: str
    check_out: str
    adults: int = Field(ge=1, le=30)
    children: int = Field(default=0, ge=0, le=30)
    selections: list[StaffSelection] = Field(min_length=1)
    guest: GuestStaffIn
    special_requests: str = ""
    internal_notes: str = ""
    promo_code: str | None = None
    status: Literal["confirmed", "pending"] = "confirmed"
    source: Literal["staff", "walk_in", "phone"] = "staff"


def _list_query(q, status, payment_status, check_in_from, check_in_to, stay_on):
    query: dict = {"booking_type": {"$ne": "event"}}
    if status:
        query["status"] = {"$in": status.split(",")}
    if payment_status:
        query["payment_status"] = payment_status
    if q:
        rx = literal_search_regex(q)
        query["$or"] = [{"reference": rx}, {"guest.name": rx}, {"guest.email": rx}, {"guest.phone": rx}]
    rng = {}
    if check_in_from:
        rng["$gte"] = check_in_from
    if check_in_to:
        rng["$lte"] = check_in_to
    if rng:
        query["check_in"] = rng
    if stay_on:
        query["check_in"] = {"$lte": stay_on}
        query["check_out"] = {"$gt": stay_on}
    return query


@router.get("/reservations")
async def list_reservations(q: str | None = None, status: str | None = None, payment_status: str | None = None, check_in_from: str | None = None,
                            check_in_to: str | None = None, stay_on: str | None = None, page: int = 1, page_size: int = 25,
                            user: dict = Depends(require("reservations.view"))):
    out = await paginate(get_db().reservations, _list_query(q, status, payment_status, check_in_from, check_in_to, stay_on),
                         [("created_at", -1)], page, page_size)
    for i in out["items"]:
        i.pop("pricing_history", None)
    return out


@router.post("/reservations", status_code=201)
async def create_manual(body: StaffBookIn, user: dict = Depends(require("reservations.create"))):
    db = get_db()
    sels = [s.model_dump() for s in body.selections]
    if any(s["room_ids"] for s in sels) and "reservations.assign" not in user["_perms"]:
        raise HTTPException(403, "You do not have permission to choose specific rooms")
    res = await rs.create_reservation(
        db, selections=sels, check_in=body.check_in, check_out=body.check_out, adults=body.adults, children=body.children,
        guest={**body.guest.model_dump(), "email": str(body.guest.email) if body.guest.email else ""}, special_requests=body.special_requests,
        promo_code=body.promo_code, source=body.source, created_by=user, hold=body.status == "pending", confirm_now=body.status == "confirmed",
        internal_notes=body.internal_notes)
    if res["status"] == "confirmed":
        await notify_guest(db, "booking_confirmation", res)
    return ser(await rs.detail(db, res["_id"]))


async def _load(rid: str) -> dict:
    r = await get_db().reservations.find_one({"_id": rid})
    if not r or r.get("booking_type") == "event":
        raise HTTPException(404, "Reservation not found")
    return r


@router.get("/reservations/{rid}")
async def get_reservation(rid: str, user: dict = Depends(require("reservations.view"))):
    d = await rs.detail(get_db(), rid)
    if not d or d["reservation"].get("booking_type") == "event":
        raise HTTPException(404, "Reservation not found")
    s = await get_settings(get_db())
    out = ser(d)
    out["payment_options"] = payment_options(d["reservation"]["total_amount"], d["reservation"]["amount_paid"], s["payment"])
    if d["reservation"]["status"] in ("pending", "confirmed", "cancellation_requested"):
        out["cancellation_preview"] = ser(rs.compute_cancellation(d["reservation"], s))
    if "payments.view" not in user["_perms"]:
        out["payments"], out["refunds"] = [], []
    return out


class ResPatch(BaseModel):
    special_requests: str | None = Field(default=None, max_length=1000)
    internal_notes: str | None = Field(default=None, max_length=2000)
    guest: GuestStaffIn | None = None


@router.patch("/reservations/{rid}")
async def patch_reservation(rid: str, body: ResPatch, user: dict = Depends(require("reservations.manage"))):
    db = get_db()
    res = await _load(rid)
    patch = {}
    if body.special_requests is not None:
        patch["special_requests"] = body.special_requests
    if body.internal_notes is not None:
        patch["internal_notes"] = body.internal_notes
    if body.guest:
        g = body.guest.model_dump()
        g["email"] = str(body.guest.email).lower() if body.guest.email else res["guest"].get("email")
        patch["guest"] = g
        await db.guests.update_one({"_id": res["guest_id"]}, {"$set": {"name": g["name"], "phone": g["phone"], "country": g["country"], "updated_at": utcnow()}})
    patch["updated_at"] = utcnow()
    await db.reservations.update_one({"_id": rid}, {"$set": patch})
    await audit(user, "reservation.update", "reservation", rid, before={k: res.get(k) for k in patch}, after=patch)
    return ser(await db.reservations.find_one({"_id": rid}))


class DatesIn(BaseModel):
    check_in: str
    check_out: str
    reason: str = ""


@router.post("/reservations/{rid}/modify-dates")
async def modify_dates(rid: str, body: DatesIn, user: dict = Depends(require("reservations.manage"))):
    return ser(await rs.modify_dates(get_db(), await _load(rid), body.check_in, body.check_out, user, body.reason))


class AssignIn(BaseModel):
    room_id: str
    reason: str = ""


@router.post("/reservations/{rid}/rooms/{rr_id}/assign")
async def assign(rid: str, rr_id: str, body: AssignIn, user: dict = Depends(require("reservations.assign"))):
    return ser(await rs.assign_room(get_db(), await _load(rid), rr_id, body.room_id, user, body.reason))


class ChargeIn(BaseModel):
    description: str = Field(min_length=2, max_length=200)
    amount_minor: int


@router.post("/reservations/{rid}/charges")
async def add_charge(rid: str, body: ChargeIn, user: dict = Depends(require("reservations.manage"))):
    return ser(await rs.add_charge(get_db(), await _load(rid), body.description, body.amount_minor, user))


class CancelIn(BaseModel):
    reason: str = Field(default="", max_length=500)
    waive_fee: bool = False
    refund_amount_minor: int | None = Field(default=None, ge=0)


@router.post("/reservations/{rid}/cancel")
async def cancel(rid: str, body: CancelIn, user: dict = Depends(require("reservations.manage"))):
    if (body.waive_fee or body.refund_amount_minor is not None) and "refunds.manage" not in user["_perms"]:
        raise HTTPException(403, "Overriding the cancellation policy requires refund permission")
    return ser(await rs.cancel_reservation(get_db(), await _load(rid), user, body.reason, body.waive_fee, body.refund_amount_minor))


@router.post("/reservations/{rid}/reject-cancellation")
async def reject_cancel(rid: str, user: dict = Depends(require("reservations.manage"))):
    return ser(await rs.reject_cancellation_request(get_db(), await _load(rid), user))


@router.post("/reservations/{rid}/review-change-request")
async def review_change_request(rid: str, user: dict = Depends(require("reservations.manage"))):
    return ser(await rs.review_change_request(get_db(), await _load(rid), user))


@router.post("/reservations/{rid}/confirm")
async def confirm(rid: str, user: dict = Depends(require("reservations.manage"))):
    db = get_db()
    res = await _load(rid)
    if res["status"] != "pending":
        raise HTTPException(409, "Only pending reservations can be confirmed")
    if not await rs.confirm_reservation(db, rid, user):
        raise HTTPException(409, "Rooms could not be secured; the hold expired and inventory was taken")
    fresh = await finance.recompute(db, rid)
    await notify_guest(db, "booking_confirmation", fresh)
    return ser(fresh)


@router.post("/reservations/{rid}/no-show")
async def no_show(rid: str, user: dict = Depends(require("reservations.manage"))):
    db = get_db()
    res = await _load(rid)
    if res["status"] != "confirmed" or res["check_in"] >= today().isoformat():
        raise HTTPException(409, "Only confirmed reservations whose check-in date has passed can be marked no-show")
    await av.release_nights(db, rid)
    await db.reservation_rooms.update_many({"reservation_id": rid}, {"$set": {"status": "cancelled"}})
    await db.reservations.update_one({"_id": rid}, {"$set": {"status": "no_show", "updated_at": utcnow()}})
    await audit(user, "reservation.no_show", "reservation", rid)
    return ser(await finance.recompute(db, rid))


@router.get("/reservations/{rid}/audit")
async def reservation_audit(rid: str, user: dict = Depends(require("reservations.view", "audit.view", any_of=True))):
    logs = await get_db().audit_logs.find({"entity_id": rid}).sort([("created_at", -1)]).to_list(200)
    return [ser(l) for l in logs]


# ---------------- guests ----------------
class GuestPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    country: str | None = None
    internal_notes: str | None = Field(default=None, max_length=2000)


@router.get("/guests")
async def list_guests(q: str | None = None, page: int = 1, page_size: int = 25, user: dict = Depends(require("guests.view"))):
    query: dict = {}
    if q:
        rx = literal_search_regex(q)
        query["$or"] = [{"name": rx}, {"email": rx}, {"phone": rx}]
    out = await paginate(get_db().guests, query, [("created_at", -1)], page, page_size)
    if "guests.notes" not in user["_perms"]:
        for g in out["items"]:
            g.pop("internal_notes", None)
    return out


@router.post("/guests", status_code=201)
async def create_guest(body: GuestStaffIn, user: dict = Depends(require("guests.manage"))):
    g = await rs.upsert_guest(get_db(), {**body.model_dump(), "email": str(body.email) if body.email else ""})
    await audit(user, "guest.register", "guest", g["_id"], after={"name": g["name"]})
    return ser(g)


@router.get("/guests/{gid}")
async def get_guest(gid: str, user: dict = Depends(require("guests.view"))):
    db = get_db()
    g = await db.guests.find_one({"_id": gid})
    if not g:
        raise HTTPException(404, "Guest not found")
    res = await db.reservations.find({"guest_id": gid}).sort([("check_in", -1)]).to_list(None)
    out = ser(g)
    if "guests.notes" not in user["_perms"]:
        out.pop("internal_notes", None)
    out["reservations"] = [{"id": r["_id"], "reference": r["reference"], "status": r["status"], "check_in": r["check_in"], "check_out": r["check_out"],
                            "total_amount": r["total_amount"], "amount_paid": r["amount_paid"], "payment_status": r["payment_status"]} for r in res]
    out["total_reservations"] = len(res)
    out["total_spent_minor"] = sum(r["amount_paid"] for r in res)
    return out


@router.patch("/guests/{gid}")
async def update_guest(gid: str, body: GuestPatch, user: dict = Depends(require("guests.manage"))):
    db = get_db()
    before = await db.guests.find_one({"_id": gid})
    if not before:
        raise HTTPException(404, "Guest not found")
    patch = {k: (str(v).lower() if k == "email" else v) for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "internal_notes" in patch and "guests.notes" not in user["_perms"]:
        raise HTTPException(403, "You cannot edit internal notes")
    patch["updated_at"] = utcnow()
    await db.guests.update_one({"_id": gid}, {"$set": patch})
    await audit(user, "guest.update", "guest", gid, before={k: before.get(k) for k in patch}, after=patch)
    return ser(await db.guests.find_one({"_id": gid}))


# ---------------- payments & refunds ----------------
@router.get("/payments")
async def list_payments(status: str | None = None, method: str | None = None, q: str | None = None, date_from: str | None = None, date_to: str | None = None,
                        page: int = 1, page_size: int = 25, user: dict = Depends(require("payments.view"))):
    query: dict = {}
    if status:
        query["status"] = status
    if method:
        query["method"] = method
    if q:
        query["$or"] = [{"reference": literal_search_regex(q)},
                        {"reservation_reference": literal_search_regex(q)}]
    if date_from or date_to:
        from datetime import datetime

        rng = {}
        if date_from:
            rng["$gte"] = datetime.fromisoformat(date_from)
        if date_to:
            rng["$lt"] = datetime.fromisoformat(date_to) + timedelta(days=1)
        query["created_at"] = rng
    return await paginate(get_db().payments, query, [("created_at", -1)], page, page_size)


class OfflineIn(BaseModel):
    reservation_id: str
    amount_minor: int = Field(gt=0)
    method: Literal["cash", "mobile_money", "card_pos", "bank_transfer", "other"] = "cash"
    note: str = Field(default="", max_length=300)
    idempotency_key: str = Field(min_length=16, max_length=128)


@router.post("/payments/offline", status_code=201)
async def record_offline(body: OfflineIn, user: dict = Depends(require("payments.record"))):
    db = get_db()
    p = await finance.record_offline(
        db, await _load(body.reservation_id), body.amount_minor, body.method, body.note, user, body.idempotency_key
    )
    res = await db.reservations.find_one({"_id": body.reservation_id})
    await notify_guest(db, "payment_confirmation", res)
    return ser(p)


@router.post("/payments/{pid}/verify")
async def reverify(pid: str, user: dict = Depends(require("payments.record", "refunds.manage", any_of=True))):
    db = get_db()
    p = await db.payments.find_one({"_id": pid})
    if not p or p["method"] != "paystack":
        raise HTTPException(404, "Online payment not found")
    return ser(await finance.verify_and_apply(db, p["reference"]))


@router.get("/refunds")
async def list_refunds(status: str | None = None, page: int = 1, page_size: int = 25, user: dict = Depends(require("refunds.view"))):
    return await paginate(get_db().refunds, {"status": status} if status else {}, [("created_at", -1)], page, page_size)


class RefundReq(BaseModel):
    reservation_id: str
    amount_minor: int = Field(gt=0)
    reason: str = Field(min_length=3, max_length=300)


@router.post("/refunds", status_code=201)
async def request_refund(body: RefundReq, user: dict = Depends(require("refunds.manage"))):
    db = get_db()
    return [ser(r) for r in await finance.request_refund(db, await _load(body.reservation_id), body.amount_minor, body.reason, user)]


class ProcessIn(BaseModel):
    note: str = Field(default="", max_length=300)


@router.post("/refunds/{fid}/approve")
async def approve_refund(fid: str, user: dict = Depends(require("refunds.manage"))):
    db = get_db()
    r = await db.refunds.find_one({"_id": fid})
    if not r or r["status"] != "requested":
        raise HTTPException(409, "Refund is not awaiting approval")
    if r.get("requested_by") == user["_id"]:
        raise HTTPException(403, "Refund requester cannot approve the refund")
    changed = await db.refunds.update_one(
        {"_id": fid, "status": "requested"},
        {"$set": {"status": "approved", "approved_by": user["_id"], "updated_at": utcnow()}},
    )
    if not changed.matched_count:
        raise HTTPException(409, "Refund is no longer awaiting approval")
    await audit(user, "refund.approve", "refund", fid, after={"amount": r["amount"]})
    return ser(await db.refunds.find_one({"_id": fid}))


@router.post("/refunds/{fid}/process")
async def process_refund(fid: str, body: ProcessIn, user: dict = Depends(require("refunds.manage"))):
    db = get_db()
    r = await db.refunds.find_one({"_id": fid})
    if not r:
        raise HTTPException(404, "Refund not found")
    if r["status"] != "approved":
        raise HTTPException(409, "Refund must be approved before processing")
    if user["_id"] in (r.get("requested_by"), r.get("approved_by")):
        raise HTTPException(403, "Refund requester and approver cannot process the refund")
    return ser(await finance.process_refund(db, r, user, body.note))


@router.post("/refunds/{fid}/reject")
async def reject_refund(fid: str, body: ProcessIn, user: dict = Depends(require("refunds.manage"))):
    db = get_db()
    r = await db.refunds.find_one({"_id": fid})
    if not r or r["status"] not in ("requested", "approved"):
        raise HTTPException(409, "Refund cannot be rejected")
    changed = await db.refunds.update_one(
        {"_id": fid, "status": {"$in": ["requested", "approved"]}},
        {"$set": {"status": "rejected", "note": body.note, "updated_at": utcnow()}},
    )
    if not changed.matched_count:
        raise HTTPException(409, "Refund can no longer be rejected")
    await finance.recompute(db, r["reservation_id"])
    await audit(user, "refund.reject", "refund", fid, note=body.note)
    return ser(await db.refunds.find_one({"_id": fid}))
