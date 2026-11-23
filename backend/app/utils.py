"""Shared helpers: ids, hotel-local dates (Africa/Accra), money, serialization."""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

ACCRA = ZoneInfo("Africa/Accra")
HIDDEN_KEYS = {"password_hash", "mfa_secret", "token_hash", "mfa_pending_secret"}

# Test hooks (never set in production)
_now_override: datetime | None = None
_today_override: date | None = None


def set_clock(now: datetime | None = None, today_: date | None = None) -> None:
    global _now_override, _today_override
    _now_override, _today_override = now, today_


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    """Naive UTC datetime, matching the database's stored timestamp representation."""
    if _now_override is not None:
        return _now_override
    n = datetime.now(timezone.utc).replace(tzinfo=None)
    return n.replace(microsecond=(n.microsecond // 1000) * 1000)


def today() -> date:
    """Today's date in the hotel's time zone (Africa/Accra)."""
    if _today_override is not None:
        return _today_override
    return datetime.now(ACCRA).date()


def parse_date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except Exception:
        raise ValueError(f"Invalid date '{s}', expected YYYY-MM-DD")


def stay_dates(check_in: str, check_out: str) -> list[str]:
    """Occupied nights: check-out date is NOT an occupied night."""
    a, b = parse_date(check_in), parse_date(check_out)
    return [(a + timedelta(days=i)).isoformat() for i in range((b - a).days)]


def round_div(a: int, b: int) -> int:
    """Integer division rounding half up (non-negative values)."""
    return (a * 2 + b) // (2 * b)


def slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return s or "item"


def ser(o: Any) -> Any:
    """Make a Mongo document JSON-friendly: _id -> id, drop private/sensitive keys, ISO datetimes."""
    if isinstance(o, dict):
        out: dict[str, Any] = {}
        for k, v in o.items():
            if k == "_id":
                out["id"] = v
            elif k.startswith("_") or k in HIDDEN_KEYS:
                continue
            else:
                out[k] = ser(v)
        return out
    if isinstance(o, (list, tuple)):
        return [ser(x) for x in o]
    if isinstance(o, datetime):
        return o.isoformat() + "Z"
    if isinstance(o, date):
        return o.isoformat()
    return o


async def paginate(coll, query: dict, sort: list[tuple[str, int]], page: int = 1, page_size: int = 25, projection=None) -> dict:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    total = await coll.count_documents(query)
    cur = coll.find(query, projection).sort(sort).skip((page - 1) * page_size).limit(page_size)
    items = await cur.to_list(None)
    return {"items": [ser(i) for i in items], "total": total, "page": page, "page_size": page_size}


def extract_media_ids(obj: Any) -> list[str]:
    """Find media references in a document: keys `media_id`, `*_media_id`, `media_ids`, `*_media_ids`."""
    found: set[str] = set()

    def walk(x: Any):
        if isinstance(x, dict):
            for k, v in x.items():
                if k.startswith("_"):
                    continue
                if (k == "media_id" or k.endswith("_media_id")) and isinstance(v, str) and v:
                    found.add(v)
                elif (k == "media_ids" or k.endswith("_media_ids")) and isinstance(v, list):
                    found.update(i for i in v if isinstance(i, str) and i)
                else:
                    walk(v)
        elif isinstance(x, list):
            for i in x:
                walk(i)

    walk(obj)
    return sorted(found)
