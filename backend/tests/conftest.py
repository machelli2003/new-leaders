import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ.update(
    APP_ENV="test", RUN_SCHEDULER="false", BCRYPT_ROUNDS="4", RATE_LIMIT_ENABLED="false",
    JWT_SECRET="test-secret-test-secret-test-secret-123", PAYSTACK_SECRET_KEY="sk_test_unit_secret",
    LOCAL_UPLOAD_DIR=_tmp, STORAGE_BACKEND="local",
)

import hashlib
import hmac
import json
import os
from datetime import date, timedelta
from urllib.parse import unquote, urlsplit

import httpx
import pytest
from mongomock_motor import AsyncMongoMockClient

from app import db as database
from app.config import Settings
from app import utils
from app.main import app
from app.security import hash_password
from app.services import paystack


class FakePaystack:
    """Stands in for the Paystack API. Tests choose each transaction's outcome."""

    def __init__(self):
        self.txs: dict[str, dict] = {}
        self.refunds: list[dict] = []
        self.fail_init = False

    async def initialize(self, *, email, amount, reference, callback_url, currency, metadata, channels=None):
        if self.fail_init:
            raise paystack.PaystackError("boom")
        self.txs[reference] = {"status": "abandoned", "amount": amount, "currency": currency, "id": abs(hash(reference)) % 10**9}
        return {"authorization_url": f"https://checkout.paystack.test/{reference}", "access_code": "AC_" + reference[-6:]}

    async def verify(self, reference):
        if reference not in self.txs:
            raise paystack.PaystackError("Transaction reference not found")
        t = self.txs[reference]
        return {"status": t["status"], "amount": t["amount"], "currency": t["currency"], "id": t["id"], "channel": "card", "gateway_response": "ok"}

    async def refund(self, *, transaction, amount, currency, note=""):
        self.refunds.append({"transaction": transaction, "amount": amount})
        return {"id": 987654, "status": "pending"}

    def pay(self, reference, **over):
        self.txs[reference].update({"status": "success", **over})


@pytest.fixture
async def db():
    test_url = os.environ.get("POSTGRES_TEST_DATABASE_URL")
    if test_url:
        import asyncpg

        from app.postgres_store import PostgresDatabase

        dsn = Settings(database_url=test_url).async_database_url
        database_name = unquote(urlsplit(dsn).path.lstrip("/"))
        if not database_name.endswith("_test"):
            pytest.fail("POSTGRES_TEST_DATABASE_URL must point to a dedicated database ending in _test")
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4, timeout=8)
        d = PostgresDatabase(pool)
        try:
            await d.initialize()
            await database.ensure_indexes(d)
            async with pool.acquire() as conn:
                await conn.execute("TRUNCATE TABLE app_documents")
            database.set_db(d)
            utils.set_clock(None, None)
            yield d
        finally:
            database.set_db(None)
            await pool.close()
        return

    d = AsyncMongoMockClient()["nlh_test"]
    database.set_db(d)
    await database.ensure_indexes(d)
    utils.set_clock(None, None)
    try:
        yield d
    finally:
        database.set_db(None)


@pytest.fixture
def gateway():
    g = FakePaystack()
    paystack.set_client(g)
    yield g
    paystack.set_client(None)


@pytest.fixture
async def client(db, gateway):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def make_user(db, role, email=None, password="Passw0rd!long", **kw):
    email = email or f"{role}@example.com"
    doc = {"_id": utils.new_id(), "name": role.replace("_", " ").title(), "email": email, "role": role,
           "password_hash": hash_password(password), "is_active": True, "token_version": 0, "created_at": utils.utcnow(), **kw}
    await db.users.insert_one(doc)
    return doc


async def login(client, email, password="Passw0rd!long", super_admin=False):
    path = "/api/v1/auth/super-admin/login" if super_admin else "/api/v1/auth/login"
    r = await client.post(path, json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
async def super_h(client, db):
    await make_user(db, "super_admin")
    return await login(client, "super_admin@example.com", super_admin=True)


@pytest.fixture
async def admin_h(client, db):
    await make_user(db, "hotel_admin")
    return await login(client, "hotel_admin@example.com")


@pytest.fixture
async def manager_h(client, db):
    await make_user(db, "hotel_manager")
    return await login(client, "hotel_manager@example.com")


@pytest.fixture
async def recep_h(client, db):
    await make_user(db, "receptionist")
    return await login(client, "receptionist@example.com")


@pytest.fixture
async def hotel(client, admin_h):
    """A small configured hotel: 2 categories, 3 + 1 rooms, sample prices (GHS 500 / 900 per night)."""
    c1 = (await client.post("/api/v1/room-categories", headers=admin_h, json={"name": "Standard", "default_rate_minor": 50000, "max_occupancy": 2, "status": "published", "is_sample": True})).json()
    c2 = (await client.post("/api/v1/room-categories", headers=admin_h, json={"name": "Executive", "default_rate_minor": 90000, "max_occupancy": 3, "status": "published", "included_guests": 2, "extra_guest_fee_minor": 10000})).json()
    r = await client.post("/api/v1/rooms/bulk", headers=admin_h, json={"category_id": c1["id"], "prefix": "10", "start": 1, "end": 3})
    assert r.status_code == 201, r.text
    await client.post("/api/v1/rooms", headers=admin_h, json={"number": "201", "category_id": c2["id"]})
    rooms = {x["number"]: x for x in (await client.get("/api/v1/rooms", headers=admin_h)).json()}
    return {"std": c1, "exe": c2, "rooms": rooms}


def future(days):
    return (utils.today() + timedelta(days=days)).isoformat()


def stay(hotel, qty=1, cat="std", d_in=10, d_out=12, **kw):
    return {"check_in": future(d_in), "check_out": future(d_out), "adults": 2, "children": 0,
            "selections": [{"category_id": hotel[cat]["id"], "quantity": qty}], **kw}


def guest(email="ama@example.com"):
    return {"name": "Ama Mensah", "email": email, "phone": "+233200000000", "country": "Ghana"}


def sign(body: dict):
    raw = json.dumps(body).encode()
    return raw, hmac.new(b"sk_test_unit_secret", raw, hashlib.sha512).hexdigest()
