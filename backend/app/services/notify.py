"""Transactional email (Resend) + in-app staff notifications. Failures never break business flows."""
from __future__ import annotations

import html
import logging

import httpx

from ..config import get_config
from ..hotel_settings import get_settings
from ..utils import new_id, utcnow

log = logging.getLogger("nlh.notify")


def money(minor: int, currency: str = "GHS") -> str:
    return f"{currency} {minor / 100:,.2f}"


async def send_email(db, to: str, subject: str, body_html: str, kind: str, reservation_id: str | None = None) -> str:
    cfg = get_config()
    rec = {"_id": new_id(), "channel": "email", "kind": kind, "to": to, "subject": subject,
           "reservation_id": reservation_id, "created_at": utcnow(), "status": "skipped", "detail": None}
    if not cfg.resend_api_key:
        rec["detail"] = "Email provider not configured (set RESEND_API_KEY)"
    else:
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post("https://api.resend.com/emails",
                                 headers={"Authorization": f"Bearer {cfg.resend_api_key}"},
                                 json={"from": cfg.email_from, "to": [to], "subject": subject, "html": body_html})
            rec["status"] = "sent" if r.status_code < 300 else "failed"
            if r.status_code >= 300:
                rec["detail"] = r.text[:300]
        except Exception as e:
            rec["status"], rec["detail"] = "failed", type(e).__name__
    await db.notifications.insert_one(rec)
    return rec["status"]


def _layout(hotel: dict, title: str, lines: list[str], res: dict | None) -> str:
    name = html.escape(hotel["profile"]["name"])
    rows = ""
    if res:
        cur = res.get("pricing", {}).get("currency", "GHS")
        if res.get("booking_type") == "event":
            event = res["event_booking"]
            detail_rows = (
                f"<tr><td style='padding:4px 12px 4px 0;color:#666'>Venue</td><td>{html.escape(event['venue_name'])}</td></tr>"
                f"<tr><td style='padding:4px 12px 4px 0;color:#666'>Event time</td><td>{html.escape(event['date'])}, "
                f"{html.escape(event['start_time'])}–{html.escape(event['end_time'])} ({event['attendees']} guests)</td></tr>"
            )
        else:
            detail_rows = (
                f"<tr><td style='padding:4px 12px 4px 0;color:#666'>Stay</td><td>{res['check_in']} → {res['check_out']} ({res['nights']} nights)</td></tr>"
            )
        rows = (
            f"<table style='border-collapse:collapse;margin:16px 0'>"
            f"<tr><td style='padding:4px 12px 4px 0;color:#666'>Booking reference</td><td><b>{html.escape(res['reference'])}</b></td></tr>"
            f"{detail_rows}"
            f"<tr><td style='padding:4px 12px 4px 0;color:#666'>Total</td><td>{money(res.get('total_amount', 0), cur)}</td></tr>"
            f"<tr><td style='padding:4px 12px 4px 0;color:#666'>Paid</td><td>{money(res.get('amount_paid', 0), cur)}</td></tr>"
            f"<tr><td style='padding:4px 12px 4px 0;color:#666'>Balance</td><td>{money(res.get('balance', 0), cur)}</td></tr></table>"
        )
    body = "".join(f"<p>{html.escape(l)}</p>" for l in lines)
    return (f"<div style='font-family:Arial,sans-serif;max-width:560px;margin:auto'><h2>{html.escape(title)}</h2>"
            f"{body}{rows}<p style='color:#888;font-size:12px'>{name}</p></div>")


TEMPLATES = {
    "booking_received": ("Booking received", "We have received your booking and are holding your selected inventory. Please complete payment before the hold expires."),
    "booking_confirmation": ("Booking confirmed", "Your booking is confirmed. We look forward to welcoming you."),
    "payment_confirmation": ("Payment received", "Thank you. We have received your payment."),
    "deposit_receipt": ("Deposit received", "We have received your deposit. The outstanding balance is shown below."),
    "balance_reminder": ("Outstanding balance reminder", "This is a reminder that a balance remains on your booking."),
    "reservation_modified": ("Your booking was updated", "Your reservation has been modified. The updated details are below."),
    "cancellation_confirmation": ("Booking cancelled", "Your booking has been cancelled."),
    "refund_notification": ("Refund update", "There is an update on your refund."),
    "checkin_reminder": ("Your stay is coming up", "A reminder of your upcoming stay with us."),
    "booking_expired": ("Booking hold expired", "Your booking hold expired because payment was not completed. You are welcome to book again."),
    "cancellation_requested": ("Cancellation request received", "We received your cancellation request and will respond shortly."),
}


async def notify_guest(db, kind: str, res: dict, extra: str | None = None) -> None:
    try:
        settings = await get_settings(db)
        if not settings["notifications"].get("send_guest_emails", True):
            return
        email = (res.get("guest") or {}).get("email")
        if not email:
            return
        title, line = TEMPLATES[kind]
        lines = [f"Dear {res['guest'].get('name', 'guest')},", line] + ([extra] if extra else [])
        await send_email(db, email, f"{title} – {res['reference']}", _layout(settings, title, lines, res), kind, res["_id"])
    except Exception:  # pragma: no cover
        log.exception("guest notification failed")


async def notify_staff(db, kind: str, title: str, body: str = "", link: str | None = None,
                       permission: str | None = None, email: bool = False) -> None:
    try:
        await db.notifications.insert_one(
            {"_id": new_id(), "channel": "in_app", "audience": "staff", "kind": kind, "title": title, "body": body,
             "link": link, "permission": permission, "created_at": utcnow(), "read_by": []}
        )
        if email:
            settings = await get_settings(db)
            for addr in settings["notifications"].get("staff_emails", []):
                await send_email(db, addr, title, _layout(settings, title, [body], None), kind)
    except Exception:  # pragma: no cover
        log.exception("staff notification failed")
