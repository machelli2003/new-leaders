import pytest
from pydantic import ValidationError

from app.config import Settings, get_config


def test_app_environment_is_required(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("JWT_SECRET", "test-secret-is-explicitly-provided")
    get_config.cache_clear()
    try:
        with pytest.raises(ValidationError, match="app_env"):
            get_config()
    finally:
        get_config.cache_clear()


def test_jwt_secret_is_required(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ValidationError, match="jwt_secret"):
        Settings(_env_file=None)


def test_empty_jwt_secret_fails_with_configuration_error(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("JWT_SECRET", "")
    get_config.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="JWT_SECRET must be set"):
            get_config()
    finally:
        get_config.cache_clear()


def test_production_rejects_non_https_public_url(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "production-test-secret-that-is-long-enough")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("MONGODB_URL", "mongodb+srv://user:pass@cluster.example.test/db")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://hotel.example.test")
    monkeypatch.setenv("CORS_ORIGINS", "https://hotel.example.test")
    get_config.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="PUBLIC_BASE_URL must be an absolute HTTPS URL"):
            get_config()
    finally:
        get_config.cache_clear()


def test_production_requires_redis_url(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "production-test-secret-that-is-long-enough")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("MONGODB_URL", "mongodb+srv://user:pass@cluster.example.test/db")
    monkeypatch.delenv("REDIS_URL", raising=False)
    get_config.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="REDIS_URL must point to a Redis service"):
            get_config()
    finally:
        get_config.cache_clear()
