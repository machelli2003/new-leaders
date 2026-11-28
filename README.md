# New Leaders Hotel & Events Centre — Eastern Region (Akyem Tafo)

Single-hotel booking, operations and website system. React + TypeScript + Vite + Tailwind (frontend), FastAPI + MongoDB (backend), Paystack (GHS).

**No real hotel data is included.** Name, rates, photos, address, policies and taxes are entered by the hotel in the admin. Optional dev sample data is clearly labelled "(SAMPLE)".

## Quick start (development)

```bash
# 1. Backend (Python 3.11+)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install --require-hashes -r requirements-dev.txt
cp ../.env.example .env          # set APP_ENV=development, MONGODB_URL and JWT_SECRET (>=32 random chars)
python -m scripts.create_super_admin   # interactive; creates "Machellix"
uvicorn app.main:app --reload    # http://localhost:8000/docs

# 2. Frontend
cd ../frontend
npm install
npm run dev                      # http://localhost:5173 (proxies /api to :8000)
```

Optional dev-only sample content: `python -m scripts.seed_sample` (every record is marked SAMPLE; remove before launch).

For direct deployments, install production dependencies with `pip install --require-hashes -r backend/requirements.txt`. Dependency constraints live in `backend/requirements.in`. From `backend`, update the locks with `python -m piptools compile --allow-unsafe --generate-hashes --output-file requirements.txt requirements.in` and `python -m piptools compile --allow-unsafe --generate-hashes --output-file requirements-dev.txt requirements-dev.in`.

## First-time setup
1. Sign in at `/super-admin/login`, open **Setup wizard**, and create a **Hotel Admin** under Admin → Staff (Super Admin enters the hotel portal at `/admin`, audited).
2. Hotel Admin completes: Settings → profile, booking, payments (deposit/pay-at-hotel), taxes, cancellation; Rooms → categories (real rates) and physical rooms; Media → upload real photos; Website → write and publish sections.
3. Publish the hotel in the Setup wizard. Until then the public site shows "coming soon".

## Tests
`cd backend && pytest` — backend unit tests (auth/RBAC, booking, payments, pricing, CMS, and media).
Frontend: `cd frontend && npx tsc -b && npm run build`.

## Security scans
GitHub Actions runs security checks on pushes, pull requests, and weekly: `pip-audit` checks both Python lockfiles, Bandit checks high-severity/high-confidence Python findings, `npm audit` checks frontend dependencies, and `detect-secrets` scans tracked files against `.secrets.baseline`. Review new secret-baseline entries before accepting them.

## Documentation
- `docs/DEPLOYMENT.md` — environment variables, Paystack, email, storage, hosting, backups
- `docs/STAFF_GUIDE.md` — daily operation per role
- `docs/ARCHITECTURE.md` — data model and the rules that keep bookings and money correct
- API reference: run the backend and open `/docs` (OpenAPI)

## Known limitations (read before launch)
- Backend unit tests use an in-memory Mongo-compatible fixture for speed; **run the full flow against MongoDB/Atlas** before go-live.
- **Paystack, Resend email and S3 storage were never exercised against live services** here (Paystack is tested with a fake gateway incl. signature checks). Test with `sk_test_` keys first.
- SEO: the SPA gets per-route title/meta/OG/JSON-LD injected by the server, plus sitemap/robots. It is not full pre-rendering.
- Rate limiter is in-memory (per process). Use a gateway/WAF or Redis-backed limiter for multi-instance.
- Run the scheduler (hold expiry, reminders) on exactly one instance.
- WhatsApp notifications are not included. Guest accounts are minimal (lookup by reference + email is the main path).
- Frontend was type-checked and built, but not browser-tested end to end; expect small UI fixes.
