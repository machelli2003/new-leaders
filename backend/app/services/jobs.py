"""Background jobs (APScheduler). All jobs are idempotent and safe to run on every instance."""
from __future__ import annotations

import logging
from datetime import timedelta

from ..db import get_db
from ..hotel_settings import get_settings
from ..utils import today, utcnow
from .notify import notify_guest, notify_staff
from .reservations import expire_holds

log = logging.getLogger("nlh.jobs")


async def job_expire_holds():
    try:
        n = await expire_holds(get_db())
        if n:
            log.info("expired %s holds", n)
    except Exception:
        log.exception("expire_holds failed")


async def job_reminders():
    """Daily: check-in reminders, balance reminders, staff arrival/departure digest."""
    db = get_db()
    try:
        s = await get_settings(db)
        n = s["notifications"]
        t = today()
        due_in = (t + timedelta(days=int(n["checkin_reminder_days"]))).isoformat()
        for r in await db.reservations.find({"status": "confirmed", "check_in": due_in, "checkin_reminder_sent": {"$ne": True}}).to_list(None):
            await notify_guest(db, "checkin_reminder", r)
            await db.reservations.update_one({"_id": r["_id"]}, {"$set": {"checkin_reminder_sent": True}})
        bal_date = (t + timedelta(days=int(n["balance_reminder_days"]))).isoformat()
        for r in await db.reservations.find({"status": "confirmed", "check_in": bal_date, "balance": {"$gt": 0}, "balance_reminder_sent": {"$ne": True}}).to_list(None):
            await notify_guest(db, "balance_reminder", r)
            await db.reservations.update_one({"_id": r["_id"]}, {"$set": {"balance_reminder_sent": True}})
        arrivals = await db.reservations.count_documents({"status": "confirmed", "check_in": t.isoformat()})
        departures = await db.reservations.count_documents({"status": "checked_in", "check_out": t.isoformat()})
        if arrivals or departures:
            await notify_staff(db, "digest", f"Today: {arrivals} arrival(s), {departures} departure(s)", "", "/admin/check-in-out", "checkin.manage")
    except Exception:
        log.exception("reminders failed")


def start_scheduler():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    sch = AsyncIOScheduler(timezone="Africa/Accra")
    sch.add_job(job_expire_holds, "interval", seconds=60, id="expire_holds", max_instances=1, coalesce=True)
    sch.add_job(job_reminders, "cron", hour=7, minute=0, id="reminders", max_instances=1)
    sch.start()
    return sch
