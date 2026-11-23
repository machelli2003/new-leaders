from __future__ import annotations

import base64
import hashlib
import re
import secrets
import time
from collections import defaultdict, deque
from datetime import timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_config
from .db import get_db
from .permissions import effective_permissions
from .utils import utcnow

bearer = HTTPBearer(auto_error=False)


# ---------- passwords ----------
def _prep(pw: str) -> bytes:
    # pre-hash so bcrypt's 72-byte limit never truncates/raises
    return base64.b64encode(hashlib.sha256(pw.encode()).digest())


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(_prep(pw), bcrypt.gensalt(get_config().bcrypt_rounds)).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prep(pw), hashed.encode())
    except Exception:
        return False


def validate_password_strength(pw: str, email: str = "") -> None:
    if len(pw) < 10:
        raise HTTPException(422, "Password must be at least 10 characters")
    if not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        raise HTTPException(422, "Password must contain letters and numbers")
    if email and pw.lower() == email.lower():
        raise HTTPException(422, "Password must not equal your email")


# ---------- tokens ----------
def create_access_token(user: dict, typ: str = "access") -> str:
    cfg = get_config()
    now = utcnow()
    payload = {
        "sub": user["_id"],
        "typ": typ,
        "ver": user.get("token_version", 0),
        "iat": int(time.time()),
        "exp": int(time.time()) + cfg.access_token_minutes * 60,
    }
    return jwt.encode(payload, cfg.jwt_secret, algorithm="HS256")


def decode_token(token: str, typ: str = "access") -> dict:
    try:
        data = jwt.decode(token, get_config().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")
    if data.get("typ") != typ:
        raise HTTPException(401, "Invalid token type")
    return data


def hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def issue_refresh_token(user_id: str, kind: str = "staff") -> str:
    cfg = get_config()
    raw = secrets.token_urlsafe(48)
    await get_db().refresh_tokens.insert_one(
        {
            "token_hash": hash_refresh(raw),
            "user_id": user_id,
            "kind": kind,
            "created_at": utcnow(),
            "expires_at": utcnow() + timedelta(days=cfg.refresh_token_days),
        }
    )
    return raw


# ---------- current user ----------
async def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if not creds:
        raise HTTPException(401, "Not authenticated")
    data = decode_token(creds.credentials)
    user = await get_db().users.find_one({"_id": data["sub"]})
    if not user or not user.get("is_active", True):
        raise HTTPException(401, "Account not found or deactivated")
    if user.get("token_version", 0) != data.get("ver", 0):
        raise HTTPException(401, "Session expired, please sign in again")
    user["_perms"] = effective_permissions(user)
    return user


async def optional_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict | None:
    if not creds:
        return None
    try:
        return await current_user(creds)
    except HTTPException:
        return None


def require(*perms: str, any_of: bool = False):
    """Server-side permission enforcement. Frontend hiding is cosmetic only."""

    async def dep(user: dict = Depends(current_user)) -> dict:
        have = user["_perms"]
        ok = any(p in have for p in perms) if any_of else all(p in have for p in perms)
        if not ok:
            raise HTTPException(403, "You do not have permission to perform this action")
        return user

    return dep


def require_role(*roles: str):
    async def dep(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(403, "Not allowed for your role")
        return user

    return dep


# ---------- rate limiting (in-memory, per process; use a shared store when running many workers) ----------
def client_ip(request: Request) -> str:
    if get_config().trust_proxy:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int, name: str = ""):
        self.limit, self.window, self.name = limit, window_seconds, name
        self.hits: dict[str, deque] = defaultdict(deque)

    async def __call__(self, request: Request) -> None:
        if not get_config().rate_limit_enabled:
            return
        key = f"{self.name}:{client_ip(request)}"
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            raise HTTPException(429, "Too many requests. Please slow down and try again shortly.")
        q.append(now)

    def reset(self) -> None:
        self.hits.clear()


login_limiter = RateLimiter(10, 60, "login")
public_limiter = RateLimiter(60, 60, "public")
booking_limiter = RateLimiter(15, 60, "booking")
