from __future__ import annotations

import logging

from .config import get_config

log = logging.getLogger("nlh.database")


class _Holder:
    client = None
    db = None


holder = _Holder()


def get_db():
    if holder.db is None:
        raise RuntimeError("Database not initialised")
    return holder.db


def set_db(db) -> None:
    holder.db = db


async def connect() -> None:
    cfg = get_config()
    if not cfg.mongodb_url:
        raise RuntimeError("MONGODB_URL must be set")

    from motor.motor_asyncio import AsyncIOMotorClient

    holder.client = AsyncIOMotorClient(cfg.mongodb_url, serverSelectionTimeoutMS=8000)
    try:
        await holder.client.admin.command("ping")
        holder.db = holder.client[cfg.mongodb_database]
        await ensure_indexes(holder.db)
    except Exception:
        log.exception("MongoDB connection or initialization failed for database '%s'", cfg.mongodb_database)
        holder.client.close()
        holder.client = None
        holder.db = None
        raise
    log.info("MongoDB connected successfully (database: %s)", cfg.mongodb_database)


async def close() -> None:
    if holder.client is not None:
        holder.client.close()
        holder.client = None
        holder.db = None


async def ensure_indexes(db) -> None:
    """Unique indexes carry the integrity guarantees (no double booking, unique refs)."""
    await db.users.create_index("email", unique=True)
    await db.refresh_tokens.create_index("token_hash", unique=True)
    await db.refresh_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.room_categories.create_index("slug", unique=True)
    await db.rooms.create_index("number", unique=True)
    await db.rooms.create_index("category_id")
    await db.reservations.create_index("reference", unique=True)
    await db.reservations.create_index([("check_in", 1), ("check_out", 1)])
    await db.reservations.create_index("status")
    await db.reservations.create_index("guest_id")
    await db.reservation_rooms.create_index("reservation_id")
    await db.reservation_rooms.create_index("room_id")
    await db.event_venues.create_index("slug", unique=True)
    await db.event_booking_slots.create_index("reservation_id")
    await db.event_booking_slots.create_index("hold_expires_at")
    # room_nights: _id is "<room_id>|<date>", unique within the room_nights collection.
    await db.room_nights.create_index("date")
    await db.room_nights.create_index("owner_id")
    await db.room_nights.create_index("hold_expires_at")
    await db.payments.create_index("reference", unique=True)
    await db.payments.create_index("idempotency_key", unique=True, sparse=True)
    await db.payments.create_index("reservation_id")
    await db.payments.create_index("paystack_transaction_id", unique=True, sparse=True)
    await db.refunds.create_index("reservation_id")
    await db.transactions.create_index("key", unique=True)
    await db.guests.create_index("email")
    await db.guests.create_index("phone")
    await db.media.create_index("category")
    await db.website_sections.create_index("key", unique=True)
    await db.content_items.create_index([("type", 1), ("status", 1)])
    await db.promotions.create_index("code", unique=True, sparse=True)
    await db.pricing_rules.create_index("category_id")
    await db.room_blocks.create_index("room_id")
    await db.audit_logs.create_index([("created_at", -1)])
    await db.audit_logs.create_index("entity_id")
    await db.notifications.create_index([("created_at", -1)])
    await db.account_verifications.create_index("email", unique=True)
    await db.account_verifications.create_index("expires_at", expireAfterSeconds=0)
    await db.account_password_resets.create_index("guest_id", unique=True)
    await db.account_password_resets.create_index("token_hash", unique=True)
    await db.account_password_resets.create_index("expires_at", expireAfterSeconds=0)
    await db.housekeeping_tasks.create_index("room_id")
    await db.maintenance_requests.create_index("status")
