# Deployment

## Environment variables (see `.env.example`)
| Variable | Notes |
|---|---|
| `APP_ENV` | `production` enforces strong `JWT_SECRET` and secure cookies |
| `DATABASE_URL` | PostgreSQL connection string (`postgresql://user:password@host:5432/database`). The app creates its JSONB document table and indexes on startup |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Docker Compose PostgreSQL credentials; use strong values outside local development |
| `JWT_SECRET` | 32+ random chars (`python -c "import secrets;print(secrets.token_urlsafe(48))"`) |
| `COOKIE_SECURE` | `true` behind HTTPS |
| `CORS_ORIGINS`, `PUBLIC_BASE_URL` | Your site origin(s) |
| `PAYSTACK_SECRET_KEY` | Backend only. `sk_test_…` first, then live |
| `RESEND_API_KEY`, `EMAIL_FROM` | Optional; without them emails are logged as skipped |
| `STORAGE_BACKEND` | `local` (needs a persistent volume) or `s3` (+ `S3_*`) |
| `RUN_SCHEDULER` | `true` on exactly one instance |
| `SERVE_FRONTEND` | `true` to serve the built SPA (with SEO tags) from the API |
| `SUPER_ADMIN_EMAIL/PASSWORD` | First boot only, then remove |

Never commit `.env`. Paystack and database credentials never go in the frontend.

## Paystack
1. Dashboard → Settings → API: copy the **secret** key into `PAYSTACK_SECRET_KEY` on the server.
2. Webhook URL: `https://YOUR_DOMAIN/api/v1/webhooks/paystack` (signature verified with HMAC-SHA512; duplicates are ignored).
3. Callback is `/booking/payment/success`; it only *polls* the server, which verifies with Paystack. The redirect alone never confirms a booking.
4. Test with test keys: successful, failed, abandoned and duplicate-webhook cases, then switch to live.

## Run
- Docker: `docker compose up --build` (reads `.env` and starts PostgreSQL), or build the image and point `DATABASE_URL` at a managed PostgreSQL instance.
- Manual: `npm run build` in `frontend`, then `SERVE_FRONTEND=true uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers` behind Nginx/Caddy with HTTPS. Set `X-Forwarded-*` and `TRUST_PROXY=true`.
- For a local PostgreSQL install, create the database before starting the API: `createdb -U postgres new_leaders_hotel`. If the installer assigned a different password, put it in `DATABASE_URL` in `backend/.env`.
- For Docker Compose, copy `.env.example` to the project root as `.env`; Compose uses those PostgreSQL credentials to configure both the database and app.

## Backups & recovery
- Managed PostgreSQL: enable point-in-time recovery. Self-hosted: nightly `pg_dump "$DATABASE_URL" --format=custom --file=backup.dump`, copy off-server, and regularly test `pg_restore` into a separate database.
- Back up the uploads volume (or use S3 versioning).
- Recovery: restore DB, restore uploads, start one app instance; expired holds are released automatically.

## Health & monitoring
`GET /api/v1/health`. Set `SENTRY_DSN` for error reporting. Review Super Admin → System overview for failed emails and integrations.

## Pre-launch checklist
- [ ] Real PostgreSQL tested end to end  - [ ] Paystack test and webhook verified  - [ ] Email domain verified
- [ ] Taxes confirmed with the hotel's accountant  - [ ] Policies written (privacy, terms, cancellation)
- [ ] Real photos uploaded  - [ ] Sample data removed  - [ ] Super Admin MFA enabled  - [ ] Backups scheduled
