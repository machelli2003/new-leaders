from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from ..audit import audit
from ..db import get_db
from ..permissions import HOTEL_ROLES, NON_GRANTABLE, PERMISSIONS, ROLE_DEFAULTS, ROLE_LABELS
from ..security import current_user, hash_password, require, validate_password_strength
from ..utils import new_id, paginate, ser, utcnow

router = APIRouter(prefix="/users", tags=["staff"])
Role = Literal["hotel_admin", "hotel_manager", "receptionist"]


class StaffCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    role: Role
    password: str
    extra_permissions: list[str] = []


class StaffUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    role: Role | None = None
    is_active: bool | None = None
    extra_permissions: list[str] | None = None


def _check_extras(extras: list[str], actor: dict) -> list[str]:
    bad = [p for p in extras if p not in PERMISSIONS or p in NON_GRANTABLE]
    if bad:
        raise HTTPException(422, f"These permissions cannot be granted: {', '.join(bad)}")
    if actor["role"] != "super_admin":
        over = [p for p in extras if p not in actor["_perms"]]
        if over:
            raise HTTPException(403, "You cannot grant permissions you do not hold")
    return sorted(set(extras))


async def _staff_or_404(uid: str) -> dict:
    u = await get_db().users.find_one({"_id": uid})
    # Super Admin accounts are invisible/untouchable from hotel staff management
    if not u or u["role"] == "super_admin":
        raise HTTPException(404, "User not found")
    return u


@router.get("/permissions")
async def matrix(user: dict = Depends(require("staff.manage"))):
    return {"permissions": PERMISSIONS, "non_grantable": sorted(NON_GRANTABLE),
            "roles": {r: {"label": ROLE_LABELS[r], "permissions": sorted(ROLE_DEFAULTS[r])} for r in HOTEL_ROLES}}


@router.get("")
async def list_staff(page: int = 1, page_size: int = 50, user: dict = Depends(require("staff.manage"))):
    return await paginate(get_db().users, {"role": {"$in": list(HOTEL_ROLES)}}, [("name", 1)], page, page_size)


@router.post("", status_code=201)
async def create_staff(body: StaffCreate, user: dict = Depends(require("staff.manage"))):
    db = get_db()
    validate_password_strength(body.password, body.email)
    if await db.users.find_one({"email": body.email.lower()}):
        raise HTTPException(409, "A user with this email already exists")
    doc = {"_id": new_id(), "name": body.name.strip(), "email": body.email.lower(), "role": body.role,
           "password_hash": hash_password(body.password), "is_active": True, "must_change_password": True,
           "extra_permissions": _check_extras(body.extra_permissions, user), "token_version": 0,
           "created_by": user["_id"], "created_at": utcnow(), "updated_at": utcnow()}
    await db.users.insert_one(doc)
    await audit(user, "staff.create", "user", doc["_id"], after={"email": doc["email"], "role": doc["role"]})
    return ser(doc)


@router.patch("/{uid}")
async def update_staff(uid: str, body: StaffUpdate, user: dict = Depends(require("staff.manage"))):
    db = get_db()
    target = await _staff_or_404(uid)
    patch = body.model_dump(exclude_unset=True)
    if target["_id"] == user["_id"] and (patch.get("is_active") is False or ("role" in patch and patch["role"] != target["role"])):
        raise HTTPException(400, "You cannot deactivate or change the role of your own account")
    if "extra_permissions" in patch:
        patch["extra_permissions"] = _check_extras(patch["extra_permissions"], user)
    if patch.get("is_active") is False or "role" in patch or "extra_permissions" in patch:
        patch["token_version"] = target.get("token_version", 0) + 1  # force re-login so changes apply immediately
    patch["updated_at"] = utcnow()
    await db.users.update_one({"_id": uid}, {"$set": patch})
    if "token_version" in patch:
        await db.refresh_tokens.delete_many({"user_id": uid})
    after = await db.users.find_one({"_id": uid})
    await audit(user, "staff.update", "user", uid, before={"role": target["role"], "is_active": target.get("is_active"), "extra": target.get("extra_permissions")},
                after={"role": after["role"], "is_active": after.get("is_active"), "extra": after.get("extra_permissions")})
    return ser(after)


class ResetPw(BaseModel):
    password: str


@router.post("/{uid}/reset-password")
async def reset_password(uid: str, body: ResetPw, user: dict = Depends(require("staff.manage"))):
    db = get_db()
    target = await _staff_or_404(uid)
    validate_password_strength(body.password, target["email"])
    await db.users.update_one({"_id": uid}, {"$set": {"password_hash": hash_password(body.password), "must_change_password": True,
                                                      "token_version": target.get("token_version", 0) + 1, "failed_attempts": 0, "locked_until": None}})
    await db.refresh_tokens.delete_many({"user_id": uid})
    await audit(user, "staff.reset_password", "user", uid)
    return {"ok": True}
