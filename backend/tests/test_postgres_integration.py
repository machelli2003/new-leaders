import os
from urllib.parse import unquote, urlsplit

import asyncpg
import pytest

from app import db as database
from app.config import Settings
from app.postgres_store import DuplicateKeyError, PostgresDatabase, ReturnDocument

_TEST_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not _TEST_URL, reason="POSTGRES_TEST_DATABASE_URL is not configured")


@pytest.fixture
async def postgres_db():
    dsn = Settings(database_url=_TEST_URL).async_database_url
    database_name = unquote(urlsplit(dsn).path.lstrip("/"))
    if not database_name.endswith("_test"):
        pytest.fail("POSTGRES_TEST_DATABASE_URL must point to a dedicated database ending in _test")

    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4, timeout=8)
    db = PostgresDatabase(pool)
    try:
        await db.initialize()
        await database.ensure_indexes(db)
        async with pool.acquire() as conn:
            await conn.execute("TRUNCATE TABLE app_documents")
        yield db
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_postgres_queries_updates_and_room_night_uniqueness(postgres_db):
    user = {
        "_id": "test-user",
        "email": "guest@example.test",
        "role": "hotel_admin",
        "profile": {"name": "Ama"},
        "created_at": "2026-11-22",
    }
    await postgres_db.users.insert_one(user)

    matches = await postgres_db.users.find(
        {"$or": [{"profile.name": {"$regex": "^ama$", "$options": "i"}}, {"role": {"$in": ["receptionist"]}}]}
    ).to_list(None)
    assert [row["_id"] for row in matches] == ["test-user"]
    assert await postgres_db.users.count_documents({}) == 1

    updated = await postgres_db.users.find_one_and_update(
        {"_id": "test-user"},
        {"$set": {"profile.name": "Ama Mensah"}, "$inc": {"login_count": 1}},
        return_document=ReturnDocument.AFTER,
    )
    assert updated["profile"]["name"] == "Ama Mensah"
    assert updated["login_count"] == 1

    with pytest.raises(DuplicateKeyError):
        await postgres_db.users.insert_one({"_id": "duplicate-email", "email": "guest@example.test"})

    await postgres_db.room_nights.insert_one({"_id": "room-1|2026-12-01", "owner_id": "winner"})
    with pytest.raises(DuplicateKeyError):
        await postgres_db.room_nights.insert_many(
            [
                {"_id": "room-1|2026-11-30", "owner_id": "loser"},
                {"_id": "room-1|2026-12-01", "owner_id": "loser"},
            ],
            ordered=False,
        )
    await postgres_db.room_nights.delete_many({"owner_id": "loser"})
    assert await postgres_db.room_nights.count_documents({"owner_id": "loser"}) == 0
    assert await postgres_db.room_nights.count_documents({"owner_id": "winner"}) == 1
