"""Public guest booking API: search, quote, book (hold), pay, lookup, cancellation request, optional guest accounts."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field, model_validator

from ..audit import audit
from ..db import get_db
from ..hotel_settings import get_settings
from ..security import (booking_limiter, create_access_token, decode_token, hash_password, public_limiter, validate_password_strength,
                        payment_status_limiter, verify_password)
from ..services import availability as av
from ..services import finance
from ..services import reservations as rs
from ..services.notify import notify_guest, notify_staff
from ..services.pricing import build_quote, payment_options, stay_dates
from ..utils import ser, utcnow

router = APIRouter(tags=["bookings"])


class Selection(BaseModel):
    category_id: str
    quantity: int = Field(ge=1, le=10)


class StayIn(BaseModel):
    check_in: str
    check_out: str
    adults: int = Field(ge=1, le=30)
    children: int = Field(default=0, ge=0, le=30)
    selections: list[Selection] = Field(min_length=1, max_length=5)
    promo_code: str | None = Field(default=None, max_length=30)


class GuestIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr | None = None
    phone: str = Field(min_length=7, max_length=30, pattern=r"^[0-9+()\-\s]+$")
    country: str = Field(default="Ghana", max_length=80)


class BookIn(StayIn):
    guest: GuestIn
    special_requests: str = Field(default="", max_length=1000)
    pay_at_hotel: bool = False


def _public_res(res: dict, rrs: list[dict] | None = None, payments: list[dict] | None = None, options: dict | None = None) -> dict:
    d = {k: res.get(k) for k in ("reference", "booking_type", "event_booking", "status", "payment_status", "guest", "check_in", "check_out", "nights", "adults", "children",
                                  "special_requests", "total_amount", "amount_paid", "balance", "hold_expires_at", "cancellation")}
    d["pricing"] = {k: res["pricing"].get(k) for k in ("currency", "accommodation_minor", "extra_guest_minor", "discount", "taxes", "total_minor")}
    d["charges"] = res.get("charges", [])
    if rrs is not None:
        d["rooms"] = [{"category_name": r["category_name"], "adults": r["adults"], "children": r["children"], "status": r["status"],
                       "nightly": r["pricing"]["nightly"]} for r in rrs]
    if payments is not None:
        d["payments"] = [{"reference": p["reference"], "amount": p["amount"], "status": p["status"], "method": p["method"],
                          "paid_at": p.get("paid_at"), "receipt_number": p.get("receipt_number")} for p in payments if p["status"] == "success"]
    if options is not None:
        d["payment_options"] = options
    return ser(d)


async def _get_by_ref(db, reference: str, email: str | None = None, phone: str | None = None) -> dict:
    res = await db.reservations.find_one({"reference": reference.strip().upper()})
    guest = (res or {}).get("guest") or {}
    email_matches = not email or (guest.get("email") or "").lower() == email.strip().lower()
    phone_matches = not phone or "".join(c for c in guest.get("phone", "") if c.isdigit()) == "".join(c for c in phone if c.isdigit())
    if not res or not email_matches or not phone_matches:
        raise HTTPException(404, "We couldn't find a booking with those details")
    return res


async def _full(db, res: dict) -> dict:
    s = await get_settings(db)
    rrs = await db.reservation_rooms.find({"reservation_id": res["_id"]}).to_list(None)
    pays = await db.payments.find({"reservation_id": res["_id"]}).sort([("created_at", 1)]).to_list(None)
    opts = payment_options(res["total_amount"], res["amount_paid"], s["payment"]) if res["status"] in ("pending", "confirmed", "checked_in") else None
    return _public_res(res, rrs, pays, opts)


@router.post("/availability/search", dependencies=[Depends(public_limiter)])
async def search(body: StayIn):
    """Availability + live price for every published category (all calculated on the server)."""
    db = get_db()
    s = await get_settings(db)
    av.validate_stay(s, body.check_in, body.check_out)
    results = await av.category_availability(db, body.check_in, body.check_out, public_only=True)
    out = []
    qty_hint = 1
    for r in results:
        cat = r["category"]
        quote = None
        if r["available"] > 0 and cat.get("default_rate_minor"):
            quote = await build_quote(db, s, rooms=[{"category": cat, "room": None}], check_in=body.check_in, check_out=body.check_out,
                                      adults=max(body.adults, 1), children=body.children)
        total_rooms_needed = 1
        out.append({"category_id": cat["_id"], "slug": cat["slug"], "name": cat["name"], "short_description": cat.get("short_description", ""),
                    "max_occupancy": cat.get("max_occupancy"), "bed_configuration": cat.get("bed_configuration", ""), "main_media_id": cat.get("main_media_id"),
                    "available_rooms": r["available"], "fits_guests": av.fits(cat, max(r["available"], 1), body.adults, body.children),
                    "per_room_total_minor": quote["total_minor"] if quote else None,
                    "avg_nightly_minor": (quote["accommodation_minor"] // quote["nights"]) if quote else None,
                    "currency": s["booking"]["currency"], "nights": len(stay_dates(body.check_in, body.check_out))})
    from .website import resolve

    return await resolve(db, out)


@router.post("/bookings/quote", dependencies=[Depends(public_limiter)])
async def quote(body: StayIn):
    db = get_db()
    s = await get_settings(db)
    av.validate_stay(s, body.check_in, body.check_out)
    rooms = []
    for sel in body.selections:
        cat = await db.room_categories.find_one({"_id": sel.category_id, "status": "published"})
        if not cat:
            raise HTTPException(404, "Room category not found")
        rooms += [{"category": cat, "room": None}] * sel.quantity
    q = await build_quote(db, s, rooms=rooms, check_in=body.check_in, check_out=body.check_out, adults=body.adults, children=body.children,
                          promo_code=body.promo_code)
    from ..services.pricing import confirm_threshold, deposit_amount

    q["payment_options"] = payment_options(q["total_minor"], 0, s["payment"])
    q["confirm_threshold_minor"] = confirm_threshold(q["total_minor"], s["payment"])
    return ser(q)


@router.post("/bookings", status_code=201, dependencies=[Depends(booking_limiter)])
async def create_booking(body: BookIn):
    db = get_db()
    s = await get_settings(db)
    if body.pay_at_hotel and not s["payment"]["allow_pay_at_hotel"]:
        raise HTTPException(400, "Pay-at-hotel is not available. Please pay online to secure your booking.")
    if not body.pay_at_hotel and not body.guest.email:
        raise HTTPException(400, "An email address is required for online Paystack payment.")
    sels = [{"category_id": x.category_id, "quantity": x.quantity} for x in body.selections]
    res = await rs.create_reservation(
        db, selections=sels, check_in=body.check_in, check_out=body.check_out, adults=body.adults, children=body.children,
        guest=body.guest.model_dump(), special_requests=body.special_requests, promo_code=body.promo_code, source="online",
        hold=not body.pay_at_hotel, confirm_now=body.pay_at_hotel)
    if res["status"] == "confirmed":
        await notify_guest(db, "booking_confirmation", res)
        await notify_staff(db, "reservation", f"New reservation {res['reference']} (pay at hotel)", f"{res['guest']['name']} · {res['check_in']} → {res['check_out']}",
                           f"/admin/reservations/{res['_id']}", "reservations.view", email=True)
    else:
        await notify_guest(db, "booking_received", res)
    return await _full(db, res)


class LookupIn(BaseModel):
    reference: str = Field(min_length=6, max_length=30)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=7, max_length=30, pattern=r"^[0-9+()\-\s]+$")

    @model_validator(mode="after")
    def require_contact(self):
        if not self.email and not self.phone:
            raise ValueError("Provide the email or phone number used when booking")
        return self


@router.post("/bookings/lookup", dependencies=[Depends(booking_limiter)])
async def lookup(body: LookupIn):
    db = get_db()
    return await _full(db, await _get_by_ref(db, body.reference, body.email, body.phone))


class PayIn(LookupIn):
    option: str = Field(default="full", pattern="^(full|deposit)$")


@router.post("/bookings/pay", dependencies=[Depends(booking_limiter)])
async def pay(body: PayIn):
    db = get_db()
    res = await _get_by_ref(db, body.reference, body.email, body.phone)
    return await finance.init_online_payment(db, res, body.option)


@router.get("/bookings/payment-status/{payment_reference}", dependencies=[Depends(payment_status_limiter)])
async def payment_status(payment_reference: str):
    """Called by the success/failed pages. Verifies with Paystack server-side; the redirect itself proves nothing."""
    db = get_db()
    p = await finance.verify_and_apply(db, payment_reference)
    res = await db.reservations.find_one({"_id": p["reservation_id"]})
    return {"status": p["status"], "reference": res["reference"], "amount_minor": p["amount"], "currency": p["currency"],
            "booking_type": res.get("booking_type", "room"), "event_booking": res.get("event_booking"),
            "reservation_status": res["status"], "needs_attention": res.get("needs_attention", False)}


class CancelReqIn(LookupIn):
    reason: str = Field(default="", max_length=500)


@router.post("/bookings/cancel-request", dependencies=[Depends(booking_limiter)])
async def cancel_request(body: CancelReqIn):
    db = get_db()
    res = await _get_by_ref(db, body.reference, body.email, body.phone)
    res = await rs.request_cancellation(db, res, body.reason)
    return await _full(db, res)


@router.post("/bookings/cancel-preview", dependencies=[Depends(booking_limiter)])
async def cancel_preview(body: LookupIn):
    db = get_db()
    res = await _get_by_ref(db, body.reference, body.email, body.phone)
    info = rs.compute_cancellation(res, await get_settings(db))
    return ser(info)


# ---------------- optional guest accounts ----------------
class RegisterIn(GuestIn):
    password: str


class GuestLoginIn(BaseModel):
    email: EmailStr
    password: str


@router.post("/bookings/account/register", status_code=201, dependencies=[Depends(booking_limiter)])
async def guest_register(body: RegisterIn):
    db = get_db()
    validate_password_strength(body.password, body.email)
    g = await rs.upsert_guest(db, body.model_dump(exclude={"password"}))
    if g.get("password_hash"):
        raise HTTPException(409, "An account already exists for this email")
    await db.guests.update_one({"_id": g["_id"]}, {"$set": {"password_hash": hash_password(body.password), "token_version": 0, "has_account": True}})
    g = await db.guests.find_one({"_id": g["_id"]})
    return {"access_token": create_access_token(g, typ="guest"), "guest": {"name": g["name"], "email": g["email"]}}


@router.post("/bookings/account/login", dependencies=[Depends(booking_limiter)])
async def guest_login(body: GuestLoginIn):
    db = get_db()
    g = await db.guests.find_one({"email": body.email.lower()})
    if not g or not g.get("password_hash") or not verify_password(body.password, g["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    return {"access_token": create_access_token(g, typ="guest"), "guest": {"name": g["name"], "email": g["email"]}}


@router.get("/bookings/account/bookings")
async def guest_bookings(request: Request):
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "Not authenticated")
    data = decode_token(auth[7:], typ="guest")
    db = get_db()
    g = await db.guests.find_one({"_id": data["sub"]})
    if not g:
        raise HTTPException(401, "Account not found")
    items = await db.reservations.find({"guest_id": g["_id"]}).sort([("check_in", -1)]).to_list(100)
    return {"guest": {"name": g["name"], "email": g["email"], "phone": g.get("phone"), "country": g.get("country")},
            "bookings": [await _full(db, r) for r in items]}
