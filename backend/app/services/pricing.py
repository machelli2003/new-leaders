"""Pricing engine. All money is integer minor units (pesewas). No floats anywhere."""
from __future__ import annotations

from datetime import date

from fastapi import HTTPException

from ..utils import parse_date, round_div, stay_dates, today, utcnow

TYPE_RANK = {"date": 4, "holiday": 3, "seasonal": 2, "weekend": 1}


def distribute(total: int, n: int) -> list[int]:
    base, rem = divmod(total, n)
    return [base + (1 if i < rem else 0) for i in range(n)]


def _matches(rule: dict, d: date, weekend_days: list[int]) -> bool:
    if rule.get("active", True) is False:
        return False
    ds = d.isoformat()
    if rule.get("start_date") and ds < rule["start_date"]:
        return False
    if rule.get("end_date") and ds > rule["end_date"]:
        return False
    if rule["type"] == "weekend":
        wd = rule.get("weekdays") or weekend_days
        if d.weekday() not in wd:
            return False
    return True


def nightly_rate(d: date, category: dict, room: dict | None, rules: list[dict], weekend_days: list[int]) -> tuple[int, str]:
    """Most special date type wins (date > holiday > seasonal > weekend), then most specific scope
    (room > category > global), then explicit priority. Falls back to room override, then category default."""
    best, best_key = None, None
    for r in rules:
        if r.get("room_id") and (not room or r["room_id"] != room["_id"]):
            continue
        if r.get("category_id") and r["category_id"] != category["_id"]:
            continue
        if not _matches(r, d, weekend_days):
            continue
        spec = 2 if r.get("room_id") else 1 if r.get("category_id") else 0
        key = (TYPE_RANK.get(r["type"], 0), spec, r.get("priority", 0))
        if best_key is None or key > best_key:
            best, best_key = r, key
    if best:
        return int(best["rate_minor"]), f"{best['type']}:{best.get('name', '')}"
    if room and room.get("price_override_minor"):
        return int(room["price_override_minor"]), "room_override"
    return int(category.get("default_rate_minor") or 0), "base"


async def find_promo(db, code: str | None, check_in: str, nights: int) -> dict | None:
    if not code:
        return None
    promo = await db.promotions.find_one({"code": code.strip().upper()})
    if not promo or promo.get("status") != "published":
        raise HTTPException(400, "Promo code is not valid")
    if promo.get("valid_from") and check_in < promo["valid_from"]:
        raise HTTPException(400, "Promo code is not yet valid for these dates")
    if promo.get("valid_to") and check_in > promo["valid_to"]:
        raise HTTPException(400, "Promo code has expired for these dates")
    if nights < int(promo.get("min_nights") or 1):
        raise HTTPException(400, f"Promo code requires at least {promo['min_nights']} nights")
    return promo


async def build_quote(db, settings: dict, *, rooms: list[dict], check_in: str, check_out: str,
                      adults: int, children: int, promo_code: str | None = None) -> dict:
    """rooms: [{"category": <doc>, "room": <doc|None>}] one entry per physical room being sold.
    Returns a self-contained pricing snapshot."""
    dates = stay_dates(check_in, check_out)
    n_rooms = len(rooms)
    if not dates or n_rooms == 0:
        raise HTTPException(400, "Invalid stay")
    rules = await db.pricing_rules.find({"active": {"$ne": False}}).to_list(None)
    weekend_days = settings["booking"].get("weekend_days", [4, 5])
    adults_each = distribute(adults, n_rooms)
    children_each = distribute(children, n_rooms)

    room_quotes = []
    acc_total = extra_total = 0
    for i, rr in enumerate(rooms):
        cat, room = rr["category"], rr.get("room")
        nightly = []
        for ds in dates:
            rate, source = nightly_rate(parse_date(ds), cat, room, rules, weekend_days)
            nightly.append({"date": ds, "rate_minor": rate, "source": source})
        acc = sum(n["rate_minor"] for n in nightly)
        guests = adults_each[i] + children_each[i]
        included = int(cat.get("included_guests") or cat.get("max_occupancy") or guests)
        extra_guests = max(0, guests - included)
        extra = extra_guests * int(cat.get("extra_guest_fee_minor") or 0) * len(dates)
        room_quotes.append(
            {
                "category_id": cat["_id"],
                "category_name": cat["name"],
                "room_id": room["_id"] if room else None,
                "adults": adults_each[i],
                "children": children_each[i],
                "nightly": nightly,
                "accommodation_minor": acc,
                "extra_guest_count": extra_guests,
                "extra_guest_minor": extra,
            }
        )
        acc_total += acc
        extra_total += extra

    promo = await find_promo(db, promo_code, check_in, len(dates))
    discount = 0
    if promo:
        if promo.get("discount_type") == "percent":
            discount = round_div(acc_total * int(promo["value"]), 100)
        else:
            discount = int(promo["value"])
        discount = min(discount, acc_total)

    subtotal = acc_total + extra_total - discount
    taxes = []
    for t in settings.get("taxes", []):
        if t.get("enabled", True):
            taxes.append({"name": t["name"], "rate_bp": int(t["rate_bp"]), "amount_minor": round_div(subtotal * int(t["rate_bp"]), 10000)})
    total = subtotal + sum(t["amount_minor"] for t in taxes)

    return {
        "currency": settings["booking"]["currency"],
        "check_in": check_in,
        "check_out": check_out,
        "nights": len(dates),
        "rooms": room_quotes,
        "accommodation_minor": acc_total,
        "extra_guest_minor": extra_total,
        "discount": {"code": promo["code"] if promo else None, "title": promo["title"] if promo else None, "amount_minor": discount},
        "subtotal_minor": subtotal,
        "taxes": taxes,
        "total_minor": total,
        "created_at": utcnow(),
    }


def deposit_amount(total: int, ps: dict) -> int:
    if ps.get("deposit_type") == "fixed":
        dep = min(int(ps.get("deposit_fixed_minor") or 0), total)
    else:
        dep = round_div(total * int(ps.get("deposit_percent") or 0), 100)
    dep = max(dep, int(ps.get("min_online_payment_minor") or 0))
    return min(dep, total)


def confirm_threshold(total: int, ps: dict) -> int:
    """Amount that must be paid online before the reservation is confirmed."""
    if ps.get("require_full_payment") or not ps.get("deposit_enabled"):
        return total
    return deposit_amount(total, ps)


def payment_options(total: int, paid: int, ps: dict) -> dict:
    due = max(total - paid, 0)
    opts = {"full": due, "deposit": None}
    if due > 0 and not ps.get("require_full_payment") and ps.get("deposit_enabled"):
        dep = max(deposit_amount(total, ps) - paid, 0)
        if 0 < dep < due:
            opts["deposit"] = dep
    return opts
