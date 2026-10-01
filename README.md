# RentalPro — Digital Rental Management System

IT Capstone project (RentalPro): a Flask application implementing 100% of
the functional requirements from the Software Requirements Specification
(Deliverable 1) — property listing, tenant records, rent tracking, and
maintenance requests, across five roles (Property Owner, Property Manager,
Tenant, Maintenance Staff, Admin). Deliverable 5 closed every remaining
gap against the SRS: unit editing, property/unit/maintenance photo
uploads, tenant blacklisting, admin user & role management, staff account
self-service, per-property late fees, and CSV/Excel export.

## Deliverable Status

| # | Deliverable | Status |
|---|---|---|
| 1 | Software Requirements Specification | ✅ Complete |
| 2 | UML & Database Design | ✅ Complete |
| 3 | Working prototype application | ✅ Complete |
| 4 | Complete project report (7 chapters + 2 appendices) | ✅ Complete |
| 5 | Fully-developed application — 100% of SRS features implemented and tested | ✅ Complete |
| 6 | Project demo video, presentation video, and final capstone report | ✅ **Complete** |

See [Deliverable 5 — Feature Completion](#deliverable-5--feature-completion) below for the full list of gaps closed and their test coverage (the full write-up, with a traceability table for all 44 functional requirements, is `docs/ABDURRAHMAAN_IT401_DEL_5.docx`), and `docs/ABDURRAHMAAN_IT401_DEL_6_*` for the Deliverable 6 files (demo video, presentation video + slide deck, and the final report).

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
  web_security.py           secret-key check at start-up, security headers
  scheduler_jobs.py         the 5 background jobs (UC-11, UC-14, UC-15, UC-23, automated billing)
  seed.py                    Harare demo data (matches credentials below)
  i18n.py                     English/Shona/Arabic interface translation
  routes/                     auth, dashboard, properties, tenants, rent, portal, maintenance, reports, api
  services/                    notifications.py, payments.py, pdf.py, reports.py
migrations/                   Alembic migrations (Flask-Migrate); see migrations/README
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
  test_i18n.py                      English/Shona/Arabic, right-to-left, language menu, place names never translated
  test_translated_documents.py      emails, SMS, PDFs, Excel and CSV in the reader's language
  test_web_security.py              secret key, security headers, cookie flags, no inline code
  test_migrations.py                migrations match the models; old databases are adopted
  test_storage.py                   uploads on local disk or in an S3-compatible bucket
  test_money.py                     amounts shown with their currency everywhere
  test_unit_history_and_maintenance_summary.py  tenant history per unit (FR-015), maintenance summary per period (FR-036)
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
cp env.example .env   # SECRET_KEY is required; compose will not start without it
docker compose up --build
# App:        http://localhost:5000
# PostgreSQL: localhost:5432
# Redis:      localhost:6379
```

The container entrypoint waits for Postgres, applies the database migrations
(`flask create-db`), and seeds demo data (`flask seed-db`) automatically on
first run.

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

### Uploaded files

Lease PDFs, ID documents and photos are stored on local disk
(`UPLOAD_FOLDER`) by default. Most hosting platforms wipe a server's disk
on every redeploy, so production should use a bucket:

```bash
STORAGE_BACKEND=s3
S3_BUCKET=rentalpro-uploads
S3_REGION=af-south-1                  # or S3_ENDPOINT_URL for Cloudflare R2, MinIO, ...
AWS_ACCESS_KEY_ID=...  AWS_SECRET_ACCESS_KEY=...
```

Routes and stored paths are identical for both backends
(`backend/services/storage.py`). Files stay private: they are streamed
through the app after its permission checks, never exposed by a public link.

### Database migrations

The schema is managed by Alembic migrations in `migrations/`, so a model
change never requires dropping a live database:

```bash
flask create-db                       # apply pending migrations (safe to re-run)
flask db migrate -m "Add unit notes"  # after editing backend/models.py
flask db upgrade                      # or: flask db downgrade
```

A database created before migrations existed (by the old `db.create_all()`)
is recognised and recorded at the first migration, keeping its data.
`tests/test_migrations.py` fails if the models and migrations ever differ.

## Demo Credentials

All demo accounts use the password `demo123`.

| Email | Name | Role |
|---|---|---|
| admin@rentalpro.com | Abdur-Rahmaan Ali | ADMIN — user & role management, bypasses ownership checks |
| owner@rentalpro.com | Tendai Moyo | PROPERTY_OWNER — full management access |
| manager@rentalpro.com | Rutendo Chikore | PROPERTY_MANAGER — management (no property creation) |
| staff@rentalpro.com | Farai Ncube | MAINTENANCE_STAFF — work queue only |
| tenant1@email.com … tenant9@email.com | Chipo Mutasa and eight others | TENANT — self-service portal only |

## Demo Data

`flask seed-db` loads a Harare portfolio into an empty database:

| Property | Area | Type | Units | Let |
|---|---|---|---|---|
| Avondale Heights | Avondale | Residential | 4 | 2 |
| Samora Machel Retail Row | CBD | Commercial | 2 shops | 1 |
| Julius Nyerere Business Centre | CBD | Mixed | 2 offices, 1 shop | 2 |
| Eastlea Garden Flats | Eastlea | Residential | 2 studios, 2 one-bed | 2 |
| Vainona Park Townhouses | Vainona | Residential | 3 townhouses | 2 |

That is 16 units, 9 active leases (56% occupancy), a payment history for
every lease, and three tenants in arrears, so the rent tracker, reports and
dashboards all have realistic figures. Every property has map coordinates.
The seed only runs on an empty database: delete `rentalpro.db` (or the
Postgres volume) to reload it.

## Languages: English, Shona and Arabic

A language button sits in the top bar and on the login page. It shows the
current language; click its arrow to open a list of English, ChiShona and
العربية (Arabic). The choice is kept in the session, survives logging in and
out, and is saved to the user's account (`users.language`), so it follows
them to other browsers. `backend/i18n.py` holds the Shona and Arabic phrase
tables; templates wrap interface text in `_("...")`, and any phrase without
an entry falls back to English.

Arabic pages are laid out right to left: the page is marked `dir="rtl"`, so
the navigation starts from the right and tables read from right to left.
The stylesheet aligns text to the start of the line rather than to a fixed
side, so one stylesheet serves both directions. Dates and codes inside
Arabic sentences are wrapped in invisible Unicode isolates so they keep
their left-to-right order.

**Arabic covers everything the app shows or sends:**
- every page, message and form option;
- **emails and SMS**, which are written in the recipient's saved language,
  including those sent by the nightly jobs;
- **PDFs** (statements, receipts, reports), which use the bundled DejaVu Sans
  font. Arabic text is joined into its connected letter forms
  (`arabic-reshaper`) and put into right-to-left order (`python-bidi`), and
  tables are mirrored;
- **the Excel report**, whose sheets open right to left in Arabic, and the
  **CSV export**, which carries a byte-order mark so Excel reads the Arabic
  headings.

`tests/test_i18n.py` fails if any of this text lacks Arabic. Shona covers the
main screens and falls back to English elsewhere. Data is never translated:
property names, addresses, suburbs, cities and people's names read the same
in every language, which `tests/test_i18n.py` also checks.

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

**Current results:** 298 tests (298 passed, 0 skipped on the latest run),
0 failures, 85% statement coverage across `backend/` (`pytest --cov=backend`).
One scheduler test self-skips on dates near month-end, where day-of-month clipping
(e.g. a due day of 31 landing in February) could shift the exact alert
date being asserted by a day.

## Deliverable 5 — Feature Completion

**Status: ✅ Complete — 100% of the SRS's functional requirements are
implemented and covered by an automated test.**

Deliverable 5 closed every gap between Deliverable 3's initial implementation
and 100% of the SRS's functional requirements:

| Gap closed | FR / UC | Where |
|---|---|---|
| Edit an existing unit's details and status | FR-005, FR-004 | `/properties/<id>/units/<id>/edit` |
| Property photos (up to 10) and unit photos (up to 5) | FR-003 | `/properties/<id>/edit`, unit edit form |
| Maintenance request photos (submission + completion, up to 3 each) | FR-028, UC-20 | `/maintenance/add`, `/maintenance/<id>/update` |
| Tenant ID document upload | UC-07 | `/tenants/add` |
| Lease document download (management and the tenant themselves) | UC-10 | `/tenants/<id>/lease-document/<lease_id>` |
| Blacklist / unblacklist a tenant, blocking future leases | FR-016 | `/tenants/<id>/blacklist` |
| Admin user & role management, with an "at least one active Owner" guard | UC-02 | `/admin/users` |
| Staff account self-service creation (Owner/Manager/Admin) | FR-044 | `/admin/staff/add` |
| Configurable per-property late fees (fixed or percentage), applied once a lease is overdue | FR-022 | `Property.late_fee_type/late_fee_amount`, `Lease.late_fee_due()` |
| CSV rent-history export | UC-17 | `/rent/<id>/history.csv` |
| Excel (.xlsx) report export | FR-043, UC-25 | `/reports/export.xlsx` |

All of the above ship with photo/document upload validation (magic-byte
checks reused from the existing PDF validator, extended to JPEG/PNG) and
are covered by `tests/test_deliverable5.py` (31 tests).

The Deliverable 5 report (`docs/ABDURRAHMAAN_IT401_DEL_5.docx`) later traced all
44 functional requirements one by one and found two only partly met: a full
tenant history per unit (FR-015) and a maintenance summary per period (FR-036).
Both were added afterwards — a History page on every unit and a Maintenance
Summary on the Reports page — and are covered by
`tests/test_unit_history_and_maintenance_summary.py` (13 tests). All 44 are now
met; FR-021 (overdue notices) and FR-044 (welcome emails) deliberately differ
from the SRS wording, as the report explains.

## Property Map

Every property can carry an optional `latitude`/`longitude`. Set it by
clicking a map on the Add/Edit Property forms (or typing coordinates
directly); a property's own Detail page then shows a small pin, and
`/properties/map` shows every located property in the portfolio on one
map, with a popup linking back to each property.

Leaflet's JS/CSS/marker icons are vendored into `frontend/static/vendor/leaflet/`
rather than pulled from a CDN, keeping the app's own assets self-contained —
the only thing that needs a live internet connection is the OpenStreetMap
map tiles themselves, which is unavoidable for any real map. Covered by
`tests/test_property_map.py` (8 tests).

## Security Controls

- **Password hashing** — `pbkdf2:sha256` with 600,000 iterations (Werkzeug).
- **RBAC** — `role_required(*roles)` enforced on every protected route; 5 roles.
- **IDOR protection** — `assert_owner()` / `assert_tenant_self()` verify the
  acting user may access the specific resource, not just the route.
- **CSRF** — Flask-WTF `CSRFProtect`, exempted only for the Stripe webhook.
- **Account lockout** — 5 failed logins locks the account for 15 minutes.
- **Open-redirect protection** — the login and language-switch `next=`
  parameters must be same-site paths (no scheme, host or backslash).
- **Secret key required** — the app refuses to start when `SECRET_KEY` is
  missing or a published placeholder, since that would let anyone forge a
  login. With `FLASK_DEBUG=1` it uses a random key for that run instead.
- **Security headers** — a Content-Security-Policy allowing scripts and styles
  from this site only (no inline code), `X-Frame-Options: DENY`, `nosniff`,
  a strict `Referrer-Policy`, and HSTS over HTTPS.
- **Session cookie** — `HttpOnly` and `SameSite=Lax`; set
  `SESSION_COOKIE_SECURE=true` in production so it is only sent over HTTPS.
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
