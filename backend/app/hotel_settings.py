"""Single-hotel settings document (hotel_settings/_id='main'). No tenant concept."""
from __future__ import annotations

import copy
from typing import Any

from .utils import utcnow

DEFAULTS: dict[str, Any] = {
    "published": False,
    "profile": {
        "name": "New Leaders Hotel and Events Centre",
        "branch_name": "Eastern Region (Akyem Tafo)",
        "description": "",
        "address": "",
        "town": "Akyem Tafo",
        "region": "Eastern Region",
        "country": "Ghana",
        "latitude": None,
        "longitude": None,
        "phones": [],
        "emails": [],
        "website_domain": "",
        "socials": {"facebook": "", "instagram": "", "x": "", "tiktok": "", "youtube": "", "whatsapp": ""},
        "logo_media_id": None,
        "banner_media_ids": [],
    },
    "booking": {
        "currency": "GHS",
        "check_in_time": "14:00",
        "check_out_time": "12:00",
        "min_nights": 1,
        "max_nights": 30,
        "max_rooms_per_booking": 5,
        "max_advance_days": 365,
        "hold_minutes": 30,
        "weekend_days": [4, 5],  # Mon=0 ... Fri=4, Sat=5 (nights that use the weekend rate)
        "checkin_requires": "none",  # none | deposit | full  (staff may override with permission)
        "booking_rules": "",
        "setup_confirmed": False,
    },
    "payment": {
        "require_full_payment": True,
        "deposit_enabled": False,
        "deposit_type": "percent",  # percent | fixed
        "deposit_percent": 50,
        "deposit_fixed_minor": 0,
        "min_online_payment_minor": 0,
        "allow_pay_at_hotel": False,
        "channels": ["card", "mobile_money"],
        "balance_policy": "",
    },
    "taxes": [],  # [{name, rate_bp, enabled}]  e.g. rate_bp 1250 == 12.5%. Left empty until the hotel confirms its rates.
    "cancellation": {
        "free_cancellation_hours": 48,
        "late_fee_percent": 100,
        "non_refundable": False,
        "description": "",
    },
    "notifications": {
        "send_guest_emails": True,
        "staff_emails": [],
        "checkin_reminder_days": 1,
        "balance_reminder_days": 3,
        "whatsapp_enabled": False,  # optional, provider integration not bundled
    },
}


def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


async def get_settings(db) -> dict:
    doc = await db.hotel_settings.find_one({"_id": "main"}) or {}
    return deep_merge(DEFAULTS, {k: v for k, v in doc.items() if k != "_id"})


async def save_section(db, section: str, value: Any) -> None:
    await db.hotel_settings.update_one(
        {"_id": "main"}, {"$set": {section: value, "updated_at": utcnow()}}, upsert=True
    )
