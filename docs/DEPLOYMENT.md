# Deployment

## Environment variables (see `.env.example`)
| Variable | Notes |
|---|---|
| `APP_ENV` | `production` enforces strong `JWT_SECRET` and secure cookies |
| `MONGODB_URL` | MongoDB Atlas connection string (`mongodb+srv://...`) or local MongoDB URI |
| `MONGODB_DATABASE` | MongoDB database name (default `new_leaders_hotel`) |
| `JWT_SECRET` | 32+ random chars (`python -c "import secrets;print(secrets.token_urlsafe(48))"`) |
| `REDIS_URL` | Shared rate-limit store (`redis://` or `rediss://`); required in production |
| `COOKIE_SECURE` | `true` behind HTTPS |
| `CORS_ORIGINS`, `PUBLIC_BASE_URL` | Your site origin(s) |
| `PAYSTACK_SECRET_KEY` | Backend only. `sk_test_…` first, then live |
| `RESEND_API_KEY`, `EMAIL_FROM` | Optional; without them emails are logged as skipped |
| `STORAGE_BACKEND` | `local` (needs a persistent volume) or `s3` (+ `S3_*`) |
| `RUN_SCHEDULER` | `true` on exactly one instance |
| `SERVE_FRONTEND` | `true` to serve the built SPA (with SEO tags) from the API |
| `SUPER_ADMIN_EMAIL/PASSWORD` | First boot only, then remove |

Never commit `.env`. Paystack and database credentials never go in the frontend.

`.env.example` contains development placeholders only. Production startup rejects a local MongoDB URL, non-HTTPS public URL/CORS origins, weak JWT secrets, insecure cookies, or incomplete S3 configuration. Supply production values through the hosting platform's secret manager instead of copying the development template unchanged. A production Super Admin must complete authenticator enrollment before using privileged APIs.

Rate limits use a Redis-backed sliding window shared across app workers and replicas. Docker Compose starts a private Redis service with no published port and defaults `REDIS_URL` to it; set `REDIS_URL` in the deployment environment to use a managed Redis-compatible service instead. Redis is required in production: an unavailable rate-limit store causes startup to fail or requests to return `503`, never a silent in-memory bypass. The Compose Redis instance is intentionally ephemeral; its counters reset on restart.

## Paystack
1. Dashboard → Settings → API: copy the **secret** key into `PAYSTACK_SECRET_KEY` on the server.
2. Webhook URL: `https://YOUR_DOMAIN/api/v1/webhooks/paystack` (signature verified with HMAC-SHA512; duplicates are ignored).
3. Callback is `/booking/payment/success`; it only *polls* the server, which verifies with Paystack. The redirect alone never confirms a booking.
4. Test with test keys: successful, failed, abandoned and duplicate-webhook cases, then switch to live.

## Run
- Docker: set `MONGODB_URL` and production settings in `.env`, then `docker compose up --build`. Compose starts Redis on its private network; do not publish its port.
- Manual: `npm run build` in `frontend`, then `SERVE_FRONTEND=true uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers` behind Nginx/Caddy with HTTPS. Set `X-Forwarded-*` and `TRUST_PROXY=true`.
- MongoDB Atlas: create a database user and cluster, allow the server IP address, and copy the `mongodb+srv://` connection string into `MONGODB_URL`.

## Backups & recovery
- MongoDB Atlas: enable continuous cloud backup or scheduled backups, and regularly test restore into a separate database.
- Back up the uploads volume (or use S3 versioning).
- Recovery: restore DB, restore uploads, start one app instance; expired holds are released automatically.

## Health & monitoring
`GET /api/v1/health` checks database readiness and returns `503` if MongoDB is unavailable; the Docker image uses it for its health check. Set `SENTRY_DSN` for error reporting. Review Super Admin → System overview for failed emails and integrations.

## Pre-launch checklist
- [ ] MongoDB/Atlas tested end to end  - [ ] Paystack test and webhook verified  - [ ] Email domain verified
- [ ] Taxes confirmed with the hotel's accountant  - [ ] Policies written (privacy, terms, cancellation)
- [ ] Real photos uploaded  - [ ] Sample data removed  - [ ] Super Admin MFA enrollment completed  - [ ] Backups scheduled and restore tested
