# E-Commerce Analytics Dashboard

A full-stack e-commerce analytics platform built in Python/Django. Portfolio project
targeting Python/Django backend and data engineering/analyst roles.

> **Status: Phase 1 — Foundation.** This phase delivers the project skeleton, Dockerised
> Postgres/Redis stack, environment-driven settings, the core domain models (with soft
> deletion + audit timestamps), and JWT authentication with role-based permissions.
> API endpoints, ETL, analytics, and forecasting arrive in later phases.

## Tech stack

Python 3.12 · Django 5 · Django REST Framework · SimpleJWT · PostgreSQL 16 · Redis ·
Docker / docker-compose · pytest + factory_boy · ruff · GitHub Actions.

## Project layout

```
config/        Django project: settings split (base/development/production), urls, wsgi/asgi
apps/
  common/      Shared abstract base model (timestamps + soft delete) and DRF permissions
  users/       Custom User model with role field; JWT auth endpoints
  products/    Category, Product, Inventory
  orders/      Customer, Order, OrderItem
tests/         pytest suite + factory_boy factories
requirements/  base / development / production dependency sets
```

## Local setup (Docker — recommended)

```bash
cp .env.example .env          # then edit SECRET_KEY etc.
docker-compose up --build     # starts web, postgres, redis
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

App runs at http://localhost:8000 · admin at http://localhost:8000/admin/.

## Environment variables

See `.env.example`. Key vars: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`,
`POSTGRES_DB/USER/PASSWORD/HOST/PORT`, `REDIS_URL`,
`DJANGO_SETTINGS_MODULE` (`config.settings.development` or `.production`).

## Authentication

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/auth/login/` | POST | Obtain access + refresh tokens (`username`, `password`) |
| `/api/v1/auth/refresh/` | POST | Exchange a `refresh` token for a new access token |

```bash
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"yourpassword"}'
# -> {"refresh":"...","access":"..."}
```

Three roles exist on the `User` model: `admin`, `analyst`, `staff`. Role-based DRF
permission classes live in `apps/common/permissions.py`.

## Data model notes

All core models inherit `apps.common.models.BaseModel`, providing `created_at`,
`updated_at`, and soft deletion: `.delete()` sets `is_deleted=True` rather than removing
the row. The default manager (`objects`) hides soft-deleted rows; `all_objects` includes them.

## Testing & linting

```bash
docker-compose exec web pytest --cov=. --cov-report=term-missing
docker-compose exec web ruff check .
```

## Roadmap

- **Phase 2** — DRF API layer: resource endpoints, pagination/filter/sort, `/api/v1/`
  versioning, standardised error middleware, Swagger (drf-spectacular), `/health/`.
- **Phase 3** — ETL pipeline: CSV/JSON ingestion, idempotent imports, data-quality
  quarantine, Celery Beat.
- **Phase 4** — Analytics: KPI snapshots, Plotly dashboard, Redis caching.
- **Phase 5** — Forecasting: scikit-learn trend projection, anomaly detection.
