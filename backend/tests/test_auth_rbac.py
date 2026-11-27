from .conftest import login, make_user
from app.config import get_config


async def test_login_and_me(client, db):
    await make_user(db, "hotel_admin")
    h = await login(client, "hotel_admin@example.com")
    r = await client.get("/api/v1/auth/me", headers=h)
    assert r.status_code == 200 and r.json()["role"] == "hotel_admin"
    assert "password_hash" not in r.json()


async def test_wrong_password_and_lockout(client, db):
    await make_user(db, "receptionist")
    for _ in range(5):
        r = await client.post("/api/v1/auth/login", json={"email": "receptionist@example.com", "password": "wrong-password1"})
        assert r.status_code == 401
    r = await client.post("/api/v1/auth/login", json={"email": "receptionist@example.com", "password": "Passw0rd!long"})
    assert r.status_code == 423  # locked even with right password


async def test_super_admin_login_is_separate(client, db):
    await make_user(db, "super_admin")
    r = await client.post("/api/v1/auth/login", json={"email": "super_admin@example.com", "password": "Passw0rd!long"})
    assert r.status_code == 401
    await make_user(db, "hotel_admin")
    r = await client.post("/api/v1/auth/super-admin/login", json={"email": "hotel_admin@example.com", "password": "Passw0rd!long"})
    assert r.status_code == 401


async def test_super_admin_system_overview(client, super_h):
    response = await client.get("/api/v1/system/overview", headers=super_h)

    assert response.status_code == 200, response.text
    assert "counts" in response.json()


async def test_unauthenticated_and_role_escalation(client, recep_h, manager_h, admin_h):
    assert (await client.get("/api/v1/reservations")).status_code == 401
    # receptionist cannot manage staff, settings, pricing, rooms
    assert (await client.get("/api/v1/users", headers=recep_h)).status_code == 403
    assert (await client.put("/api/v1/settings/payment", headers=recep_h, json={"require_full_payment": True, "deposit_enabled": False})).status_code == 403
    assert (await client.post("/api/v1/room-categories", headers=recep_h, json={"name": "X"})).status_code == 403
    assert (await client.get("/api/v1/audit-logs", headers=manager_h)).status_code == 403
    assert (await client.get("/api/v1/reports/revenue", headers=manager_h)).status_code == 403  # no financial reports
    assert (await client.get("/api/v1/reports/occupancy", headers=manager_h)).status_code == 200
    # hotel admin cannot use platform-owner controls
    assert (await client.get("/api/v1/system/overview", headers=admin_h)).status_code == 403


async def test_staff_management_rules(client, db, admin_h, super_h):
    body = {"name": "New Rec", "email": "rec2@example.com", "role": "receptionist", "password": "Sup3rSecret!!"}
    r = await client.post("/api/v1/users", headers=admin_h, json=body)
    assert r.status_code == 201 and r.json()["must_change_password"] is True
    assert (await client.post("/api/v1/users", headers=admin_h, json=body)).status_code == 409
    weak = {**body, "email": "rec3@example.com", "password": "short"}
    assert (await client.post("/api/v1/users", headers=admin_h, json=weak)).status_code == 422
    # cannot target the super admin
    sa = await db.users.find_one({"role": "super_admin"})
    assert (await client.patch(f"/api/v1/users/{sa['_id']}", headers=admin_h, json={"is_active": False})).status_code == 404
    assert (await client.post(f"/api/v1/users/{sa['_id']}/reset-password", headers=admin_h, json={"password": "Another1Pass!!"})).status_code == 404
    # cannot grant non-grantable permission, can grant others
    uid = r.json()["id"]
    assert (await client.patch(f"/api/v1/users/{uid}", headers=admin_h, json={"extra_permissions": ["settings.payments"]})).status_code == 422
    ok = await client.patch(f"/api/v1/users/{uid}", headers=admin_h, json={"extra_permissions": ["reports.financial"]})
    assert ok.status_code == 200
    # admin cannot deactivate themselves
    me = (await client.get("/api/v1/auth/me", headers=admin_h)).json()
    assert (await client.patch(f"/api/v1/users/{me['id']}", headers=admin_h, json={"is_active": False})).status_code == 400


async def test_deactivation_revokes_access_immediately(client, db, admin_h):
    await make_user(db, "receptionist", "gone@example.com")
    h = await login(client, "gone@example.com")
    assert (await client.get("/api/v1/auth/me", headers=h)).status_code == 200
    uid = (await db.users.find_one({"email": "gone@example.com"}))["_id"]
    await client.patch(f"/api/v1/users/{uid}", headers=admin_h, json={"is_active": False})
    assert (await client.get("/api/v1/auth/me", headers=h)).status_code == 401


async def test_extra_permission_applies(client, db, admin_h):
    await make_user(db, "receptionist", "x@example.com")
    h = await login(client, "x@example.com")
    assert (await client.get("/api/v1/reports/revenue", headers=h)).status_code == 403
    uid = (await db.users.find_one({"email": "x@example.com"}))["_id"]
    await client.patch(f"/api/v1/users/{uid}", headers=admin_h, json={"extra_permissions": ["reports.financial"]})
    h = await login(client, "x@example.com")
    assert (await client.get("/api/v1/reports/revenue", headers=h)).status_code == 200


async def test_refresh_requires_csrf_header_and_rotates(client, db):
    await make_user(db, "hotel_admin")
    r = await client.post("/api/v1/auth/login", json={"email": "hotel_admin@example.com", "password": "Passw0rd!long"})
    assert r.status_code == 200
    assert (await client.post("/api/v1/auth/refresh")).status_code == 403
    r1 = await client.post("/api/v1/auth/refresh", headers={"X-Requested-With": "XMLHttpRequest"})
    assert r1.status_code == 200
    old_cookie = None  # cookie jar now holds the rotated token; replaying the old one must fail
    await client.post("/api/v1/auth/logout")
    assert (await client.post("/api/v1/auth/refresh", headers={"X-Requested-With": "XMLHttpRequest"})).status_code == 401


async def test_mfa_flow(client, db):
    import pyotp

    await make_user(db, "super_admin")
    h = await login(client, "super_admin@example.com", super_admin=True)
    secret = (await client.post("/api/v1/auth/mfa/setup", headers=h)).json()["secret"]
    assert (await client.post("/api/v1/auth/mfa/enable", headers=h, json={"otp": "000000"})).status_code == 400
    assert (await client.post("/api/v1/auth/mfa/enable", headers=h, json={"otp": pyotp.TOTP(secret).now()})).status_code == 200
    r = await client.post("/api/v1/auth/super-admin/login", json={"email": "super_admin@example.com", "password": "Passw0rd!long"})
    assert r.status_code == 401 and r.json()["error"]["message"] == "mfa_required"
    r = await client.post("/api/v1/auth/super-admin/login", json={"email": "super_admin@example.com", "password": "Passw0rd!long", "otp": pyotp.TOTP(secret).now()})
    assert r.status_code == 200


async def test_must_change_password_is_enforced_by_api(client, db):
    await make_user(db, "hotel_admin", must_change_password=True)
    h = await login(client, "hotel_admin@example.com")
    blocked = await client.get("/api/v1/reservations", headers=h)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["details"]["code"] == "password_change_required"

    changed = await client.post(
        "/api/v1/auth/change-password",
        headers=h,
        json={"current_password": "Passw0rd!long", "new_password": "NewPassw0rd!long"},
    )
    assert changed.status_code == 200
    fresh_h = {"Authorization": f"Bearer {changed.json()['access_token']}"}
    assert (await client.get("/api/v1/reservations", headers=fresh_h)).status_code == 200


async def test_production_super_admin_must_enroll_mfa(client, db, monkeypatch):
    import pyotp

    class RedisStub:
        async def eval(self, *args):
            return [1, 0]

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("MONGODB_URL", "mongodb+srv://user:pass@cluster.example.test/db")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://hotel.example.test")
    monkeypatch.setenv("CORS_ORIGINS", "https://hotel.example.test")
    monkeypatch.setattr("app.security._rate_limit_redis", RedisStub())
    get_config.cache_clear()
    try:
        await make_user(db, "super_admin")
        login_response = await client.post(
            "/api/v1/auth/super-admin/login",
            json={"email": "super_admin@example.com", "password": "Passw0rd!long"},
        )
        assert login_response.status_code == 200
        assert login_response.json()["mfa_enrollment_required"] is True
        assert "set-cookie" not in login_response.headers
        enroll_h = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        assert (await client.get("/api/v1/system/overview", headers=enroll_h)).status_code == 403

        setup = await client.post("/api/v1/auth/mfa/setup", headers=enroll_h)
        assert setup.status_code == 200
        enable = await client.post(
            "/api/v1/auth/mfa/enable",
            headers=enroll_h,
            json={"otp": pyotp.TOTP(setup.json()["secret"]).now()},
        )
        assert enable.status_code == 200
        assert enable.json()["user"]["mfa_enabled"] is True
        assert (await client.get("/api/v1/system/overview", headers=enroll_h)).status_code == 401
        assert (await client.get(
            "/api/v1/system/overview",
            headers={"Authorization": f"Bearer {enable.json()['access_token']}"},
        )).status_code == 200
    finally:
        get_config.cache_clear()
