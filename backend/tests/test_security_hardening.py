import re

import pytest
from fastapi import HTTPException

from app.routers.common import literal_search_regex
from app.security import hash_password, validate_password_strength
from app.utils import new_id, utcnow


def test_search_regex_treats_metacharacters_as_literals_and_limits_length():
    assert literal_search_regex(".*") == {"$regex": r"\.\*", "$options": "i"}
    with pytest.raises(HTTPException) as exc:
        literal_search_regex("x" * 101)
    assert exc.value.status_code == 422


def test_password_policy_rejects_short_common_repetitive_and_oversized_passwords():
    for password in ("Short1!", "password1234", "aaaaaaaaaaaa1!", "A" * 129):
        with pytest.raises(HTTPException):
            validate_password_strength(password)

    validate_password_strength("New-secure-Password-2026!")


async def test_guest_password_reset_is_generic_expiring_and_single_use(client, db, monkeypatch):
    emails = []

    async def fake_send_email(_db, to, subject, body_html, kind, reservation_id=None):
        emails.append({"to": to, "subject": subject, "body": body_html, "kind": kind})
        return "sent"

    monkeypatch.setattr("app.routers.bookings.send_email", fake_send_email)
    path = "/api/v1/bookings/account/password-reset/request"
    expected = {"message": "If an account exists for that email, reset instructions will be sent."}
    unknown = await client.post(path, json={"email": "unknown@example.com"})
    assert unknown.status_code == 202 and unknown.json() == expected
    assert not emails

    guest = {
        "_id": new_id(),
        "name": "Guest",
        "email": "guest@example.com",
        "phone": "+233200000000",
        "country": "Ghana",
        "password_hash": hash_password("Guest-pass-123"),
        "has_account": True,
        "email_verified": True,
        "token_version": 0,
    }
    await db.guests.insert_one(guest)
    old_login = await client.post(
        "/api/v1/bookings/account/login",
        json={"email": guest["email"], "password": "Guest-pass-123"},
    )
    assert old_login.status_code == 200

    requested = await client.post(path, json={"email": guest["email"]})
    assert requested.status_code == 202 and requested.json() == expected
    assert len(emails) == 1
    token_match = re.search(r"#token=([A-Za-z0-9_-]+)", emails[0]["body"])
    assert token_match
    token = token_match.group(1)

    confirm_path = "/api/v1/bookings/account/password-reset/confirm"
    await db.account_password_resets.update_one(
        {"guest_id": guest["_id"]},
        {"$set": {"expires_at": utcnow()}},
    )
    expired = await client.post(
        confirm_path,
        json={"token": token, "password": "New-secure-Password-2026!"},
    )
    assert expired.status_code == 400
    requested_again = await client.post(path, json={"email": guest["email"]})
    assert requested_again.status_code == 202 and requested_again.json() == expected
    token_match = re.search(r"#token=([A-Za-z0-9_-]+)", emails[-1]["body"])
    assert token_match
    token = token_match.group(1)

    weak = await client.post(
        confirm_path,
        json={"token": token, "password": "Short1!"},
    )
    assert weak.status_code == 422
    assert await db.account_password_resets.count_documents({"guest_id": guest["_id"]}) == 1

    reset = await client.post(
        confirm_path,
        json={"token": token, "password": "New-secure-Password-2026!"},
    )
    assert reset.status_code == 200
    assert (await client.post(
        confirm_path,
        json={"token": token, "password": "Another-secure-Password-2026!"},
    )).status_code == 400
    assert (await client.get(
        "/api/v1/bookings/account/bookings",
        headers={"Authorization": f"Bearer {old_login.json()['access_token']}"},
    )).status_code == 401
    new_login = await client.post(
        "/api/v1/bookings/account/login",
        json={"email": guest["email"], "password": "New-secure-Password-2026!"},
    )
    assert new_login.status_code == 200


async def test_login_and_authorization_failures_are_audited(client, db, recep_h):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com", "password": "UnknownPassword123!"},
    )
    assert login_response.status_code == 401

    denied = await client.get("/api/v1/users", headers=recep_h)
    assert denied.status_code == 403
    logs = await db.audit_logs.find(
        {"action": {"$in": ["auth.login_failed", "auth.authorization_denied"]}}
    ).to_list(None)
    assert {log["action"] for log in logs} == {"auth.login_failed", "auth.authorization_denied"}
    assert any(log["entity_id"] == "/api/v1/users" for log in logs)
    assert "unknown@example.com" not in repr(logs)


async def test_regex_search_does_not_treat_user_input_as_a_pattern(client, hotel, admin_h):
    response = await client.get("/api/v1/rooms", params={"q": ".*"}, headers=admin_h)
    assert response.status_code == 200
    assert response.json() == []
