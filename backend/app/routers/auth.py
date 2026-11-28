from __future__ import annotations

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr

from ..audit import audit
from ..config import get_config
from ..db import get_db
from ..permissions import ROLE_LABELS, effective_permissions
from ..security import (create_access_token, current_user, hash_password, hash_refresh, issue_refresh_token, login_limiter,
                        validate_password_strength, verify_password)
from ..utils import ser, utcnow
from datetime import timedelta

router = APIRouter(prefix="/auth", tags=["auth"])
COOKIE = "nlh_refresh"
MAX_FAILS, LOCK_MINUTES = 5, 15


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    otp: str | None = None


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


def public_user(u: dict) -> dict:
    d = ser(u)
    d["permissions"] = sorted(effective_permissions(u))
    d["role_label"] = ROLE_LABELS.get(u["role"], u["role"])
    d["mfa_enabled"] = bool(u.get("mfa_enabled"))
    d["mfa_required"] = get_config().app_env == "production" and u["role"] == "super_admin"
    return d


def _set_cookie(resp: Response, raw: str) -> None:
    cfg = get_config()
    resp.set_cookie(COOKIE, raw, max_age=cfg.refresh_token_days * 86400, httponly=True, secure=cfg.cookie_secure,
                    samesite="strict", path="/api/v1/auth")


async def _login(body: LoginIn, response: Response, super_admin: bool) -> dict:
    db = get_db()
    user = await db.users.find_one({"email": body.email.lower()})
    generic = HTTPException(401, "Invalid email or password")
    if not user or (user["role"] == "super_admin") != super_admin:
        await audit(None, "auth.login_failed", "user", None, note="invalid_credentials")
        raise generic
    now = utcnow()
    if user.get("locked_until") and user["locked_until"] > now:
        await audit(user, "auth.login_blocked", "user", user["_id"], note="account_locked")
        raise HTTPException(423, "Account temporarily locked after repeated failed attempts. Try again later.")
    if not user.get("is_active", True):
        await audit(user, "auth.login_blocked", "user", user["_id"], note="account_inactive")
        raise HTTPException(403, "This account has been deactivated")
    async def record_failure() -> None:
        fails = user.get("failed_attempts", 0) + 1
        upd = {"failed_attempts": fails}
        if fails >= MAX_FAILS:
            upd = {"failed_attempts": 0, "locked_until": now + timedelta(minutes=LOCK_MINUTES)}
        await db.users.update_one({"_id": user["_id"]}, {"$set": upd})
        await audit(user, "auth.login_failed", "user", user["_id"])

    if not verify_password(body.password, user["password_hash"]):
        await record_failure()
        raise generic
    if user.get("mfa_enabled"):
        if not body.otp:
            raise HTTPException(401, "mfa_required")
        if not pyotp.TOTP(user["mfa_secret"]).verify(body.otp, valid_window=1):
            await record_failure()
            raise HTTPException(401, "Invalid verification code")
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"failed_attempts": 0, "locked_until": None, "last_login_at": now}})
    if super_admin and get_config().app_env == "production" and not user.get("mfa_enabled"):
        await audit(user, "auth.mfa_enrollment_required", "user", user["_id"])
        return {
            "access_token": create_access_token(user, mfa_enrollment=True),
            "token_type": "bearer",
            "user": public_user(user),
            "mfa_enrollment_required": True,
        }
    raw = await issue_refresh_token(user["_id"])
    _set_cookie(response, raw)
    await audit(user, "auth.login", "user", user["_id"])
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": public_user(user),
            "mfa_enrollment_required": False}


@router.post("/login", dependencies=[Depends(login_limiter)])
async def login(body: LoginIn, response: Response):
    """Hotel staff login (Hotel Admin, Hotel Manager, Receptionist)."""
    return await _login(body, response, super_admin=False)


@router.post("/super-admin/login", dependencies=[Depends(login_limiter)])
async def super_admin_login(body: LoginIn, response: Response):
    return await _login(body, response, super_admin=True)


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    # CSRF defence: SameSite=Strict cookie + required custom header that cross-site forms cannot send
    if request.headers.get("x-requested-with") != "XMLHttpRequest":
        raise HTTPException(403, "Missing CSRF header")
    raw = request.cookies.get(COOKIE)
    if not raw:
        raise HTTPException(401, "No session")
    db = get_db()
    tok = await db.refresh_tokens.find_one_and_delete({"token_hash": hash_refresh(raw)})  # rotation: single use
    if not tok or tok["expires_at"] < utcnow():
        response.delete_cookie(COOKIE, path="/api/v1/auth")
        raise HTTPException(401, "Session expired")
    user = await db.users.find_one({"_id": tok["user_id"]})
    if not user or not user.get("is_active", True):
        raise HTTPException(401, "Account not available")
    _set_cookie(response, await issue_refresh_token(user["_id"]))
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": public_user(user)}


@router.post("/logout")
async def logout(request: Request, response: Response):
    raw = request.cookies.get(COOKIE)
    if raw:
        await get_db().refresh_tokens.delete_one({"token_hash": hash_refresh(raw)})
    response.delete_cookie(COOKIE, path="/api/v1/auth")
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(current_user)):
    return public_user(user)


@router.post("/change-password")
async def change_password(body: ChangePasswordIn, response: Response, user: dict = Depends(current_user)):
    if not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(400, "Current password is incorrect")
    validate_password_strength(body.new_password, user["email"])
    db = get_db()
    ver = user.get("token_version", 0) + 1
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"password_hash": hash_password(body.new_password), "must_change_password": False,
                                                              "token_version": ver, "updated_at": utcnow()}})
    await db.refresh_tokens.delete_many({"user_id": user["_id"]})
    user["token_version"] = ver
    _set_cookie(response, await issue_refresh_token(user["_id"]))
    await audit(user, "auth.change_password", "user", user["_id"])
    return {"access_token": create_access_token(user), "token_type": "bearer"}


# ---- optional TOTP multi-factor authentication ----
@router.post("/mfa/setup")
async def mfa_setup(user: dict = Depends(current_user)):
    secret = pyotp.random_base32()
    await get_db().users.update_one({"_id": user["_id"]}, {"$set": {"mfa_pending_secret": secret}})
    uri = pyotp.TOTP(secret).provisioning_uri(name=user["email"], issuer_name="New Leaders Hotel")
    return {"secret": secret, "otpauth_uri": uri}


class OtpIn(BaseModel):
    otp: str
    password: str | None = None


@router.post("/mfa/enable")
async def mfa_enable(body: OtpIn, response: Response, user: dict = Depends(current_user)):
    secret = user.get("mfa_pending_secret")
    if not secret or not pyotp.TOTP(secret).verify(body.otp, valid_window=1):
        raise HTTPException(400, "Invalid verification code")
    db = get_db()
    updates: dict[str, object] = {"mfa_enabled": True, "mfa_secret": secret}
    if user["role"] == "super_admin":
        user["token_version"] = user.get("token_version", 0) + 1
        updates["token_version"] = user["token_version"]
        await db.refresh_tokens.delete_many({"user_id": user["_id"]})
    await db.users.update_one({"_id": user["_id"]}, {"$set": updates, "$unset": {"mfa_pending_secret": ""}})
    await audit(user, "auth.mfa_enable", "user", user["_id"])
    if user["role"] == "super_admin":
        _set_cookie(response, await issue_refresh_token(user["_id"]))
        return {"ok": True, "access_token": create_access_token(user), "user": public_user({**user, "mfa_enabled": True})}
    return {"ok": True}


@router.post("/mfa/disable")
async def mfa_disable(body: OtpIn, user: dict = Depends(current_user)):
    if not user.get("mfa_enabled"):
        raise HTTPException(400, "MFA is not enabled")
    if not body.password or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(400, "Password is incorrect")
    if not pyotp.TOTP(user["mfa_secret"]).verify(body.otp, valid_window=1):
        raise HTTPException(400, "Invalid verification code")
    db = get_db()
    updates: dict[str, object] = {"mfa_enabled": False}
    if user["role"] == "super_admin":
        user["token_version"] = user.get("token_version", 0) + 1
        updates["token_version"] = user["token_version"]
        await db.refresh_tokens.delete_many({"user_id": user["_id"]})
    await db.users.update_one({"_id": user["_id"]}, {"$set": updates, "$unset": {"mfa_secret": ""}})
    await audit(user, "auth.mfa_disable", "user", user["_id"])
    return {"ok": True}
