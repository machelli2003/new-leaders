"""Bookable event venues and hourly event reservations."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from pymongo.errors import BulkWriteError, DuplicateKeyError

from ..audit import audit
from ..db import get_db
from ..hotel_settings import get_settings
from ..security import booking_limiter, public_limiter, require
from ..services import finance
from ..services.notify import notify_guest
from ..services.pricing import confirm_threshold, payment_options
from ..utils import new_id, parse_date, round_div, ser, slugify, today, utcnow
from .common import partial

router = APIRouter(tags=["event venues"])
VenueStatus = Literal["draft", "published", "archived"]


class VenueIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str | None = None
    description: str = Field(default="", max_length=3000)
    capacity: int = Field(ge=1, le=10000)
    hourly_rate_minor: int = Field(default=0, ge=0)
    opening_time: str = Field(default="06:00", pattern=r"^\d{2}:\d{2}$")
    closing_time: str = Field(default="23:00", pattern=r"^\d{2}:\d{2}$")
    capacity_confirmed: bool = True
    main_media_id: str | None = None
    gallery_media_ids: list[str] = Field(default_factory=list)
    status: VenueStatus = "draft"


VenuePatch = partial(VenueIn)


def _minutes(value: str) -> int:
    try:
        parsed = datetime.strptime(value, "%H:%M")
    except ValueError as exc:
        raise HTTPException(422, "Times must use 24-hour HH:MM format") from exc
    minutes = parsed.hour * 60 + parsed.minute
    if minutes % 15:
        raise HTTPException(422, "Times must be in 15-minute increments")
    return minutes


def _validate_venue(venue: dict) -> None:
    start, end = _minutes(venue["opening_time"]), _minutes(venue["closing_time"])
    if end <= start:
        raise HTTPException(422, "Closing time must be after opening time")
    if venue["status"] == "published":
        if venue["hourly_rate_minor"] <= 0:
            raise HTTPException(422, "Set an hourly rate before publishing this venue")
        if not venue.get("capacity_confirmed", venue.get("slug") != "event-centre"):
            raise HTTPException(422, "Confirm the event centre's actual maximum capacity before publishing")


async def _unique_slug(db, name: str, requested: str | None = None, exclude: str | None = None) -> str:
    base = slugify(requested or name)
    slug = base
    suffix = 2
    while True:
        existing = await db.event_venues.find_one({"slug": slug})
        if not existing or existing["_id"] == exclude:
            return slug
        slug = f"{base}-{suffix}"
        suffix += 1


async def _resolved(db, items: list[dict] | dict) -> list[dict] | dict:
    from .website import resolve

    return await resolve(db, [ser(x) for x in items] if isinstance(items, list) else ser(items))


@router.get("/event-venues", dependencies=[Depends(public_limiter)])
async def public_venues():
    db = get_db()
    venues = await db.event_venues.find({"status": "published", "hourly_rate_minor": {"$gt": 0}}).sort([("name", 1)]).to_list(None)
    return await _resolved(db, venues)


@router.get("/event-venues/admin")
async def admin_venues(user: dict = Depends(require("rooms.view"))):
    db = get_db()
    venues = await db.event_venues.find({"status": {"$ne": "archived"}}).sort([("name", 1)]).to_list(None)
    return await _resolved(db, venues)


@router.post("/event-venues/admin/defaults", status_code=201)
async def add_default_venues(user: dict = Depends(require("rooms.manage"))):
    db = get_db()
    now = utcnow()
    defaults = [
        ("conference-room-100", "Conference Room (100 seats)", 100, "Conference room with seating for up to 100 guests."),
        ("conference-room-30", "Conference Room (30 seats)", 30, "Conference room with seating for up to 30 guests."),
        ("event-centre", "Event Centre (500+ guests)", 501, "Event centre for engagements, parties, weddings and other celebrations."),
    ]
    created = []
    for slug, name, capacity, description in defaults:
        if await db.event_venues.find_one({"slug": slug}):
            continue
        venue = {
            "_id": new_id(), "slug": slug, "name": name, "description": description,
            "capacity": capacity, "hourly_rate_minor": 0, "opening_time": "06:00", "closing_time": "23:00",
            "capacity_confirmed": slug != "event-centre",
            "main_media_id": None, "gallery_media_ids": [], "status": "draft",
            "created_at": now, "updated_at": now,
        }
        await db.event_venues.insert_one(venue)
        created.append(venue)
    await audit(user, "event_venues.add_defaults", "event_venue", None, after={"created": [v["slug"] for v in created]})
    return await _resolved(db, created)


@router.post("/event-venues/admin", status_code=201)
async def create_venue(body: VenueIn, user: dict = Depends(require("rooms.manage"))):
    db = get_db()
    venue = body.model_dump()
    _validate_venue(venue)
    venue.update({
        "_id": new_id(), "slug": await _unique_slug(db, body.name, body.slug),
        "created_at": utcnow(), "updated_at": utcnow(),
    })
    await db.event_venues.insert_one(venue)
    await audit(user, "event_venue.create", "event_venue", venue["_id"], after=venue)
    return await _resolved(db, venue)


@router.patch("/event-venues/admin/{venue_id}")
async def update_venue(venue_id: str, body: VenuePatch, user: dict = Depends(require("rooms.manage"))):
    db = get_db()
    before = await db.event_venues.find_one({"_id": venue_id})
    if not before:
        raise HTTPException(404, "Event venue not found")
    patch = body.model_dump(exclude_unset=True)
    merged = {**before, **patch}
    _validate_venue(merged)
    if "name" in patch or "slug" in patch:
        patch["slug"] = await _unique_slug(db, patch.get("name", before["name"]), patch.get("slug"), venue_id)
    patch["updated_at"] = utcnow()
    await db.event_venues.update_one({"_id": venue_id}, {"$set": patch})
    after = await db.event_venues.find_one({"_id": venue_id})
    await audit(user, "event_venue.update", "event_venue", venue_id, before=before, after=after)
    return await _resolved(db, after)


@router.delete("/event-venues/admin/{venue_id}")
async def archive_venue(venue_id: str, user: dict = Depends(require("rooms.manage"))):
    db = get_db()
    venue = await db.event_venues.find_one({"_id": venue_id})
    if not venue:
        raise HTTPException(404, "Event venue not found")
    await db.event_venues.update_one({"_id": venue_id}, {"$set": {"status": "archived", "updated_at": utcnow()}})
    await audit(user, "event_venue.archive", "event_venue", venue_id, before={"status": venue["status"]})
    return {"ok": True}


class EventDetails(BaseModel):
    venue_id: str
    date: str
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    attendees: int = Field(ge=1, le=10000)
    event_type: str = Field(min_length=2, max_length=80)


class EventQuoteIn(EventDetails):
    pass


class EventGuest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=30, pattern=r"^[0-9+()\-\s]+$")
    country: str = Field(default="Ghana", max_length=80)


class EventBookIn(EventDetails):
    guest: EventGuest
    special_requests: str = Field(default="", max_length=1000)
    payment_option: Literal["full", "deposit"] = "full"


def _slot_ids(venue_id: str, date: str, start: int, end: int) -> list[str]:
    return [f"{venue_id}|{date}|{minute:04d}" for minute in range(start, end, 15)]


async def _event_quote(db, body: EventDetails) -> tuple[dict, dict]:
    try:
        date = parse_date(body.date)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if date < today():
        raise HTTPException(400, "Event date cannot be in the past")
    settings = await get_settings(db)
    if (date - today()).days > int(settings["booking"]["max_advance_days"]):
        raise HTTPException(400, "Event date is too far in advance")

    venue = await db.event_venues.find_one({"_id": body.venue_id, "status": "published"})
    if not venue or int(venue.get("hourly_rate_minor") or 0) <= 0:
        raise HTTPException(404, "Event venue not found or not bookable")
    if body.attendees > int(venue["capacity"]):
        raise HTTPException(400, f"This venue accommodates up to {venue['capacity']} guests")

    start, end = _minutes(body.start_time), _minutes(body.end_time)
    opening, closing = _minutes(venue["opening_time"]), _minutes(venue["closing_time"])
    if start < opening or end > closing or end <= start:
        raise HTTPException(400, f"Choose a time between {venue['opening_time']} and {venue['closing_time']}")
    duration = end - start
    if duration < 60:
        raise HTTPException(400, "Event bookings must be at least one hour")

    slots = _slot_ids(venue["_id"], body.date, start, end)
    now = utcnow()
    await db.event_booking_slots.delete_many({"_id": {"$in": slots}, "hold_expires_at": {"$ne": None, "$lt": now}})
    occupied = await db.event_booking_slots.find_one({"_id": {"$in": slots}})
    subtotal = round_div(int(venue["hourly_rate_minor"]) * duration, 60)
    taxes = [
        {"name": tax["name"], "rate_bp": int(tax["rate_bp"]),
         "amount_minor": round_div(subtotal * int(tax["rate_bp"]), 10000)}
        for tax in settings.get("taxes", []) if tax.get("enabled", True)
    ]
    total = subtotal + sum(tax["amount_minor"] for tax in taxes)
    options = payment_options(total, 0, settings["payment"])
    quote = {
        "venue_id": venue["_id"], "venue_name": venue["name"], "date": body.date,
        "start_time": body.start_time, "end_time": body.end_time, "duration_minutes": duration,
        "hourly_rate_minor": venue["hourly_rate_minor"], "attendees": body.attendees,
        "subtotal_minor": subtotal, "taxes": taxes, "total_minor": total,
        "currency": settings["booking"]["currency"], "payment_options": options,
        "available": occupied is None,
    }
    return quote, venue


@router.post("/event-bookings/quote", dependencies=[Depends(public_limiter)])
async def quote_event(body: EventQuoteIn):
    quote, _ = await _event_quote(get_db(), body)
    return quote


async def _claim_slots(db, venue_id: str, date: str, start: int, end: int, reservation_id: str, expires_at) -> bool:
    slots = _slot_ids(venue_id, date, start, end)
    now = utcnow()
    await db.event_booking_slots.delete_many({"_id": {"$in": slots}, "hold_expires_at": {"$ne": None, "$lt": now}})
    rows = [{"_id": slot, "reservation_id": reservation_id, "hold_expires_at": expires_at, "created_at": now} for slot in slots]
    try:
        await db.event_booking_slots.insert_many(rows, ordered=False)
        return True
    except (DuplicateKeyError, BulkWriteError):
        await db.event_booking_slots.delete_many({"_id": {"$in": slots}, "reservation_id": reservation_id})
        return False


@router.post("/event-bookings", status_code=201, dependencies=[Depends(booking_limiter)])
async def create_event_booking(body: EventBookIn):
    db = get_db()
    quote, venue = await _event_quote(db, body)
    if not quote["available"]:
        raise HTTPException(409, "That time is no longer available. Choose another time.")

    settings = await get_settings(db)
    now = utcnow()
    reservation_id = new_id()
    hold_expires_at = now + timedelta(minutes=int(settings["booking"]["hold_minutes"]))
    start, end = _minutes(body.start_time), _minutes(body.end_time)
    if not await _claim_slots(db, venue["_id"], body.date, start, end, reservation_id, hold_expires_at):
        raise HTTPException(409, "That time was just booked. Choose another time.")

    from ..services.reservations import generate_reference, upsert_guest

    event_details = {
        "venue_id": venue["_id"], "venue_name": venue["name"], "date": body.date,
        "start_time": body.start_time, "end_time": body.end_time, "duration_minutes": quote["duration_minutes"],
        "attendees": body.attendees, "event_type": body.event_type,
    }
    try:
        guest = await upsert_guest(db, body.guest.model_dump())
        total = quote["total_minor"]
        reference = await generate_reference(db)
        reservation = {
            "_id": reservation_id, "reference": reference, "booking_type": "event",
            "event_booking": event_details, "status": "pending", "payment_status": "unpaid", "source": "online",
            "guest_id": guest["_id"],
            "guest": {"name": guest["name"], "email": guest.get("email"), "phone": guest.get("phone"), "country": guest.get("country")},
            "check_in": body.date, "check_out": (parse_date(body.date) + timedelta(days=1)).isoformat(), "nights": 1,
            "adults": body.attendees, "children": 0, "rooms_count": 1,
            "special_requests": body.special_requests, "internal_notes": "", "pricing_history": [], "charges": [],
            "pricing": {
                "currency": quote["currency"], "accommodation_minor": quote["subtotal_minor"], "extra_guest_minor": 0,
                "discount": {"code": None, "title": None, "amount_minor": 0},
                "subtotal_minor": quote["subtotal_minor"], "taxes": quote["taxes"], "total_minor": total,
                "nights": 1,
            },
            "total_amount": total, "amount_paid": 0, "balance": total,
            "confirm_threshold": confirm_threshold(total, settings["payment"]),
            "hold_expires_at": hold_expires_at, "checked_in_at": None, "checked_out_at": None,
            "cancellation": None, "needs_attention": False, "created_by": None,
            "created_at": now, "updated_at": now,
        }
        await db.reservations.insert_one(reservation)
        payment = await finance.init_online_payment(db, reservation, body.payment_option)
    except Exception:
        await db.event_booking_slots.delete_many({"reservation_id": reservation_id})
        await db.reservations.update_one({"_id": reservation_id}, {"$set": {"status": "expired", "hold_expires_at": None}})
        raise
    await audit(None, "event_booking.create", "reservation", reservation_id,
                after={"reference": reference, **event_details, "total_minor": total})
    await notify_guest(db, "booking_received", reservation)
    return {
        "reference": reference, "payment_reference": payment["reference"],
        "authorization_url": payment["authorization_url"], "amount_minor": payment["amount_minor"],
    }


@router.get("/event-bookings/admin")
async def admin_event_bookings(user: dict = Depends(require("reservations.view"))):
    bookings = await get_db().reservations.find({"booking_type": "event"}).sort([("event_booking.date", -1), ("created_at", -1)]).to_list(500)
    return [ser(booking) for booking in bookings]


@router.post("/event-bookings/admin/{reservation_id}/cancel")
async def cancel_event_booking(reservation_id: str, body: dict, user: dict = Depends(require("reservations.manage"))):
    db = get_db()
    reservation = await db.reservations.find_one({"_id": reservation_id, "booking_type": "event"})
    if not reservation:
        raise HTTPException(404, "Event booking not found")
    from ..services.reservations import cancel_reservation

    return ser(await cancel_reservation(db, reservation, user, str(body.get("reason", ""))))


@router.post("/event-bookings/admin/{reservation_id}/reject-cancellation")
async def reject_event_cancellation(reservation_id: str, user: dict = Depends(require("reservations.manage"))):
    db = get_db()
    reservation = await db.reservations.find_one({"_id": reservation_id, "booking_type": "event"})
    if not reservation:
        raise HTTPException(404, "Event booking not found")
    from ..services.reservations import reject_cancellation_request

    return ser(await reject_cancellation_request(db, reservation, user))
