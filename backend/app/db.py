from __future__ import annotations

from .config import get_config


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
    import asyncpg

    cfg = get_config()
    holder.client = await asyncpg.create_pool(cfg.async_database_url, min_size=1, max_size=10, timeout=8)
    from .postgres_store import PostgresDatabase

    holder.db = PostgresDatabase(holder.client)
    await holder.db.initialize()
    await ensure_indexes(holder.db)


async def close() -> None:
    if holder.client is not None:
        await holder.db.close()
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
    # room_nights: _id is "<room_id>|<date>", unique within the room_nights collection.
    await db.room_nights.create_index("date")
    await db.room_nights.create_index("owner_id")
    await db.room_nights.create_index("hold_expires_at")
    await db.payments.create_index("reference", unique=True)
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
    await db.housekeeping_tasks.create_index("room_id")
    await db.maintenance_requests.create_index("status")
