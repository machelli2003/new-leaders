import pytest

from app.config import get_config


def test_empty_jwt_secret_fails_with_configuration_error(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("JWT_SECRET", "")
    get_config.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="JWT_SECRET must be set"):
            get_config()
    finally:
        get_config.cache_clear()
