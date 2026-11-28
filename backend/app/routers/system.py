"""Audit logs, in-app notifications, Super Admin system tools, Paystack webhook, SEO endpoints."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse

from ..audit import audit
from ..config import get_config
from ..db import get_db
from ..hotel_settings import get_settings
from ..security import current_user, require, require_role
from ..services import finance, paystack
from ..utils import paginate, ser, utcnow
from .common import literal_search_regex
from .hotel import compute_setup_status

router = APIRouter(tags=["system"])


# ---------------- audit logs (read-only: no update/delete endpoints exist) ----------------
@router.get("/audit-logs")
async def audit_logs(q: str | None = None, action: str | None = None, entity: str | None = None, actor: str | None = None, date_from: str | None = None,
                     date_to: str | None = None, page: int = 1, page_size: int = 50, user: dict = Depends(require("audit.view"))):
    query: dict = {}
    if action:
        query["action"] = literal_search_regex(action)
    if entity:
        query["entity"] = entity
    if actor:
        query["actor_name"] = literal_search_regex(actor)
    if q:
        query["$or"] = [{"action": literal_search_regex(q)},
                        {"actor_name": literal_search_regex(q)}, {"entity_id": q}]
    if date_from or date_to:
        rng = {}
        if date_from:
            rng["$gte"] = datetime.fromisoformat(date_from)
        if date_to:
            rng["$lt"] = datetime.fromisoformat(date_to) + timedelta(days=1)
        query["created_at"] = rng
    if user["role"] != "super_admin":  # Super Admin activity is hidden from hotel staff except explicit support access
        query = {"$and": [query, {"$or": [{"actor_role": {"$ne": "super_admin"}}, {"action": {"$regex": "^support\\."}}]}]}
    return await paginate(get_db().audit_logs, query, [("created_at", -1)], page, page_size)


# ---------------- notifications ----------------
@router.get("/notifications")
async def my_notifications(unread_only: bool = False, user: dict = Depends(current_user)):
    items = await get_db().notifications.find({"channel": "in_app"}).sort([("created_at", -1)]).to_list(60)
    out = []
    for n in items:
        if n.get("permission") and n["permission"] not in user["_perms"]:
            continue
        read = user["_id"] in n.get("read_by", [])
        if unread_only and read:
            continue
        d = ser({k: v for k, v in n.items() if k != "read_by"})
        d["read"] = read
        out.append(d)
    return {"items": out, "unread": sum(1 for i in out if not i["read"])}


@router.post("/notifications/read-all")
async def read_all(user: dict = Depends(current_user)):
    await get_db().notifications.update_many({"channel": "in_app"}, {"$addToSet": {"read_by": user["_id"]}})
    return {"ok": True}


@router.post("/notifications/{nid}/read")
async def read_one(nid: str, user: dict = Depends(current_user)):
    await get_db().notifications.update_one({"_id": nid}, {"$addToSet": {"read_by": user["_id"]}})
    return {"ok": True}


@router.get("/notifications/email-log")
async def email_log(page: int = 1, user: dict = Depends(require("audit.view"))):
    return await paginate(get_db().notifications, {"channel": "email"}, [("created_at", -1)], page, 30)


# ---------------- Super Admin tools ----------------
@router.get("/system/overview")
async def overview(user: dict = Depends(require("system.manage"))):
    db = get_db()
    cfg = get_config()
    await db.command("ping") if hasattr(db, "command") else None
    return {
        "environment": cfg.app_env,
        "integrations": {"paystack": cfg.paystack_mode, "email": bool(cfg.resend_api_key), "storage": cfg.storage_backend, "scheduler": cfg.run_scheduler},
        "counts": {"rooms": await db.rooms.count_documents({}), "categories": await db.room_categories.count_documents({}),
                   "reservations": await db.reservations.count_documents({}), "staff": await db.users.count_documents({"role": {"$ne": "super_admin"}}),
                   "media": await db.media.count_documents({}), "payments_pending": await db.payments.count_documents({"status": "pending"})},
        "setup": await compute_setup_status(db),
        "recent_audit": [ser(a) for a in await db.audit_logs.find({}).sort([("created_at", -1)]).to_list(10)],
        "failed_emails": await db.notifications.count_documents({"channel": "email", "status": "failed"}),
    }


@router.post("/system/support/enter-hotel-portal")
async def enter_portal(user: dict = Depends(require_role("super_admin"))):
    await audit(user, "support.enter_hotel_portal", "system", None, note="Super Admin opened the hotel portal")
    return {"ok": True}


@router.post("/system/support/release-expired-holds")
async def release_holds(user: dict = Depends(require("system.manage"))):
    from ..services.reservations import expire_holds

    n = await expire_holds(get_db())
    await audit(user, "support.release_expired_holds", "system", None, after={"released": n})
    return {"released": n}


# ---------------- Paystack webhook ----------------
@router.post("/webhooks/paystack")
async def paystack_webhook(request: Request):
    body = await request.body()
    cfg = get_config()
    if not paystack.verify_signature(cfg.paystack_secret_key, body, request.headers.get("x-paystack-signature")):
        raise HTTPException(401, "Invalid signature")  # unsigned/forged events are never processed
    try:
        event = json.loads(body)
        etype, data = event["event"], event.get("data", {})
    except Exception:
        raise HTTPException(400, "Malformed event")
    db = get_db()
    key = f"{etype}:{data.get('id') or data.get('reference') or data.get('transaction_reference')}"
    seen = await db.transactions.find_one({"key": key})
    if seen and seen.get("processed"):
        return {"status": "duplicate"}  # idempotent: Paystack retries never double-process
    if not seen:
        try:
            await db.transactions.insert_one({"key": key, "event": etype, "reference": data.get("reference"), "received_at": utcnow(), "processed": False})
        except Exception:
            pass
    if etype == "charge.success" and data.get("reference"):
        if await db.payments.find_one({"reference": data["reference"]}):
            await finance.verify_and_apply(db, data["reference"])  # re-verifies amount/currency with Paystack API
    elif etype == "refund.processed":
        await finance.refund_webhook_update(db, data, "processed")
    elif etype in ("refund.failed",):
        await finance.refund_webhook_update(db, data, "failed")
    await db.transactions.update_one({"key": key}, {"$set": {"processed": True, "processed_at": utcnow()}})
    return {"status": "ok"}


# ---------------- SEO ----------------
@router.get("/seo/robots", response_class=PlainTextResponse, include_in_schema=False)
async def robots_txt():
    base = get_config().public_base_url.rstrip("/")
    return f"User-agent: *\nDisallow: /admin\nDisallow: /super-admin\nDisallow: /api/\nDisallow: /booking/\nAllow: /\nSitemap: {base}/sitemap.xml\n"


@router.get("/seo/sitemap", include_in_schema=False)
async def sitemap():
    db = get_db()
    base = get_config().public_base_url.rstrip("/")
    paths = ["/", "/about", "/rooms", "/facilities", "/restaurant", "/events", "/gallery", "/offers", "/contact", "/faq", "/booking/search", "/booking/lookup",
             "/privacy-policy", "/terms", "/cancellation-policy"]
    for c in await db.room_categories.find({"status": "published"}).to_list(None):
        paths.append(f"/rooms/{c['slug']}")
    xml = ['<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    xml += [f"<url><loc>{base}{p}</loc></url>" for p in paths]
    xml.append("</urlset>")
    return Response("".join(xml), media_type="application/xml")
