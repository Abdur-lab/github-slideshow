# RentalPro — Digital Rental Management System

IT Capstone project (RentalPro): a Flask application implementing the 25 use
cases from the Software Requirements Specification (Deliverable 1) and the
UML & Database Design (Deliverable 2) — property listing, tenant records,
rent tracking, and maintenance requests, across five roles (Property Owner,
Property Manager, Tenant, Maintenance Staff, Admin).

## Technology Stack

| Layer | Choice |
|---|---|
| Language | Python 3.12 |
| Web framework | Flask 3.1 (application factory pattern) |
| ORM | Flask-SQLAlchemy — 13 models, UUID primary keys |
| Database | SQLite (dev/test) → PostgreSQL 15 (Docker/production) |
| Auth / Security | Werkzeug `pbkdf2:sha256` (600,000 iterations), CSRF (Flask-WTF), RBAC via `role_required` |
| Rate limiting | Flask-Limiter |
| Caching | Flask-Caching (SimpleCache dev / Redis in Docker) |
| Scheduler | APScheduler — 4 cron jobs (lease expiry, rent due, overdue, maintenance escalation) |
| Email / SMS | SendGrid / Twilio — dev-mode fallback when no API key is configured |
| Payments | Stripe-style dev-mode checkout + custom HMAC webhook verification |
| PDF export | reportlab (pure Python — no native system libraries, unlike WeasyPrint) |
| Testing | pytest + pytest-cov |
| Deployment | Docker + docker-compose (Flask/Gunicorn + PostgreSQL + Redis), GitHub Actions CI |

## Project Layout

```
backend/
  __init__.py          create_app(), scheduler wiring, CLI commands, error handlers
  config.py             Config / TestConfig
  extensions.py          db, csrf, limiter, cache, scheduler singletons
  models.py               13 SQLAlchemy models + business logic (balances, occupancy, numbering)
  security.py              auth, RBAC, IDOR guard, input validation, audit log
  scheduler_jobs.py         the 4 background jobs (UC-11, UC-14, UC-15, UC-23)
  seed.py                    demo data (matches credentials below)
  routes/                     auth, dashboard, properties, tenants, rent, portal, maintenance, reports, api
  services/                    notifications.py, payments.py, pdf.py, reports.py
frontend/
  templates/                  Jinja2 templates (base layout + one per page)
  static/css/style.css         design system
tests/
  conftest.py                   fixtures (fresh in-memory SQLite per test)
  test_models.py                  business logic: balances, due-date math, numbering formats
  test_auth.py                     login, lockout, RBAC, IDOR protection
  test_routes.py                    end-to-end feature flows for all 25 use cases
  test_scheduler.py                 the 4 background jobs, invoked directly
  test_validation.py                validate(), validate_upload(), Stripe HMAC, idempotency
app.py                                entry point (`python app.py` / `gunicorn app:app`)
Dockerfile, docker-compose.yml, .github/workflows/ci.yml
```

## Use Case Implementation Status

All 25 use cases from the SRS are implemented, with a route and a covering test:

| UC | Name | Route(s) |
|---|---|---|
| UC-01 | Register / Login | `/login`, `/logout` |
| UC-02 | RBAC | `role_required()` on every protected route |
| UC-03 | Add Property | `/properties/add` |
| UC-04 | Add / Edit Unit | `/properties/<id>/add-unit` |
| UC-05 | Property Dashboard | `/dashboard`, `/api/v1/dashboard-stats` |
| UC-06 | Archive Property / Unit | `/properties/<id>/archive`, `/properties/<id>/units/<id>/archive` |
| UC-07 | Create Tenant Profile | `/tenants/add` |
| UC-08 | Invite Tenant (48h link) | `/tenants/invite`, `/register/invitation/<token>` |
| UC-09 | Upload Lease Document | `/tenants/<id>/upload-lease` |
| UC-10 | Tenant Views Lease / Profile | `/portal` |
| UC-11 | Lease Expiry Alerts (60/30/7d) | `job_lease_expiry_alerts()` |
| UC-12 | Record Rent Payment | `/rent/record` |
| UC-13 | Pay Rent Online | `/portal/pay`, `/api/v1/webhooks/stripe` |
| UC-14 | Rent Due Alerts (7d/1d) | `job_rent_due_alerts()` |
| UC-15 | Overdue Notices | `job_overdue_alerts()` |
| UC-16 | Generate Rent Statement | `/rent/<id>/statement`, `/rent/<id>/statement.pdf` |
| UC-17 | View Rent History | `/rent/<id>/history`, `/portal/history` |
| UC-18 | Submit Maintenance Request | `/maintenance/add` |
| UC-19 | Assign Maintenance Request | `/maintenance/<id>/update` (assign) |
| UC-20 | Update Request Status | `/maintenance/<id>/update` (start/complete) |
| UC-21 | Confirm / Reopen Request | `/maintenance/<id>/update` (close/reopen) |
| UC-22 | Log Maintenance Cost | `/maintenance/<id>/costs/add` |
| UC-23 | Escalate Overdue Maintenance | `job_escalate_overdue_maintenance()` |
| UC-24 | Property Performance Report | `/reports` |
| UC-25 | Export Report (PDF / JSON) | `/reports/export.pdf`, `/api/v1/reports/export` |

## Run the Application

### Docker (recommended)

```bash
cp env.example .env   # set SECRET_KEY at minimum
docker compose up --build
# App:        http://localhost:5000
# PostgreSQL: localhost:5432
# Redis:      localhost:6379
```

The container entrypoint waits for Postgres, creates the schema (`flask
create-db`), and seeds demo data (`flask seed-db`) automatically on first run.

### Local (without Docker)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
export DATABASE_URL=sqlite:///rentalpro.db
flask create-db
flask seed-db
python app.py
# App: http://localhost:5000
```

Any of `SENDGRID_API_KEY`, `TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN`, and
`STRIPE_SECRET_KEY` can be left unset — email/SMS then log as `SENT`
without calling an external API, and online payments use a simulated
checkout, so the whole app is exercisable offline.

## Demo Credentials

| Email | Password | Role |
|---|---|---|
| owner@rentalpro.com | demo123 | PROPERTY_OWNER — full management access |
| manager@rentalpro.com | demo123 | PROPERTY_MANAGER — management (no property creation) |
| tenant1@email.com | demo123 | TENANT — self-service portal only |
| staff@rentalpro.com | demo123 | MAINTENANCE_STAFF — work queue only |

## Run the Test Suite

```bash
pytest tests/ -v                                    # all tests
pytest tests/ --cov=backend --cov-report=term-missing  # with coverage
pytest tests/test_models.py -v                       # a single file
pytest tests/test_models.py::test_receipt_number_format -v  # a single test
```

Tests run against an in-memory SQLite database with a fresh schema per test
— no external services or API keys required. Stripe, SendGrid, and Twilio
calls are exercised through their dev-mode fallback and monkeypatched
failure paths, not live network calls.

**Current results:** 93 tests, 0 failures, 77% statement coverage across
`backend/` (`pytest --cov=backend`). Two tests self-skip within a few days
of month-end, where day-of-month clipping (e.g. a due day of 31 landing in
February) could shift the exact alert date being asserted by a day.

## Security Controls

- **Password hashing** — `pbkdf2:sha256` with 600,000 iterations (Werkzeug).
- **RBAC** — `role_required(*roles)` enforced on every protected route; 5 roles.
- **IDOR protection** — `assert_owner()` / `assert_tenant_self()` verify the
  acting user may access the specific resource, not just the route.
- **CSRF** — Flask-WTF `CSRFProtect`, exempted only for the Stripe webhook.
- **Account lockout** — 5 failed logins locks the account for 15 minutes.
- **Open-redirect protection** — the login `next=` parameter is validated
  (netloc and scheme must be empty) before use.
- **Stripe webhook verification** — manual `t=<ts>,v1=<hmac>` HMAC check
  with a 300-second replay window, independent of the Stripe SDK's own
  verifier so it's unit-testable offline; idempotent on `gateway_ref`.
- **File upload validation** — rejects anything whose first bytes aren't
  `%PDF-`, regardless of extension (blocks a ZIP renamed to `.pdf`).
- **Audit log** — every state-changing action writes an immutable
  `AuditLog` row (`user_id`, `action`, entity, before/after, `ip_address`);
  safe to call from a background job (`ip_address='scheduler'`).

## Notable Design Deviations from Deliverable 2

Two swaps were made for a simpler, more portable Docker build, without
changing what the application does:

- **PDF export** uses `reportlab` instead of WeasyPrint — pure Python, no
  Cairo/Pango system libraries required.
- **Primary keys** are `String(36)` UUIDs rather than a Postgres-native
  `UUID` column type, so the same schema works unmodified on SQLite in
  tests/dev and PostgreSQL in Docker.

Everything else (13 tables, RBAC roles, use case coverage, scheduler jobs,
security controls) follows the SRS and UML & Database Design documents.
