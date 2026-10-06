# 🛍️ Smart E-Commerce Platform

A two-panel e-commerce system sharing **one database**:

| Panel | Tech | Port | Purpose |
|---|---|---|---|
| **User panel** | FastAPI + SQLAlchemy + vanilla-JS storefront | `8000` | Browse, cart, Stripe checkout, orders, real-time notifications |
| **Admin panel** | Django (admin + custom dashboard) | `8001` | Users/roles, products, orders, analytics, CSV/PDF reports |

```
 Browser ──HTTP/WS──▶ FastAPI :8000 ──┐
                         ▲            ├──▶ PostgreSQL / SQLite  (schema owned by Django migrations)
 Admin   ──HTTP────▶ Django :8001  ───┘
                         └── POST /api/internal/notify ──▶ FastAPI ──WebSocket──▶ customer browser
 Stripe ──webhook──▶ FastAPI /api/payments/webhook
```

**Key design decisions**
* **Django owns the schema.** FastAPI maps the same tables with SQLAlchemy (`api/app/models.py`) and never migrates in production.
* **Interoperable passwords.** The API hashes with Django's PBKDF2-SHA256 format, so a user created in either panel can log in via the other.
* **Roles** (`admin` / `staff` / `customer`) live in `users.role`. Django syncs `is_staff`/`is_superuser` from it; FastAPI uses a `require_roles(...)` dependency.
* **Order status changes in Django** (admin edits, bulk actions) fire a signal → in-app notification + email + a WebSocket push through FastAPI.
* **Mock payment mode.** With no Stripe keys the full flow still works (simulate success/failure) — ideal for demos and tests.

---

## 1. Quick start (local, SQLite, no Docker)

Requires Python 3.11+.

```bash
make setup            # venv + dependencies + .env copied from .env.example
make migrate          # creates data/db.sqlite3
make seed             # demo users, products, 30 days of orders
make admin            # terminal 1 → http://localhost:8001/admin/
make api              # terminal 2 → http://localhost:8000
```
Without `make`:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r admin_panel/requirements.txt -r api/requirements.txt
cp .env.example .env
cd admin_panel && python manage.py migrate && python manage.py seed_demo && python manage.py runserver 8001
# second terminal:
cd api && uvicorn app.main:app --reload --port 8000
```

| URL | What |
|---|---|
| http://localhost:8000 | Storefront (responsive SPA) |
| http://localhost:8000/docs | Swagger UI for the API |
| http://localhost:8001/admin/ | Django admin |
| http://localhost:8001/dashboard/ | Analytics dashboard (Chart.js) |

**Demo logins** (from `seed_demo`)

| Role | Email | Password |
|---|---|---|
| admin | admin@example.com | Admin@12345 |
| staff | staff@example.com | Staff@12345 |
| customer | customer@example.com | Customer@12345 |

## 2. Docker (PostgreSQL)

```bash
cp .env.example .env     # optional: add Stripe / Auth0 / SMTP values
docker compose up --build
docker compose exec admin python manage.py seed_demo
```

## 3. Configuration (`.env`)

See `.env.example` — every variable is documented there. The important ones:

| Variable | Notes |
|---|---|
| `DATABASE_URL` | `sqlite:///data/db.sqlite3` (default) or `postgresql://user:pass@host:5432/db` — **same value for both apps** |
| `JWT_SECRET`, `DJANGO_SECRET_KEY`, `INTERNAL_SECRET` | **Change in production.** `INTERNAL_SECRET` must match in both apps |
| `STRIPE_SECRET_KEY` / `STRIPE_PUBLISHABLE_KEY` / `STRIPE_WEBHOOK_SECRET` | Empty ⇒ mock payments |
| `AUTH0_DOMAIN` / `AUTH0_CLIENT_ID` | Empty ⇒ social login hidden (API returns 501) |
| `SMTP_HOST` … | Empty ⇒ emails are printed to the console |
| `LOW_STOCK_THRESHOLD` | Dashboard low-stock alert level (default 5) |

### Stripe
1. Put test keys (`sk_test_…`, `pk_test_…`) in `.env`.
2. Forward webhooks: `stripe listen --forward-to localhost:8000/api/payments/webhook` and copy the printed `whsec_…` into `STRIPE_WEBHOOK_SECRET`.
3. Pay with test card `4242 4242 4242 4242` (any future date / CVC). Decline test: `4000 0000 0000 0002`.
4. The order is confirmed **only from the webhook** (`payment_intent.succeeded` / `payment_intent.payment_failed`), never from the browser.

### Auth0 (Google / Facebook)
1. Create a *Single Page Application* in Auth0; enable the Google and Facebook social connections for it.
2. Allowed Callback URLs: `http://localhost:8000/`. Enable the **Implicit** grant (Advanced → Grant Types).
3. Set `AUTH0_DOMAIN` (e.g. `dev-abc.us.auth0.com`) and `AUTH0_CLIENT_ID`. Restart the API — the login dialog now shows the social buttons.
4. Flow: Auth0 returns an ID token → `POST /api/auth/auth0` verifies signature/issuer/audience/nonce via Auth0's JWKS → we issue our own JWT pair and create the user on first login.

## 4. Features ↔ where to find them

| Requirement | Implementation |
|---|---|
| Register/login, JWT (access + refresh), Auth0 social | `api/app/routers/auth.py`, `security.py` |
| Browse by category / price / popularity, search, pagination | `GET /api/products` (`category`, `min_price`, `max_price`, `sort=popularity`, `q`) |
| Cart add/remove/update | `api/app/routers/cart.py` |
| Stripe checkout + webhook + retry | `routers/orders.py`, `routers/payments.py`, `services/stripe_service.py` |
| Atomic stock reservation, cancel → restock | `routers/orders.py` |
| Order history & status | `GET /api/orders`, storefront "📦" tab |
| Email + in-app notifications | `services/notifications.py`, `services/email.py`, `admin_panel/shop/notifications.py` |
| Real-time WebSockets (orders, cart, notifications) | `ws://…/ws/notifications?token=…`, `api/app/realtime.py` |
| RBAC | `deps.require_roles`; `RolePermissionMixin` in `admin_panel/shop/admin.py` |
| Admin: users CRUD + roles, products + images, orders | Django admin (`admin_panel/shop/admin.py`) |
| Analytics: sales, top products, revenue trend, low stock | `/dashboard/` |
| CSV / PDF export | Dashboard buttons → `/dashboard/export/<report>.<csv|pdf>` (sales, top-products, revenue, low-stock) |
| Mobile-responsive UI | `frontend/` (CSS grid, dark-mode aware) |

**Role matrix (Django admin)**

| | admin | staff | customer |
|---|---|---|---|
| Users / Notifications | full | – | – |
| Products & categories | full | view/add/change | – |
| Orders | full | view/change status | own orders via API |
| Payments | view | view | own via API |
| Delete anything | ✔ | ✘ | ✘ |

## 5. API overview

Full, runnable list: import `postman/Smart-Ecommerce.postman_collection.json` (39 requests; login requests store the token automatically) or open `/docs`.

| Area | Endpoints |
|---|---|
| Auth | `POST /api/auth/register · login · token · refresh · auth0` · `GET /api/auth/me` |
| Catalogue | `GET /api/categories · /api/products · /api/products/{id}` |
| Cart | `GET/POST/DELETE /api/cart` · `PATCH/DELETE /api/cart/{product_id}` |
| Orders | `POST /api/orders/checkout` · `GET /api/orders · /{id}` · `POST /{id}/pay · /{id}/cancel` |
| Payments | `GET /api/payments/config` · `POST /api/payments/webhook` · `POST /api/payments/{order_id}/mock-confirm` (demo only) |
| Notifications | `GET /api/notifications · /unread-count` · `POST /{id}/read · /read-all` |
| Staff | `GET /api/admin/summary` (admin+staff) · `GET /api/admin/users` (admin) |
| WebSocket | `/ws/notifications?token=<access_token>` → `connected`, `notification`, `cart_updated` |

## 6. Database

* Migrations: `admin_panel/shop/migrations/0001_initial.py` → `python manage.py migrate`.
* Reference SQL: `sql/schema_postgres.sql`. Exact SQL for any backend: `python manage.py sqlmigrate shop 0001`.
* Dump after seeding: `sqlite3 data/db.sqlite3 .dump > sql/dump.sql` or `pg_dump shop > sql/dump.sql`.

## 7. Tests

```bash
make test        # or: cd api && python -m pytest -q
```
Covers: Django-compatible hashing, auth/refresh, filters/sorting, cart & stock limits, checkout → payment success / failure / retry / cancel-restock, order privacy, RBAC, WebSocket events, internal notify secret.

## 8. Verification status (please read)

This code was generated in a sandbox **without internet access**, so Django/FastAPI/SQLAlchemy could not be installed there. What was actually checked: every Python file compiles, the frontend JS passes `node --check`, the security module (hashing/JWT) was executed and verified, and the Postman JSON was generated programmatically. **The test-suite and the two servers have not been run end-to-end yet.** On your machine, run in this order and report any failure:

1. `python manage.py migrate` then `python manage.py makemigrations --check` (the initial migration was hand-written; if Django reports drift, run `makemigrations` and commit the result).
2. `make test`
3. Walk through `docs/DEMO_GUIDE.md`.

## 9. Production checklist / known limits

* Set strong secrets, `DJANGO_DEBUG=0`, real `ALLOWED_HOSTS`, HTTPS (use `wss://`), restrict `CORS_ORIGINS`.
* Put a reverse proxy (nginx/Caddy) in front; serve `/media` from object storage/CDN.
* Pending orders keep their stock reserved until paid or cancelled — add a scheduled job to cancel stale ones.
* Real-time delivery uses an in-process hub: with several API workers/instances, replace `realtime.py` with Redis pub/sub.
* Emails are sent from background threads; for volume use a queue (Celery/RQ).
* Auth0 uses the implicit flow for simplicity; prefer Authorization Code + PKCE for hardened deployments.
* No rate limiting on login — add it (e.g. `slowapi`) before going live.
