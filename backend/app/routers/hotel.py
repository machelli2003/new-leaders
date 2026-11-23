"""Hotel profile, settings and the setup wizard status/publish."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from ..audit import audit
from ..config import get_config
from ..db import get_db
from ..hotel_settings import get_settings, save_section
from ..security import require
from ..utils import utcnow

router = APIRouter(tags=["hotel"])


class Socials(BaseModel):
    facebook: str = ""
    instagram: str = ""
    x: str = ""
    tiktok: str = ""
    youtube: str = ""
    whatsapp: str = ""


class ProfileIn(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    branch_name: str = ""
    description: str = ""
    address: str = ""
    town: str = ""
    region: str = ""
    country: str = "Ghana"
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    phones: list[str] = []
    emails: list[EmailStr] = []
    website_domain: str = ""
    socials: Socials = Socials()
    logo_media_id: str | None = None
    banner_media_ids: list[str] = []


class BookingIn(BaseModel):
    currency: Literal["GHS"] = "GHS"
    check_in_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    check_out_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    min_nights: int = Field(ge=1, le=30)
    max_nights: int = Field(ge=1, le=120)
    max_rooms_per_booking: int = Field(ge=1, le=20)
    max_advance_days: int = Field(ge=1, le=730)
    hold_minutes: int = Field(ge=5, le=240)
    weekend_days: list[int] = Field(default=[4, 5])
    checkin_requires: Literal["none", "deposit", "full"] = "none"
    booking_rules: str = ""


class PaymentIn(BaseModel):
    require_full_payment: bool
    deposit_enabled: bool
    deposit_type: Literal["percent", "fixed"] = "percent"
    deposit_percent: int = Field(default=50, ge=1, le=100)
    deposit_fixed_minor: int = Field(default=0, ge=0)
    min_online_payment_minor: int = Field(default=0, ge=0)
    allow_pay_at_hotel: bool = False
    channels: list[Literal["card", "mobile_money", "bank", "bank_transfer", "ussd", "qr"]] = ["card", "mobile_money"]
    balance_policy: str = ""


class TaxIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    rate_bp: int = Field(ge=0, le=5000, description="basis points: 1250 = 12.5%")
    enabled: bool = True


class CancellationIn(BaseModel):
    free_cancellation_hours: int = Field(ge=0, le=24 * 60)
    late_fee_percent: int = Field(ge=0, le=100)
    non_refundable: bool = False
    description: str = ""


class NotificationsIn(BaseModel):
    send_guest_emails: bool = True
    staff_emails: list[EmailStr] = []
    checkin_reminder_days: int = Field(default=1, ge=0, le=14)
    balance_reminder_days: int = Field(default=3, ge=0, le=30)
    whatsapp_enabled: bool = False


@router.get("/hotel/profile")
async def get_profile(user: dict = Depends(require("dashboard.view"))):
    s = await get_settings(get_db())
    return {"profile": s["profile"], "published": s["published"]}


@router.put("/hotel/profile")
async def put_profile(body: ProfileIn, user: dict = Depends(require("hotel.manage"))):
    db = get_db()
    before = (await get_settings(db))["profile"]
    after = body.model_dump()
    after["emails"] = [str(e) for e in after["emails"]]
    await save_section(db, "profile", after)
    await audit(user, "hotel.profile_update", "hotel_settings", "main", before=before, after=after)
    return {"profile": after}


@router.get("/settings")
async def get_all_settings(user: dict = Depends(require("dashboard.view"))):
    s = await get_settings(get_db())
    s.pop("profile")
    cfg = get_config()
    s["integrations"] = {"paystack": cfg.paystack_mode, "email_configured": bool(cfg.resend_api_key),
                         "storage_backend": cfg.storage_backend}
    return s


async def _save(user, section: str, value, action: str):
    db = get_db()
    before = (await get_settings(db))[section]
    await save_section(db, section, value)
    await audit(user, action, "hotel_settings", section, before=before, after=value)
    return {section: value}


@router.put("/settings/booking")
async def put_booking(body: BookingIn, user: dict = Depends(require("hotel.manage"))):
    if body.max_nights < body.min_nights:
        raise HTTPException(422, "Maximum nights must be at least the minimum nights")
    if any(d < 0 or d > 6 for d in body.weekend_days):
        raise HTTPException(422, "weekend_days must be numbers 0 (Mon) to 6 (Sun)")
    val = body.model_dump()
    val["setup_confirmed"] = True
    return await _save(user, "booking", val, "settings.booking_update")


@router.put("/settings/payment")
async def put_payment(body: PaymentIn, user: dict = Depends(require("settings.payments"))):
    return await _save(user, "payment", body.model_dump(), "settings.payment_update")


@router.put("/settings/taxes")
async def put_taxes(body: list[TaxIn], user: dict = Depends(require("pricing.manage"))):
    return await _save(user, "taxes", [t.model_dump() for t in body], "settings.taxes_update")


@router.put("/settings/cancellation")
async def put_cancellation(body: CancellationIn, user: dict = Depends(require("settings.payments"))):
    return await _save(user, "cancellation", body.model_dump(), "settings.cancellation_update")


@router.put("/settings/notifications")
async def put_notifications(body: NotificationsIn, user: dict = Depends(require("hotel.manage"))):
    val = body.model_dump()
    val["staff_emails"] = [str(e) for e in val["staff_emails"]]
    return await _save(user, "notifications", val, "settings.notifications_update")


async def compute_setup_status(db) -> dict:
    s = await get_settings(db)
    p = s["profile"]
    cats = await db.room_categories.find({"status": {"$ne": "archived"}}).to_list(None)
    published = [c for c in cats if c.get("status") == "published"]
    rooms = await db.rooms.count_documents({"archived": {"$ne": True}})
    cfg = get_config()
    staff = await db.users.count_documents({"role": "hotel_admin", "is_active": True})
    sections = await db.website_sections.count_documents({"status": "published"})
    facilities = await db.content_items.count_documents({"type": "facility", "status": "published"})
    unpriced = [c["name"] for c in published if not c.get("default_rate_minor")]

    def step(key, label, required, missing):
        return {"key": key, "label": label, "required": required, "complete": not missing, "missing": missing}

    steps = [
        step("profile", "Hotel profile", True,
             [m for m, ok in [("Address", p["address"]), ("At least one phone number", p["phones"]), ("At least one email", p["emails"]),
                              ("Description", p["description"])] if not ok]),
        step("categories", "Room categories", True, [] if published else ["Publish at least one room category"]),
        step("rooms", "Physical rooms", True, [] if rooms else ["Create at least one physical room"]),
        step("pricing", "Pricing", True, ([f"Set a nightly rate for: {', '.join(unpriced)}"] if unpriced else []) + ([] if published else ["Create priced categories"])),
        step("facilities", "Facilities & services", False, [] if facilities else ["Add and publish facilities"]),
        step("website", "Website content", False, [] if sections else ["Publish homepage content"]),
        step("booking", "Booking & payment settings", True,
             [] if s["booking"].get("setup_confirmed") else ["Review and save booking settings (check-in/out times, rules)"]),
        step("payments", "Online payments (Paystack)", False,
             [] if cfg.paystack_mode != "unconfigured" else ["Paystack key not set on the server (PAYSTACK_SECRET_KEY)"]),
        step("staff", "Staff accounts", False, [] if staff else ["Create a Hotel Admin account"]),
    ]
    req = [x for x in steps if x["required"]]
    return {"steps": steps, "ready_to_publish": all(x["complete"] for x in req), "published": s["published"],
            "completion_percent": int(100 * sum(x["complete"] for x in steps) / len(steps))}


@router.get("/hotel/setup-status")
async def setup_status(user: dict = Depends(require("hotel.manage"))):
    return await compute_setup_status(get_db())


@router.post("/hotel/publish")
async def publish(user: dict = Depends(require("hotel.manage"))):
    db = get_db()
    st = await compute_setup_status(db)
    if not st["ready_to_publish"]:
        missing = [m for x in st["steps"] if x["required"] for m in x["missing"]]
        raise HTTPException(409, "Required setup is incomplete: " + "; ".join(missing))
    await save_section(db, "published", True)
    await audit(user, "website.publish_site", "hotel_settings", "main")
    return {"published": True}


@router.post("/hotel/unpublish")
async def unpublish(user: dict = Depends(require("hotel.manage"))):
    await save_section(get_db(), "published", False)
    await audit(user, "website.unpublish_site", "hotel_settings", "main")
    return {"published": False}
