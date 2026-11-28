from functools import lru_cache
import ipaddress
from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str  # development | test | production
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "new_leaders_hotel"
    # Kept as a compatibility alias for existing deployments.
    database_url: str = "mongodb://localhost:27017"

    jwt_secret: str
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    bcrypt_rounds: int = 12
    cookie_secure: bool = False
    trust_proxy: bool = False
    trusted_proxy_cidrs: str = ""
    rate_limit_enabled: bool = True
    redis_url: str = ""

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
        return self.mongodb_url

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
    if s.app_env not in {"development", "test", "production"}:
        raise RuntimeError("APP_ENV must be development, test or production")
    if not s.jwt_secret:
        raise RuntimeError("JWT_SECRET must be set to a non-empty random value")
    if s.app_env == "production" and not s.mongodb_url:
        raise RuntimeError("MONGODB_URL must be set in production")
    if s.app_env == "production":
        if s.jwt_secret.startswith("dev-only") or len(s.jwt_secret) < 32:
            raise RuntimeError("JWT_SECRET must be set to a strong random value (>=32 chars) in production")
        if s.trust_proxy and not s.trusted_proxy_cidrs.strip():
            raise RuntimeError("TRUSTED_PROXY_CIDRS must be set when TRUST_PROXY=true in production")
        if s.trusted_proxy_cidrs.strip():
            try:
                for cidr in s.trusted_proxy_cidrs.split(","):
                    if cidr.strip():
                        ipaddress.ip_network(cidr.strip(), strict=False)
            except ValueError as exc:
                raise RuntimeError("TRUSTED_PROXY_CIDRS must contain valid IP addresses or CIDRs") from exc
        if not s.cookie_secure:
            raise RuntimeError("COOKIE_SECURE must be true in production (HTTPS only)")
        if not s.rate_limit_enabled:
            raise RuntimeError("RATE_LIMIT_ENABLED must be true in production")
        redis_url = urlsplit(s.redis_url)
        if redis_url.scheme not in {"redis", "rediss"} or not redis_url.hostname:
            raise RuntimeError("REDIS_URL must point to a Redis service in production")
        mongo_url = urlsplit(s.mongodb_url)
        mongo_host = (mongo_url.hostname or "").lower()
        if mongo_url.scheme not in {"mongodb", "mongodb+srv"} or not mongo_host or mongo_host in {"localhost", "127.0.0.1", "::1"}:
            raise RuntimeError("MONGODB_URL must point to a remote MongoDB database in production")
        public_url = urlsplit(s.public_base_url)
        if (public_url.scheme != "https" or not public_url.netloc or public_url.username or public_url.password
                or public_url.path not in ("", "/") or public_url.query or public_url.fragment):
            raise RuntimeError("PUBLIC_BASE_URL must be an absolute HTTPS URL in production")
        origins = [urlsplit(origin) for origin in s.origins]
        if not origins or any(
            origin.scheme != "https" or not origin.netloc or origin.path not in ("", "/")
            or origin.query or origin.fragment or origin.username or origin.password
            for origin in origins
        ):
            raise RuntimeError("CORS_ORIGINS must contain only HTTPS origins in production")
        if s.max_upload_mb < 1:
            raise RuntimeError("MAX_UPLOAD_MB must be a positive integer")
        if s.storage_backend not in {"local", "s3"}:
            raise RuntimeError("STORAGE_BACKEND must be 'local' or 's3'")
        if s.storage_backend == "s3" and not all((s.s3_bucket, s.s3_access_key_id, s.s3_secret_access_key, s.s3_public_base_url)):
            raise RuntimeError("S3_BUCKET, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY and S3_PUBLIC_BASE_URL are required for S3 storage")
        if s.storage_backend == "s3":
            s3_url = urlsplit(s.s3_public_base_url)
            endpoint = urlsplit(s.s3_endpoint_url) if s.s3_endpoint_url else None
            if s3_url.scheme != "https" or not s3_url.netloc or (endpoint and endpoint.scheme != "https"):
                raise RuntimeError("S3 public and endpoint URLs must use HTTPS in production")
    return s
