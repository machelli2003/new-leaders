import os
import secrets

import pytest
from fastapi import HTTPException
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.requests import Request

from app.config import get_config
from app.security import RateLimiter, client_ip, set_rate_limit_redis


@pytest.fixture(autouse=True)
def clear_rate_limit_redis():
    set_rate_limit_redis(None)
    yield
    set_rate_limit_redis(None)


@pytest.fixture
def request_with_client_ip():
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [],
            "client": ("203.0.113.8", 12345),
            "server": ("testserver", 80),
        }
    )


class FakeRedis:
    def __init__(self, result):
        self.result = result
        self.call = None

    async def eval(self, *args):
        self.call = args
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


async def test_redis_rate_limit_uses_hmac_ip_key_and_accepts_request(
    monkeypatch, request_with_client_ip
):
    monkeypatch.setattr(get_config(), "rate_limit_enabled", True)
    redis_client = FakeRedis([1, 0])
    set_rate_limit_redis(redis_client)

    await RateLimiter(2, 60, "test")(request_with_client_ip)

    key = redis_client.call[2]
    assert key.startswith("nlh:rate-limit:test:")
    assert "203.0.113.8" not in key
    assert redis_client.call[3:5] == (60000, 2)


def test_forwarded_ip_is_ignored_for_untrusted_peer(monkeypatch, request_with_client_ip):
    monkeypatch.setattr(get_config(), "trust_proxy", True)
    monkeypatch.setattr(get_config(), "trusted_proxy_cidrs", "127.0.0.1/32")
    request_with_client_ip.scope["headers"] = [(b"x-forwarded-for", b"198.51.100.50")]

    assert client_ip(request_with_client_ip) == "203.0.113.8"


def test_forwarded_ip_is_used_for_trusted_peer(monkeypatch, request_with_client_ip):
    monkeypatch.setattr(get_config(), "trust_proxy", True)
    monkeypatch.setattr(get_config(), "trusted_proxy_cidrs", "203.0.113.0/24,192.0.2.0/24")
    request_with_client_ip.scope["client"] = ("203.0.113.8", 12345)
    request_with_client_ip.scope["headers"] = [
        (b"x-forwarded-for", b"198.51.100.99, 198.51.100.50, 192.0.2.10")
    ]

    assert client_ip(request_with_client_ip) == "198.51.100.50"


async def test_redis_rate_limit_returns_retry_after_when_limited(
    monkeypatch, request_with_client_ip
):
    monkeypatch.setattr(get_config(), "rate_limit_enabled", True)
    set_rate_limit_redis(FakeRedis([0, 1500]))

    with pytest.raises(HTTPException) as exc:
        await RateLimiter(1, 60, "test")(request_with_client_ip)

    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"] == "2"


async def test_redis_failure_fails_closed(monkeypatch, request_with_client_ip):
    monkeypatch.setattr(get_config(), "rate_limit_enabled", True)
    set_rate_limit_redis(FakeRedis(RedisError("Redis unavailable")))

    with pytest.raises(HTTPException) as exc:
        await RateLimiter(1, 60, "test")(request_with_client_ip)

    assert exc.value.status_code == 503


async def test_production_without_redis_fails_closed(monkeypatch, request_with_client_ip):
    monkeypatch.setattr(get_config(), "app_env", "production")
    monkeypatch.setattr(get_config(), "rate_limit_enabled", True)

    with pytest.raises(HTTPException) as exc:
        await RateLimiter(1, 60, "test")(request_with_client_ip)

    assert exc.value.status_code == 503


@pytest.mark.skipif(not os.getenv("TEST_REDIS_URL"), reason="TEST_REDIS_URL is not configured")
async def test_separate_limiters_share_the_redis_counter(request_with_client_ip):
    first_client = Redis.from_url(os.environ["TEST_REDIS_URL"], decode_responses=True)
    second_client = Redis.from_url(os.environ["TEST_REDIS_URL"], decode_responses=True)
    limiter = RateLimiter(1, 60, f"integration-{secrets.token_hex(8)}")
    key = limiter._redis_key(request_with_client_ip)
    try:
        await first_client.ping()
        await second_client.ping()
        set_rate_limit_redis(first_client)
        await limiter(request_with_client_ip)
        set_rate_limit_redis(second_client)
        with pytest.raises(HTTPException) as exc:
            await RateLimiter(1, 60, limiter.name)(request_with_client_ip)
        assert exc.value.status_code == 429
    finally:
        set_rate_limit_redis(None)
        await first_client.delete(key)
        await first_client.aclose()
        await second_client.aclose()
