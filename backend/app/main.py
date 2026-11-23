from __future__ import annotations

import html
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db as database
from .audit import request_meta
from .config import get_config
from .routers import auth, bookings, catalog, hotel, media, operations, pricing, reports, reservations, system, users, website
from .security import client_ip, hash_password
from .utils import new_id, utcnow

log = logging.getLogger("nlh")
API = "/api/v1"


async def bootstrap_super_admin(db) -> None:
    cfg = get_config()
    if not (cfg.super_admin_email and cfg.super_admin_password):
        return
    if await db.users.find_one({"role": "super_admin"}):
        return
    await db.users.insert_one({"_id": new_id(), "name": cfg.super_admin_name, "email": cfg.super_admin_email.lower(), "role": "super_admin",
                               "password_hash": hash_password(cfg.super_admin_password), "is_active": True, "must_change_password": False,
                               "token_version": 0, "created_at": utcnow(), "updated_at": utcnow()})
    log.warning("Super Admin account created from environment. Remove SUPER_ADMIN_PASSWORD from the environment now.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_config()
    if cfg.sentry_dsn:
        try:
            import sentry_sdk

            sentry_sdk.init(dsn=cfg.sentry_dsn, environment=cfg.app_env, traces_sample_rate=0.0, send_default_pii=False)
        except ImportError:
            log.warning("SENTRY_DSN set but sentry-sdk is not installed")
    owns_db = database.holder.db is None
    if owns_db:
        await database.connect()
    await bootstrap_super_admin(database.get_db())
    sch = None
    if cfg.run_scheduler:
        from .services.jobs import start_scheduler

        sch = start_scheduler()
    yield
    if sch:
        sch.shutdown(wait=False)
    if owns_db:
        await database.close()


def create_app() -> FastAPI:
    cfg = get_config()
    app = FastAPI(title="New Leaders Hotel API", version="1.0.0", lifespan=lifespan,
                  docs_url="/api/docs" if cfg.app_env != "production" else None,
                  redoc_url=None, openapi_url="/api/openapi.json" if cfg.app_env != "production" else None)
    app.add_middleware(CORSMiddleware, allow_origins=cfg.origins, allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                       allow_headers=["Authorization", "Content-Type", "X-Requested-With"])

    @app.middleware("http")
    async def meta(request: Request, call_next):
        request_meta.set({"ip": client_ip(request), "ua": (request.headers.get("user-agent") or "")[:200]})
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        p = request.url.path
        if p.startswith(("/admin", "/super-admin", "/api")):
            resp.headers["X-Robots-Tag"] = "noindex, nofollow"
        if cfg.cookie_secure:
            resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return resp

    @app.exception_handler(HTTPException)
    async def http_exc(request: Request, exc: HTTPException):
        d = exc.detail
        body = {"error": {"status": exc.status_code, "message": d if isinstance(d, str) else d.get("message", "Error"),
                          **({"details": {k: v for k, v in d.items() if k != "message"}} if isinstance(d, dict) else {})}}
        return JSONResponse(body, status_code=exc.status_code, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def val_exc(request: Request, exc: RequestValidationError):
        errs = [{"field": ".".join(str(x) for x in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
        return JSONResponse({"error": {"status": 422, "message": "Validation failed", "details": {"fields": errs}}}, status_code=422)

    for r in (auth, users, hotel, catalog, media, website, pricing, bookings, reservations, operations, reports, system):
        app.include_router(r.router, prefix=API)

    @app.get(f"{API}/health", tags=["system"])
    async def health():
        return {"status": "ok"}

    if cfg.storage_backend == "local":
        os.makedirs(cfg.local_upload_dir, exist_ok=True)
        app.mount(cfg.local_media_url, StaticFiles(directory=cfg.local_upload_dir), name="media-files")

    @app.get("/robots.txt", include_in_schema=False)
    async def robots():
        from fastapi.responses import PlainTextResponse

        return PlainTextResponse(await system.robots_txt())

    @app.get("/sitemap.xml", include_in_schema=False)
    async def sitemap_xml():
        return await system.sitemap()

    if cfg.serve_frontend:
        _mount_frontend(app, cfg)
    return app


def _mount_frontend(app: FastAPI, cfg) -> None:
    """Serve the built SPA from the API process with per-route SEO metadata injected into <head>
    (title, description, Open Graph, canonical, Hotel JSON-LD) so crawlers/social previews see real values."""
    dist = os.path.abspath(cfg.frontend_dist)
    index_path = os.path.join(dist, "index.html")
    if not os.path.exists(index_path):
        log.warning("SERVE_FRONTEND is true but %s does not exist (run npm run build)", index_path)
        return
    if os.path.isdir(os.path.join(dist, "assets")):
        app.mount("/assets", StaticFiles(directory=os.path.join(dist, "assets")), name="assets")
    TITLES = {"/": "", "/about": "About", "/rooms": "Rooms & Suites", "/facilities": "Facilities", "/restaurant": "Restaurant & Dining", "/events": "Events & Conferences",
              "/gallery": "Gallery", "/offers": "Special Offers", "/contact": "Contact", "/faq": "FAQs", "/booking/search": "Book your stay", "/booking/lookup": "Find your booking",
              "/privacy-policy": "Privacy Policy", "/terms": "Terms & Conditions", "/cancellation-policy": "Cancellation Policy"}

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str, request: Request):
        fp = os.path.join(dist, full_path)
        if full_path and os.path.isfile(fp) and os.path.abspath(fp).startswith(dist):
            from fastapi.responses import FileResponse

            return FileResponse(fp)
        if full_path.startswith("api/"):
            raise HTTPException(404, "Not found")
        path = "/" + full_path.rstrip("/") if full_path else "/"
        page = open(index_path, encoding="utf-8").read()
        private = path.startswith(("/admin", "/super-admin", "/booking/payment", "/booking/checkout"))
        head = ""
        try:
            from .hotel_settings import get_settings

            s = await get_settings(database.get_db())
            p = s["profile"]
            title, desc = TITLES.get(path, ""), (p["description"] or f"{p['name']} – {p['town']}, {p['region']}, {p['country']}")[:300]
            if path.startswith("/rooms/"):
                c = await database.get_db().room_categories.find_one({"slug": path.split("/")[2], "status": "published"})
                if c:
                    title, desc = c["name"], (c.get("short_description") or desc)[:300]
            full_title = f"{title} | {p['name']}" if title else f"{p['name']} – {p['town']}"
            base = cfg.public_base_url.rstrip("/")
            e = html.escape
            head = (f"<title>{e(full_title)}</title><meta name=\"description\" content=\"{e(desc)}\"/>"
                    f"<link rel=\"canonical\" href=\"{e(base + path)}\"/><meta property=\"og:title\" content=\"{e(full_title)}\"/>"
                    f"<meta property=\"og:description\" content=\"{e(desc)}\"/><meta property=\"og:type\" content=\"website\"/>"
                    f"<meta property=\"og:url\" content=\"{e(base + path)}\"/>")
            if private:
                head += "<meta name=\"robots\" content=\"noindex,nofollow\"/>"
            if path == "/":
                ld = {"@context": "https://schema.org", "@type": "Hotel", "name": p["name"], "description": p["description"], "url": base,
                      "telephone": (p["phones"] or [""])[0], "email": (p["emails"] or [""])[0],
                      "address": {"@type": "PostalAddress", "streetAddress": p["address"], "addressLocality": p["town"], "addressRegion": p["region"], "addressCountry": "GH"}}
                head += f"<script type=\"application/ld+json\">{json.dumps(ld).replace('<', '\\u003c')}</script>"
        except Exception:
            log.exception("SEO injection failed")
        page = page.replace("<!--SEO_HEAD-->", head)
        return HTMLResponse(page, headers={"X-Robots-Tag": "noindex, nofollow"} if private else {})


app = create_app()
