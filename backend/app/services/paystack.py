"""Paystack client (https://paystack.com/docs/). Amounts are in the subunit (pesewas for GHS)."""
from __future__ import annotations

import hashlib
import hmac

import httpx

from ..config import get_config


class PaystackError(Exception):
    pass


class PaystackNotConfigured(PaystackError):
    pass


class PaystackUncertainError(PaystackError):
    pass


class PaystackClient:
    def __init__(self, secret: str, base_url: str):
        self.secret, self.base = secret, base_url.rstrip("/")

    async def _req(self, method: str, path: str, **kw) -> dict:
        if not self.secret:
            raise PaystackNotConfigured("Paystack is not configured")
        try:
            async with httpx.AsyncClient(timeout=25) as c:
                r = await c.request(method, f"{self.base}{path}", headers={"Authorization": f"Bearer {self.secret}"}, **kw)
        except Exception as e:
            raise PaystackUncertainError(f"Could not reach Paystack: {type(e).__name__}")
        try:
            data = r.json()
        except Exception as e:
            raise PaystackUncertainError(f"Paystack returned an invalid response: {type(e).__name__}")
        if not isinstance(data, dict):
            raise PaystackUncertainError("Paystack returned an invalid response")
        if r.status_code >= 500:
            raise PaystackUncertainError(f"Paystack returned server error {r.status_code}")
        if r.status_code >= 400 or not data.get("status"):
            raise PaystackError(data.get("message") or f"Paystack error {r.status_code}")
        if not isinstance(data.get("data"), dict):
            raise PaystackUncertainError("Paystack returned an invalid response")
        return data["data"]

    async def initialize(self, *, email: str, amount: int, reference: str, callback_url: str,
                         currency: str, metadata: dict, channels: list[str] | None = None) -> dict:
        body = {"email": email, "amount": amount, "reference": reference, "callback_url": callback_url,
                "currency": currency, "metadata": metadata}
        if channels:
            body["channels"] = channels
        return await self._req("POST", "/transaction/initialize", json=body)

    async def verify(self, reference: str) -> dict:
        return await self._req("GET", f"/transaction/verify/{reference}")

    async def refund(self, *, transaction: str, amount: int, currency: str, note: str = "") -> dict:
        body = {"transaction": transaction, "amount": amount, "currency": currency}
        if note:
            body["merchant_note"] = note
        return await self._req("POST", "/refund", json=body)


_client: PaystackClient | None = None


def get_client() -> PaystackClient:
    global _client
    if _client is None:
        cfg = get_config()
        _client = PaystackClient(cfg.paystack_secret_key, cfg.paystack_base_url)
    return _client


def set_client(c) -> None:  # tests inject a fake gateway
    global _client
    _client = c


def verify_signature(secret: str, body: bytes, signature: str | None) -> bool:
    """Paystack signs webhooks with HMAC-SHA512 of the raw body using the secret key."""
    if not secret or not signature:
        return False
    digest = hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(digest, signature)
