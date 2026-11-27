import logging
from types import SimpleNamespace

import motor.motor_asyncio
import pytest

from app import db


class FakeMongoClient:
    def __init__(self, *args, fail_ping=False, **kwargs):
        self.fail_ping = fail_ping
        self.closed = False
        self.admin = self

    async def command(self, name):
        if self.fail_ping:
            raise OSError("MongoDB unavailable")
        return {"ok": 1}

    def __getitem__(self, name):
        return object()

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def clear_database_holder():
    db.holder.client = None
    db.holder.db = None
    yield
    db.holder.client = None
    db.holder.db = None


@pytest.mark.asyncio
async def test_connect_logs_success_after_ping_and_index_setup(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="nlh.database")
    client = FakeMongoClient()
    monkeypatch.setattr(motor.motor_asyncio, "AsyncIOMotorClient", lambda *args, **kwargs: client)
    monkeypatch.setattr(db, "get_config", lambda: SimpleNamespace(mongodb_url="mongodb://test", mongodb_database="hotel"))

    async def ensure_indexes(database):
        return None

    monkeypatch.setattr(db, "ensure_indexes", ensure_indexes)

    await db.connect()

    assert "MongoDB connected successfully (database: hotel)" in caplog.text
    assert db.holder.db is not None
    await db.close()
    assert client.closed


@pytest.mark.asyncio
async def test_connect_logs_failure_and_closes_client(monkeypatch, caplog):
    client = FakeMongoClient(fail_ping=True)
    monkeypatch.setattr(motor.motor_asyncio, "AsyncIOMotorClient", lambda *args, **kwargs: client)
    monkeypatch.setattr(db, "get_config", lambda: SimpleNamespace(mongodb_url="mongodb://test", mongodb_database="hotel"))

    with pytest.raises(OSError, match="MongoDB unavailable"):
        await db.connect()

    assert "MongoDB connection or initialization failed" in caplog.text
    assert client.closed
    assert db.holder.client is None
    assert db.holder.db is None
