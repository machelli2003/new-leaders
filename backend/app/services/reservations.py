"""Reservation lifecycle: create (hold), confirm, modify, reassign, cancel, expire."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException

from ..audit import audit
from ..hotel_settings import get_settings
from ..utils import new_id, round_div, stay_dates, utcnow
from . import availability as av
from .finance import next_counter, recompute, request_refund
from .notify import notify_guest, notify_staff
from .pricing import build_quote, confirm_threshold, find_promo


async def generate_reference(db) -> str:
    from ..utils import today

    year = today().year
    seq = await next_counter(db, f"ref-{year}")
    return f"NLH-{year}-{seq:06d}"


async def upsert_guest(db, info: dict) -> dict:
    email = (info.get("email") or "").strip().lower() or None
    phone = (info.get("phone") or "").strip()
    q = {"email": email} if email else ({"phone": phone} if phone else None)
    g = await db.guests.find_one(q) if q else None
    now = utcnow()
    if g:
        fill = {k: info[k] for k in ("name", "phone", "country") if info.get(k) and not g.get(k)}
        if fill:
            fill["updated_at"] = now
            await db.guests.update_one({"_id": g["_id"]}, {"$set": fill})
            g.update(fill)
        return g
    g = {"_id": new_id(), "name": info["name"].strip(), "email": email, "phone": phone, "country": info.get("country", ""),
         "internal_notes": "", "created_at": now, "updated_at": now}
    await db.guests.insert_one(g)
    return g


async def create_reservation(db, *, selections: list[dict], check_in: str, check_out: str, adults: int, children: int,
                             guest: dict, special_requests: str = "", promo_code: str | None = None,
                             source: str = "online", created_by: dict | None = None, hold: bool = True,
                             confirm_now: bool = False, internal_notes: str = "") -> dict:
    settings = await get_settings(db)
    staff = source != "online"
    av.validate_stay(settings, check_in, check_out, staff=staff)
    n_rooms = sum(int(s["quantity"]) for s in selections)
    if n_rooms < 1 or n_rooms > int(settings["booking"]["max_rooms_per_booking"]):
        raise HTTPException(400, f"You can book between 1 and {settings['booking']['max_rooms_per_booking']} rooms at once")
    if adults < 1 or adults + children < n_rooms:
        raise HTTPException(400, "At least one adult is required, and every room needs at least one guest")
    cap = 0
    for s in selections:
        cat = await db.room_categories.find_one({"_id": s["category_id"]})
        if not cat:
            raise HTTPException(404, "Room category not found")
        cap += int(cat.get("max_occupancy") or 99) * int(s["quantity"])
    if adults + children > cap:
        raise HTTPException(400, "The selected rooms cannot accommodate that many guests")

    dates = stay_dates(check_in, check_out)
    res_id, now = new_id(), utcnow()
    hold_exp = now + timedelta(minutes=int(settings["booking"]["hold_minutes"])) if hold else None
    alloc = await av.allocate(db, selections, dates, res_id, "hold" if hold else "reservation", hold_exp, public_only=not staff)
    try:
        quote = await build_quote(db, settings, rooms=alloc, check_in=check_in, check_out=check_out,
                                  adults=adults, children=children, promo_code=promo_code)
        g = await upsert_guest(db, guest)
        reference = await generate_reference(db)
        status = "confirmed" if (confirm_now or not hold) else "pending"
        total = quote["total_minor"]
        pricing = {k: v for k, v in quote.items() if k != "rooms"}
        res = {
            "_id": res_id, "reference": reference, "status": status, "payment_status": "unpaid", "source": source,
            "guest_id": g["_id"], "guest": {"name": g["name"], "email": g.get("email"), "phone": g.get("phone"), "country": g.get("country")},
            "check_in": check_in, "check_out": check_out, "nights": quote["nights"], "adults": adults, "children": children,
            "rooms_count": n_rooms, "special_requests": special_requests, "internal_notes": internal_notes,
            "pricing": pricing, "pricing_history": [], "charges": [], "total_amount": total, "amount_paid": 0, "balance": total,
            "confirm_threshold": confirm_threshold(total, settings["payment"]),
            "hold_expires_at": hold_exp if status == "pending" else None,
            "checked_in_at": None, "checked_out_at": None, "cancellation": None, "needs_attention": False,
            "created_by": created_by["_id"] if created_by else None, "created_at": now, "updated_at": now,
        }
        if status == "confirmed":
            await db.room_nights.update_many({"owner_id": res_id}, {"$set": {"hold_expires_at": None, "kind": "reservation"}})
        await db.reservations.insert_one(res)
        rrs = []
        for a, rq in zip(alloc, quote["rooms"]):
            rrs.append({"_id": new_id(), "reservation_id": res_id, "category_id": a["category"]["_id"],
                        "category_name": a["category"]["name"], "room_id": a["room"]["_id"], "room_number": a["room"]["number"],
                        "adults": rq["adults"], "children": rq["children"], "pricing": rq, "status": "reserved",
                        "checked_in_at": None, "checked_out_at": None,
                        "assignment_history": [{"room_id": a["room"]["_id"], "room_number": a["room"]["number"], "at": now,
                                                "by": created_by["name"] if created_by else "booking engine", "reason": "initial allocation"}]})
        await db.reservation_rooms.insert_many(rrs)
        for rr in rrs:
            await db.room_nights.update_many({"owner_id": res_id, "room_id": rr["room_id"]}, {"$set": {"reservation_room_id": rr["_id"]}})
    except Exception:
        await av.release_nights(db, res_id)
        await db.reservations.delete_one({"_id": res_id})
        await db.reservation_rooms.delete_many({"reservation_id": res_id})
        raise
    await audit(created_by, "reservation.create", "reservation", res_id, after={"reference": reference, "source": source, "total": total})
    return res


async def reclaim_rooms(db, res: dict) -> bool:
    """After an expired hold: re-secure the same rooms (or another free room of the category)."""
    dates = stay_dates(res["check_in"], res["check_out"])
    await av.release_nights(db, res["_id"])
    rrs = await db.reservation_rooms.find({"reservation_id": res["_id"]}).to_list(None)
    busy = await av.busy_room_ids(db, dates)
    for rr in rrs:
        got = None
        options = [rr["room_id"]] + [r["_id"] for r in await av.eligible_rooms(db, rr["category_id"]) if r["_id"] != rr["room_id"] and r["_id"] not in busy]
        for rid in options:
            room = await db.rooms.find_one({"_id": rid})
            if room.get("archived") or room.get("operational_status") != "active":
                continue
            if await av.claim_room(db, rid, dates, res["_id"], "reservation", None, rr["_id"]):
                got = room
                break
        if not got:
            await av.release_nights(db, res["_id"])
            return False
        busy.add(got["_id"])
        upd = {"status": "reserved"}
        if got["_id"] != rr["room_id"]:
            upd.update({"room_id": got["_id"], "room_number": got["number"]})
        await db.reservation_rooms.update_one({"_id": rr["_id"]}, {"$set": upd})
    return True


async def confirm_reservation(db, res_id: str, user: dict | None = None) -> bool:
    res = await db.reservations.find_one({"_id": res_id})
    if not res or res["status"] not in ("pending", "expired"):
        return bool(res and res["status"] in ("confirmed", "checked_in"))
    if res["status"] == "expired" or (res.get("hold_expires_at") and res["hold_expires_at"] < utcnow()):
        if not await reclaim_rooms(db, res):
            return False
    await av.confirm_hold(db, res_id)
    await db.reservations.update_one({"_id": res_id}, {"$set": {"status": "confirmed", "hold_expires_at": None, "updated_at": utcnow()}})
    await db.reservation_rooms.update_many({"reservation_id": res_id, "status": {"$ne": "cancelled"}}, {"$set": {"status": "reserved"}})
    await audit(user, "reservation.confirm", "reservation", res_id)
    return True


async def expire_holds(db) -> int:
    now = utcnow()
    n = 0
    due = await db.reservations.find({"status": "pending", "hold_expires_at": {"$ne": None, "$lt": now}}).to_list(None)
    for r in due:
        got = await db.reservations.find_one_and_update(
            {"_id": r["_id"], "status": "pending", "hold_expires_at": {"$lt": now}},
            {"$set": {"status": "expired", "updated_at": now}})
        if not got:
            continue
        await av.release_nights(db, r["_id"])
        await db.reservation_rooms.update_many({"reservation_id": r["_id"]}, {"$set": {"status": "cancelled"}})
        res = await recompute(db, r["_id"])
        await notify_guest(db, "booking_expired", res)
        n += 1
    await av.purge_expired_holds(db)
    return n


# ---------------- cancellation ----------------
def compute_cancellation(res: dict, settings: dict, now: datetime | None = None) -> dict:
    pol = settings["cancellation"]
    now = now or utcnow()
    hh, mm = (int(x) for x in settings["booking"]["check_in_time"].split(":"))
    ci = datetime.fromisoformat(res["check_in"]) + timedelta(hours=hh, minutes=mm)
    deadline = ci - timedelta(hours=int(pol["free_cancellation_hours"]))
    total = res["pricing"]["total_minor"]
    paid = res["amount_paid"]
    free = (now <= deadline) and not pol.get("non_refundable")
    fee = 0 if free else (total if pol.get("non_refundable") else round_div(total * int(pol["late_fee_percent"]), 100))
    fee = min(fee, paid)
    return {"free_cancellation": free, "deadline": deadline, "fee_minor": fee, "refundable_minor": max(paid - fee, 0)}


async def request_cancellation(db, res: dict, reason: str) -> dict:
    if res["status"] not in ("pending", "confirmed"):
        raise HTTPException(409, "This booking cannot be cancelled online")
    settings = await get_settings(db)
    info = compute_cancellation(res, settings)
    await db.reservations.update_one({"_id": res["_id"]}, {"$set": {
        "status": "cancellation_requested", "updated_at": utcnow(),
        "cancellation": {"requested_at": utcnow(), "requested_reason": reason, "preview": info, "previous_status": res["status"]}}})
    res = await db.reservations.find_one({"_id": res["_id"]})
    await audit(None, "reservation.cancellation_request", "reservation", res["_id"], note=reason)
    await notify_staff(db, "cancellation", f"Cancellation requested – {res['reference']}", reason or "",
                       f"/admin/reservations/{res['_id']}", "reservations.manage", email=True)
    await notify_guest(db, "cancellation_requested", res)
    return res


async def cancel_reservation(db, res: dict, user: dict | None, reason: str, waive_fee: bool = False,
                             refund_override_minor: int | None = None) -> dict:
    if res["status"] not in ("pending", "confirmed", "cancellation_requested"):
        raise HTTPException(409, f"A reservation that is {res['status'].replace('_', ' ')} cannot be cancelled")
    settings = await get_settings(db)
    info = compute_cancellation(res, settings)
    fee = 0 if waive_fee else info["fee_minor"]
    refundable = max(res["amount_paid"] - fee, 0)
    if refund_override_minor is not None:
        if refund_override_minor < 0 or refund_override_minor > res["amount_paid"]:
            raise HTTPException(400, "Refund override must be between 0 and the amount paid")
        refundable, fee = refund_override_minor, res["amount_paid"] - refund_override_minor
    await av.release_nights(db, res["_id"])
    await db.reservation_rooms.update_many({"reservation_id": res["_id"]}, {"$set": {"status": "cancelled"}})
    prev = res.get("cancellation") or {}
    cancellation = {**prev, "cancelled_at": utcnow(), "reason": reason, "cancelled_by": user["name"] if user else "guest",
                    "fee_minor": fee, "refundable_minor": refundable, "policy_free": info["free_cancellation"]}
    await db.reservations.update_one({"_id": res["_id"]}, {"$set": {"status": "cancelled", "hold_expires_at": None,
                                                                    "cancellation": cancellation, "updated_at": utcnow()}})
    fresh = await db.reservations.find_one({"_id": res["_id"]})
    await audit(user, "reservation.cancel", "reservation", res["_id"], before={"status": res["status"]},
                after={"fee_minor": fee, "refundable_minor": refundable}, note=reason)
    if refundable > 0:
        await request_refund(db, fresh, refundable, f"Cancellation of {res['reference']}", user)
    fresh = await recompute(db, res["_id"])
    extra = (f"A refund of {refundable / 100:,.2f} {fresh['pricing']['currency']} has been requested and will be reviewed by the hotel."
             if refundable > 0 else None)
    await notify_guest(db, "cancellation_confirmation", fresh, extra)
    return fresh


async def reject_cancellation_request(db, res: dict, user: dict) -> dict:
    if res["status"] != "cancellation_requested":
        raise HTTPException(409, "No cancellation request to reject")
    prev = (res.get("cancellation") or {}).get("previous_status", "confirmed")
    await db.reservations.update_one({"_id": res["_id"]}, {"$set": {"status": prev, "cancellation": None, "updated_at": utcnow()}})
    await audit(user, "reservation.cancellation_rejected", "reservation", res["_id"])
    return await db.reservations.find_one({"_id": res["_id"]})


# ---------------- modification ----------------
async def _requote(db, res: dict, rrs: list[dict], check_in: str, check_out: str, reason: str, user: dict | None) -> dict:
    settings = await get_settings(db)
    rooms = []
    for rr in rrs:
        rooms.append({"category": await db.room_categories.find_one({"_id": rr["category_id"]}), "room": await db.rooms.find_one({"_id": rr["room_id"]})})
    code = (res["pricing"].get("discount") or {}).get("code")
    try:
        await find_promo(db, code, check_in, len(stay_dates(check_in, check_out)))
    except HTTPException:
        code = None
    quote = await build_quote(db, settings, rooms=rooms, check_in=check_in, check_out=check_out,
                              adults=res["adults"], children=res["children"], promo_code=code)
    history = {"at": utcnow(), "by": user["name"] if user else "system", "reason": reason,
               "check_in": res["check_in"], "check_out": res["check_out"], "pricing": res["pricing"],
               "rooms": [rr["pricing"] for rr in rrs]}
    for rr, rq in zip(rrs, quote["rooms"]):
        await db.reservation_rooms.update_one({"_id": rr["_id"]}, {"$set": {"pricing": rq, "adults": rq["adults"], "children": rq["children"]}})
    pricing = {k: v for k, v in quote.items() if k != "rooms"}
    upd = {"check_in": check_in, "check_out": check_out, "nights": quote["nights"], "pricing": pricing, "updated_at": utcnow()}
    if res["status"] == "pending":
        upd["confirm_threshold"] = confirm_threshold(pricing["total_minor"], settings["payment"])
    await db.reservations.update_one({"_id": res["_id"]}, {"$set": upd, "$push": {"pricing_history": history}})
    return await recompute(db, res["_id"])


async def modify_dates(db, res: dict, check_in: str, check_out: str, user: dict, reason: str = "") -> dict:
    if res["status"] not in ("pending", "confirmed", "checked_in"):
        raise HTTPException(409, "This reservation can no longer be modified")
    settings = await get_settings(db)
    av.validate_stay(settings, check_in, check_out, staff=True)
    if res["status"] == "checked_in" and check_in != res["check_in"]:
        raise HTTPException(400, "Check-in date cannot be changed after check-in")
    old = set(stay_dates(res["check_in"], res["check_out"]))
    new = stay_dates(check_in, check_out)
    add = [d for d in new if d not in old]
    remove = [d for d in old if d not in set(new)]
    rrs = await db.reservation_rooms.find({"reservation_id": res["_id"], "status": {"$ne": "cancelled"}}).to_list(None)
    kind = "hold" if res["status"] == "pending" else "reservation"
    claimed: list[tuple[str, list[str]]] = []
    for rr in rrs:
        if add and not await av.claim_room(db, rr["room_id"], add, res["_id"], kind, res.get("hold_expires_at"), rr["_id"]):
            for rid, ds in claimed:
                await av.release_nights(db, res["_id"], room_id=rid, dates=ds)
            raise HTTPException(409, f"Room {rr['room_number']} is not available for the new dates")
        if add:
            claimed.append((rr["room_id"], add))
    if remove:
        await av.release_nights(db, res["_id"], dates=remove)
    before = {"check_in": res["check_in"], "check_out": res["check_out"], "total": res["total_amount"]}
    fresh = await _requote(db, res, rrs, check_in, check_out, reason or "dates changed", user)
    await audit(user, "reservation.modify_dates", "reservation", res["_id"], before=before,
                after={"check_in": check_in, "check_out": check_out, "total": fresh["total_amount"]}, note=reason)
    await notify_guest(db, "reservation_modified", fresh)
    return fresh


async def assign_room(db, res: dict, rr_id: str, new_room_id: str, user: dict, reason: str = "") -> dict:
    rr = await db.reservation_rooms.find_one({"_id": rr_id, "reservation_id": res["_id"]})
    if not rr or rr["status"] not in ("reserved", "checked_in"):
        raise HTTPException(404, "Reservation room not found or not reassignable")
    if rr["room_id"] == new_room_id:
        raise HTTPException(400, "Room is already assigned")
    room = await db.rooms.find_one({"_id": new_room_id})
    if not room or room.get("archived") or room.get("operational_status") != "active":
        raise HTTPException(409, "The selected room cannot be assigned")
    from ..utils import today

    dates = stay_dates(res["check_in"], res["check_out"])
    if rr["status"] == "checked_in":
        dates = [d for d in dates if d >= today().isoformat()]
    kind = "hold" if res["status"] == "pending" else "reservation"
    if not await av.claim_room(db, new_room_id, dates, res["_id"], kind, res.get("hold_expires_at"), rr["_id"]):
        raise HTTPException(409, f"Room {room['number']} is not available for those dates")
    await av.release_nights(db, res["_id"], room_id=rr["room_id"], dates=dates)
    old_room_id, old_number, old_cat = rr["room_id"], rr["room_number"], rr["category_id"]
    hist = {"room_id": new_room_id, "room_number": room["number"], "at": utcnow(), "by": user["name"], "reason": reason or "reassigned"}
    await db.reservation_rooms.update_one({"_id": rr_id}, {"$set": {"room_id": new_room_id, "room_number": room["number"], "category_id": room["category_id"]},
                                                           "$push": {"assignment_history": hist}})
    if rr["status"] == "checked_in":
        await db.rooms.update_one({"_id": old_room_id}, {"$set": {"occupancy_status": "vacant", "housekeeping_status": "dirty"}})
        await db.rooms.update_one({"_id": new_room_id}, {"$set": {"occupancy_status": "occupied"}})
    fresh_res = await db.reservations.find_one({"_id": res["_id"]})
    if room["category_id"] != old_cat:
        cat = await db.room_categories.find_one({"_id": room["category_id"]})
        await db.reservation_rooms.update_one({"_id": rr_id}, {"$set": {"category_name": cat["name"]}})
        rrs = await db.reservation_rooms.find({"reservation_id": res["_id"], "status": {"$ne": "cancelled"}}).to_list(None)
        fresh_res = await _requote(db, fresh_res, rrs, res["check_in"], res["check_out"], f"category change on reassignment ({old_number}→{room['number']})", user)
    await audit(user, "reservation.reassign_room", "reservation", res["_id"], before={"room": old_number}, after={"room": room["number"]}, note=reason)
    return fresh_res


async def add_charge(db, res: dict, description: str, amount_minor: int, user: dict) -> dict:
    if res["status"] not in ("confirmed", "checked_in", "pending"):
        raise HTTPException(409, "Charges can only be added to active reservations")
    if amount_minor == 0:
        raise HTTPException(400, "Amount cannot be zero")
    charge = {"id": new_id(), "description": description, "amount_minor": amount_minor, "created_by": user["name"], "created_at": utcnow()}
    await db.reservations.update_one({"_id": res["_id"]}, {"$push": {"charges": charge}})
    await audit(user, "reservation.add_charge", "reservation", res["_id"], after={"description": description, "amount_minor": amount_minor})
    return await recompute(db, res["_id"])


async def detail(db, res_id: str) -> dict | None:
    res = await db.reservations.find_one({"_id": res_id})
    if not res:
        return None
    rrs = await db.reservation_rooms.find({"reservation_id": res_id}).to_list(None)
    pays = await db.payments.find({"reservation_id": res_id}).sort([("created_at", 1)]).to_list(None)
    refs = await db.refunds.find({"reservation_id": res_id}).sort([("created_at", 1)]).to_list(None)
    return {"reservation": res, "rooms": rrs, "payments": pays, "refunds": refs}
