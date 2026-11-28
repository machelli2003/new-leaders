"""Dashboard + reports computed from real records. CSV/XLSX export supported."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..db import get_db
from ..security import require
from ..utils import parse_date, stay_dates, today

router = APIRouter(prefix="/reports", tags=["reports"])


def _range(start: str | None, end: str | None, default_days: int = 30) -> tuple[str, str]:
    e = parse_date(end) if end else today()
    s = parse_date(start) if start else e - timedelta(days=default_days - 1)
    if s > e or (e - s).days > 800:
        raise HTTPException(400, "Invalid date range")
    return s.isoformat(), e.isoformat()


def _days(s: str, e: str) -> list[str]:
    a, b = parse_date(s), parse_date(e)
    return [(a + timedelta(days=i)).isoformat() for i in range((b - a).days + 1)]


def _d(dt: datetime) -> str:
    return dt.date().isoformat()


def _export(rows: list[dict], columns: list[str], fmt: str, name: str):
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(columns)
        for r in rows:
            w.writerow([("'" + str(r.get(c)) if isinstance(r.get(c), str) and str(r.get(c))[:1] in "=+-@" else r.get(c, "")) for c in columns])  # CSV-injection safe
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(columns)
    for r in rows:
        ws.append([("'" + str(r.get(c)) if isinstance(r.get(c), str) and str(r.get(c))[:1] in "=+-@" else r.get(c)) for c in columns])
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return StreamingResponse(out, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{name}.xlsx"'})


def _major(minor: int) -> float:
    return round(minor / 100, 2)  # display/export only; never used for calculation


async def _revenue_rows(db, s, e):
    pays = await db.payments.find({"status": "success"}).to_list(None)
    refs = await db.refunds.find({"status": "processed"}).to_list(None)
    by: dict[str, dict] = {d: {"date": d, "payments_minor": 0, "refunds_minor": 0, "count": 0} for d in _days(s, e)}
    for p in pays:
        d = _d(p["paid_at"])
        if d in by:
            by[d]["payments_minor"] += p["amount"]
            by[d]["count"] += 1
    for r in refs:
        d = _d(r.get("processed_at") or r["updated_at"])
        if d in by:
            by[d]["refunds_minor"] += r["amount"]
    for v in by.values():
        v["net_minor"] = v["payments_minor"] - v["refunds_minor"]
    return list(by.values())


def _bucket(rows, period):
    if period == "daily":
        return rows
    out: dict[str, dict] = {}
    for r in rows:
        d = parse_date(r["date"])
        key = (d - timedelta(days=d.weekday())).isoformat() if period == "weekly" else d.strftime("%Y-%m")
        b = out.setdefault(key, {"date": key, "payments_minor": 0, "refunds_minor": 0, "net_minor": 0, "count": 0})
        for k in ("payments_minor", "refunds_minor", "net_minor", "count"):
            b[k] += r[k]
    return list(out.values())


@router.get("/revenue")
async def revenue(start: str | None = None, end: str | None = None, period: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
                  format: str = Query("json", pattern="^(json|csv|xlsx)$"), user: dict = Depends(require("reports.financial"))):
    s, e = _range(start, end)
    rows = _bucket(await _revenue_rows(get_db(), s, e), period)
    if format != "json":
        return _export([{**r, "payments": _major(r["payments_minor"]), "refunds": _major(r["refunds_minor"]), "net": _major(r["net_minor"])} for r in rows],
                       ["date", "count", "payments", "refunds", "net"], format, f"revenue-{period}-{s}-{e}")
    return {"start": s, "end": e, "period": period, "rows": rows, "totals": {k: sum(r[k] for r in rows) for k in ("payments_minor", "refunds_minor", "net_minor")}}


async def _occupancy_rows(db, s, e):
    rooms = await db.rooms.count_documents({"archived": {"$ne": True}, "operational_status": "active"})
    nights = await db.room_nights.find({"date": {"$gte": s, "$lte": e}, "kind": "reservation"}).to_list(None)
    sold: dict[str, int] = {}
    for n in nights:
        sold[n["date"]] = sold.get(n["date"], 0) + 1
    return [{"date": d, "rooms_sold": sold.get(d, 0), "rooms_available_total": rooms,
             "occupancy_percent": round(100 * sold.get(d, 0) / rooms, 1) if rooms else 0} for d in _days(s, e)]


@router.get("/occupancy")
async def occupancy(start: str | None = None, end: str | None = None, format: str = Query("json", pattern="^(json|csv|xlsx)$"),
                    user: dict = Depends(require("reports.operational"))):
    s, e = _range(start, end)
    rows = await _occupancy_rows(get_db(), s, e)
    if format != "json":
        return _export(rows, ["date", "rooms_sold", "rooms_available_total", "occupancy_percent"], format, f"occupancy-{s}-{e}")
    avg = round(sum(r["occupancy_percent"] for r in rows) / len(rows), 1) if rows else 0
    return {"start": s, "end": e, "rows": rows, "average_occupancy_percent": avg}


@router.get("/reservations")
async def reservations_report(start: str | None = None, end: str | None = None, status: str | None = None,
                              format: str = Query("json", pattern="^(json|csv|xlsx)$"), user: dict = Depends(require("reports.operational"))):
    s, e = _range(start, end, 30)
    q: dict = {"created_at": {"$gte": datetime.fromisoformat(s), "$lt": datetime.fromisoformat(e) + timedelta(days=1)}}
    if status:
        q["status"] = status
    rows = [{"reference": r["reference"], "created": _d(r["created_at"]), "guest": r["guest"].get("name"), "email": r["guest"].get("email"),
             "check_in": r["check_in"], "check_out": r["check_out"], "nights": r["nights"], "rooms": r["rooms_count"], "status": r["status"],
             "payment_status": r["payment_status"], "total": _major(r["total_amount"]), "paid": _major(r["amount_paid"]), "balance": _major(r["balance"]),
             "source": r["source"]} for r in await get_db().reservations.find(q).sort([("created_at", -1)]).to_list(None)]
    cols = ["reference", "created", "guest", "email", "check_in", "check_out", "nights", "rooms", "status", "payment_status", "total", "paid", "balance", "source"]
    if "reports.financial" not in user["_perms"]:
        cols = [c for c in cols if c not in ("total", "paid", "balance", "email")]
    if format != "json":
        return _export(rows, cols, format, f"reservations-{s}-{e}")
    return {"start": s, "end": e, "columns": cols, "rows": [{c: r[c] for c in cols} for r in rows]}


@router.get("/payments")
async def payments_report(start: str | None = None, end: str | None = None, format: str = Query("json", pattern="^(json|csv|xlsx)$"),
                          user: dict = Depends(require("reports.financial"))):
    s, e = _range(start, end)
    q = {"created_at": {"$gte": datetime.fromisoformat(s), "$lt": datetime.fromisoformat(e) + timedelta(days=1)}}
    rows = [{"date": _d(p["created_at"]), "reference": p["reference"], "reservation": p.get("reservation_reference"), "method": p["method"], "kind": p["kind"],
             "status": p["status"], "amount": _major(p["amount"]), "currency": p["currency"], "receipt": p.get("receipt_number", "")}
            for p in await get_db().payments.find(q).sort([("created_at", -1)]).to_list(None)]
    cols = ["date", "reference", "reservation", "method", "kind", "status", "amount", "currency", "receipt"]
    if format != "json":
        return _export(rows, cols, format, f"payments-{s}-{e}")
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    return {"start": s, "end": e, "columns": cols, "rows": rows, "by_status": by_status}


@router.get("/outstanding")
async def outstanding(format: str = Query("json", pattern="^(json|csv|xlsx)$"), user: dict = Depends(require("reports.financial"))):
    rows = [{"reference": r["reference"], "guest": r["guest"].get("name"), "phone": r["guest"].get("phone"), "check_in": r["check_in"], "check_out": r["check_out"],
             "status": r["status"], "total": _major(r["total_amount"]), "paid": _major(r["amount_paid"]), "balance": _major(r["balance"])}
            for r in await get_db().reservations.find({"status": {"$in": ["confirmed", "checked_in", "checked_out"]}, "balance": {"$gt": 0}}).sort([("check_in", 1)]).to_list(None)]
    cols = ["reference", "guest", "phone", "check_in", "check_out", "status", "total", "paid", "balance"]
    if format != "json":
        return _export(rows, cols, format, "outstanding-balances")
    return {"columns": cols, "rows": rows, "total_balance": round(sum(r["balance"] for r in rows), 2)}


@router.get("/cancellations")
async def cancellations(start: str | None = None, end: str | None = None, format: str = Query("json", pattern="^(json|csv|xlsx)$"),
                        user: dict = Depends(require("reports.operational"))):
    s, e = _range(start, end, 90)
    rows = []
    for r in await get_db().reservations.find({"status": {"$in": ["cancelled", "cancellation_requested", "no_show", "expired"]}}).to_list(None):
        c = r.get("cancellation") or {}
        when = c.get("cancelled_at") or r["updated_at"]
        if s <= _d(when) <= e:
            rows.append({"reference": r["reference"], "guest": r["guest"].get("name"), "status": r["status"], "date": _d(when), "check_in": r["check_in"],
                         "paid": _major(r["pricing"]["total_minor"] and r.get("amount_paid", 0)), "fee": _major(c.get("fee_minor", 0)), "reason": c.get("reason") or c.get("requested_reason", "")})
    cols = ["reference", "guest", "status", "date", "check_in", "paid", "fee", "reason"]
    if format != "json":
        return _export(rows, cols, format, f"cancellations-{s}-{e}")
    return {"start": s, "end": e, "columns": cols, "rows": rows}


@router.get("/refunds")
async def refunds_report(format: str = Query("json", pattern="^(json|csv|xlsx)$"), user: dict = Depends(require("reports.financial"))):
    rows = [{"date": _d(r["created_at"]), "reservation": r["reservation_reference"], "amount": _major(r["amount"]), "method": r["method"], "status": r["status"], "reason": r["reason"]}
            for r in await get_db().refunds.find({}).sort([("created_at", -1)]).to_list(None)]
    cols = ["date", "reservation", "amount", "method", "status", "reason"]
    if format != "json":
        return _export(rows, cols, format, "refunds")
    return {"columns": cols, "rows": rows}


@router.get("/categories")
async def category_performance(start: str | None = None, end: str | None = None, format: str = Query("json", pattern="^(json|csv|xlsx)$"),
                               user: dict = Depends(require("reports.financial"))):
    s, e = _range(start, end)
    db = get_db()
    cats = {c["_id"]: c["name"] for c in await db.room_categories.find({}).to_list(None)}
    stats = {n: {"category": n, "room_nights": 0, "revenue_minor": 0, "reservations": set()} for n in cats.values()}
    for rr in await db.reservation_rooms.find({"status": {"$ne": "cancelled"}}).to_list(None):
        for n in rr["pricing"]["nightly"]:
            if s <= n["date"] <= e:
                st = stats.setdefault(rr["category_name"], {"category": rr["category_name"], "room_nights": 0, "revenue_minor": 0, "reservations": set()})
                st["room_nights"] += 1
                st["revenue_minor"] += n["rate_minor"]
                st["reservations"].add(rr["reservation_id"])
    rows = [{"category": v["category"], "room_nights": v["room_nights"], "reservations": len(v["reservations"]), "revenue": _major(v["revenue_minor"]),
             "avg_rate": _major(v["revenue_minor"] // v["room_nights"]) if v["room_nights"] else 0} for v in stats.values()]
    cols = ["category", "reservations", "room_nights", "revenue", "avg_rate"]
    if format != "json":
        return _export(rows, cols, format, f"category-performance-{s}-{e}")
    return {"start": s, "end": e, "columns": cols, "rows": rows}


@router.get("/guests")
async def guests_report(format: str = Query("json", pattern="^(json|csv|xlsx)$"), user: dict = Depends(require("reports.operational", "guests.view"))):
    db = get_db()
    rows = []
    for g in await db.guests.find({}).to_list(None):
        res = await db.reservations.find({"guest_id": g["_id"]}).to_list(None)
        rows.append({"name": g["name"], "email": g.get("email") or "", "phone": g.get("phone") or "", "country": g.get("country") or "",
                     "reservations": len(res), "total_paid": _major(sum(r["amount_paid"] for r in res)),
                     "last_stay": max((r["check_in"] for r in res), default="")})
    rows.sort(key=lambda r: r["reservations"], reverse=True)
    cols = ["name", "email", "phone", "country", "reservations", "total_paid", "last_stay"]
    if "reports.financial" not in user["_perms"]:
        cols = [c for c in cols if c != "total_paid"]
    if format != "json":
        return _export(rows, cols, format, "guests")
    return {"columns": cols, "rows": [{c: r[c] for c in cols} for r in rows]}


@router.get("/dashboard")
async def dashboard(start: str | None = None, end: str | None = None, user: dict = Depends(require("dashboard.view"))):
    db = get_db()
    s, e = _range(start, end)
    t = today().isoformat()
    fin = "reports.financial" in user["_perms"]
    rooms = await db.rooms.find({"archived": {"$ne": True}}).to_list(None)
    from .catalog import room_display_status

    ds = await room_display_status(db, rooms)
    counts: dict[str, int] = {}
    for v in ds.values():
        counts[v] = counts.get(v, 0) + 1
    active_rooms = [r for r in rooms if r.get("operational_status") == "active"]
    occupied = counts.get("occupied", 0)
    all_res = await db.reservations.find({}).to_list(None)
    room_reservations = [r for r in all_res if r.get("booking_type", "room") != "event"]
    upcoming = sorted([r for r in room_reservations if r["status"] == "confirmed" and r["check_in"] >= t], key=lambda r: r["check_in"])[:8]
    today_arrivals = sorted(
        [r for r in room_reservations if r["check_in"] == t and r["status"] in ("confirmed", "pending", "checked_in")],
        key=lambda r: r.get("created_at"),
    )
    today_departures = sorted(
        [r for r in room_reservations if r["check_out"] == t and r["status"] in ("checked_in", "checked_out")],
        key=lambda r: r.get("check_out"),
    )

    def operation_item(r: dict) -> dict:
        return {"id": r["_id"], "reference": r["reference"], "guest": r["guest"].get("name"),
                "check_in": r["check_in"], "check_out": r["check_out"], "status": r["status"], "rooms": r["rooms_count"]}

    rooms_not_ready = []
    for room in rooms:
        if room.get("archived"):
            continue
        housekeeping_status = room.get("housekeeping_status", "ready")
        operational_status = room.get("operational_status", "active")
        if operational_status != "active" or (
            housekeeping_status != "ready" and room.get("occupancy_status") != "occupied"
        ):
            rooms_not_ready.append({
                "id": room["_id"], "number": room["number"],
                "status": operational_status if operational_status != "active" else housekeeping_status,
            })

    data = {
        "today": t,
        "total_reservations": len(all_res),
        "todays_check_ins": sum(1 for r in all_res if r["check_in"] == t and r["status"] in ("confirmed", "checked_in")),
        "todays_check_outs": sum(1 for r in all_res if r["check_out"] == t and r["status"] in ("checked_in", "checked_out")),
        "pending_reservations": sum(1 for r in all_res if r["status"] == "pending"),
        "cancellation_requests": sum(1 for r in all_res if r["status"] == "cancellation_requested"),
        "needs_attention": sum(1 for r in all_res if r.get("needs_attention")),
        "rooms_total": len(rooms), "rooms_occupied": occupied, "rooms_available": counts.get("available", 0),
        "rooms_maintenance": counts.get("maintenance", 0) + counts.get("out_of_service", 0),
        "occupancy_percent": round(100 * occupied / len(active_rooms), 1) if active_rooms else 0,
        "upcoming": [{"id": r["_id"], "reference": r["reference"], "guest": r["guest"].get("name"), "check_in": r["check_in"], "check_out": r["check_out"], "rooms": r["rooms_count"]} for r in upcoming],
        "today_arrivals": [operation_item(r) for r in today_arrivals],
        "today_departures": [operation_item(r) for r in today_departures],
        "reservation_trend": [],
        "occupancy_trend": await _occupancy_rows(db, s, e),
    }
    if "housekeeping.view" in user["_perms"]:
        data["rooms_not_ready"] = sorted(rooms_not_ready, key=lambda room: room["number"])
    if "payments.view" in user["_perms"]:
        overdue_balances = sorted(
            [r for r in room_reservations if r["check_in"] <= t
             and r["status"] in ("confirmed", "checked_in", "checked_out") and r.get("balance", 0) > 0],
            key=lambda r: (r["check_in"], r["reference"]),
        )
        data["overdue_balance_count"] = len(overdue_balances)
        data["overdue_balances"] = [
            {**operation_item(r), "balance_minor": r["balance"]} for r in overdue_balances[:8]
        ]
    if "maintenance.manage" in user["_perms"]:
        maintenance_filter = {"status": {"$in": ["open", "in_progress"]}}
        data["open_maintenance_count"] = await db.maintenance_requests.count_documents(maintenance_filter)
        maintenance = await db.maintenance_requests.find(maintenance_filter).sort([("created_at", -1)]).to_list(8)
        data["open_maintenance"] = [
            {"id": item["_id"], "title": item["title"], "priority": item["priority"],
             "status": item["status"], "room_numbers": item.get("room_numbers", [])}
            for item in maintenance
        ]
    created: dict[str, int] = {}
    for r in all_res:
        d = _d(r["created_at"])
        created[d] = created.get(d, 0) + 1
    data["reservation_trend"] = [{"date": d, "count": created.get(d, 0)} for d in _days(s, e)]
    if fin:
        rev = await _revenue_rows(db, s, e)
        data["revenue_trend"] = rev
        data["total_revenue_minor"] = sum(r["net_minor"] for r in rev)
        data["outstanding_balances_minor"] = sum(r["balance"] for r in all_res if r["status"] in ("confirmed", "checked_in", "checked_out"))
        pays = await db.payments.find({}).sort([("created_at", -1)]).to_list(8)
        data["recent_payments"] = [{"id": p["_id"], "reference": p["reference"], "reservation": p.get("reservation_reference"), "amount_minor": p["amount"],
                                    "status": p["status"], "method": p["method"], "created_at": p["created_at"].isoformat() + "Z"} for p in pays]
        by_status: dict[str, int] = {}
        for p in await db.payments.find({"created_at": {"$gte": datetime.fromisoformat(s)}}).to_list(None):
            by_status[p["status"]] = by_status.get(p["status"], 0) + 1
        data["payment_status"] = [{"status": k, "count": v} for k, v in by_status.items()]
        cat = await category_performance(s, e, "json", user)
        data["category_performance"] = cat["rows"]
    return data
