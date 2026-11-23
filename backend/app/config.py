from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"  # development | test | production
    database_url: str = "postgresql://postgres:postgres@localhost:5432/new_leaders_hotel"

    jwt_secret: str = "dev-only-change-me-dev-only-change-me"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    bcrypt_rounds: int = 12
    cookie_secure: bool = False
    trust_proxy: bool = False
    rate_limit_enabled: bool = True

    cors_origins: str = "http://localhost:5173"
    public_base_url: str = "http://localhost:5173"  # frontend URL (Paystack callback, email links)

    # Paystack (secret stays on the backend only)
    paystack_secret_key: str = ""
    paystack_base_url: str = "https://api.paystack.co"

    # Email (Resend). Leave blank to log emails as "skipped".
    resend_api_key: str = ""
    email_from: str = "New Leaders Hotel <no-reply@example.com>"

    # Storage
    storage_backend: str = "local"  # local | s3
    local_upload_dir: str = "uploads"
    local_media_url: str = "/media-files"
    s3_bucket: str = ""
    s3_region: str = "auto"
    s3_endpoint_url: str = ""  # e.g. https://<account>.r2.cloudflarestorage.com
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_public_base_url: str = ""  # public CDN/base URL for stored objects
    max_upload_mb: int = 8

    run_scheduler: bool = True
    serve_frontend: bool = False
    frontend_dist: str = "../frontend/dist"
    sentry_dsn: str = ""

    # Optional bootstrap of the platform owner account on first start
    super_admin_email: str = ""
    super_admin_password: str = ""
    super_admin_name: str = "Machellix"

    @property
    def async_database_url(self) -> str:
        parts = urlsplit(self.database_url)
        if parts.scheme in {
            "postgresql+asyncpg",
            "postgresql+psycopg",
            "postgresql+psycopg2",
            "postgres+psycopg",
            "postgres+psycopg2",
        }:
            return urlunsplit(("postgresql", parts.netloc, parts.path, parts.query, parts.fragment))
        return self.database_url

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def paystack_mode(self) -> str:
        k = self.paystack_secret_key
        if not k:
            return "unconfigured"
        return "live" if k.startswith("sk_live") else "test"


@lru_cache
def get_config() -> Settings:
    s = Settings()
    if not s.jwt_secret:
        raise RuntimeError("JWT_SECRET must be set to a non-empty random value")
    if s.app_env == "production":
        if s.jwt_secret.startswith("dev-only") or len(s.jwt_secret) < 32:
            raise RuntimeError("JWT_SECRET must be set to a strong random value (>=32 chars) in production")
        if not s.cookie_secure:
            raise RuntimeError("COOKIE_SECURE must be true in production (HTTPS only)")
    return s
