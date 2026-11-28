"""Append-only audit log. There is intentionally no update/delete API for audit_logs.
In production also restrict the DB user so it cannot modify/delete this collection (see docs)."""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from .db import get_db
from .utils import new_id, utcnow

request_meta: ContextVar[dict] = ContextVar("request_meta", default={})
SECRET_FIELDS = {
    "password", "password_hash", "mfa_secret", "mfa_pending_secret", "token_hash",
    "password_reset_token", "reset_token", "secret", "otp", "access_token",
}


def scrub(o: Any) -> Any:
    if isinstance(o, dict):
        return {k: ("***" if k in SECRET_FIELDS else scrub(v)) for k, v in o.items() if not k.startswith("_")}
    if isinstance(o, list):
        return [scrub(i) for i in o]
    return o


async def audit(user: dict | None, action: str, entity: str, entity_id: str | None = None,
                before: Any = None, after: Any = None, note: str | None = None) -> None:
    meta = request_meta.get()
    await get_db().audit_logs.insert_one(
        {
            "_id": new_id(),
            "created_at": utcnow(),
            "actor_id": user["_id"] if user else None,
            "actor_name": user.get("name") if user else "system",
            "actor_role": user.get("role") if user else "system",
            "action": action,
            "entity": entity,
            "entity_id": entity_id,
            "before": scrub(before) if before is not None else None,
            "after": scrub(after) if after is not None else None,
            "note": note,
            "ip": meta.get("ip"),
            "user_agent": meta.get("ua"),
        }
    )
