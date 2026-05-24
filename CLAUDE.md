# CLAUDE.md — E-Commerce Analytics Dashboard

## Project Overview

A full-stack e-commerce analytics platform built in Python/Django.
Portfolio project targeting Python/Django backend roles and data engineering/analyst roles.
Owner: Sayed | Brand context: Lilymade.it (handmade crochet bags, Italy)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, Django 5, Django REST Framework |
| Task Queue | Celery 5, Redis |
| Database | PostgreSQL 16 |
| Data / ML | Pandas, NumPy, scikit-learn |
| Visualisation | Plotly (embedded in Django templates) |
| Auth | SimpleJWT (JWT + refresh tokens) |
| API Docs | drf-spectacular (Swagger + Redoc) |
| DevOps | Docker, docker-compose |
| CI/CD | GitHub Actions (ruff, pytest, coverage) |
| Deployment | Railway or Render (free tier) |
| Testing | pytest, factory_boy, coverage |

---

## MVP Priority Order

Build strictly in this sequence. Do not scaffold Phase 2 until Phase 1 is complete and tested.

**Phase 1 — Foundation**
- Django project structure, Docker, docker-compose
- PostgreSQL connection, environment-based settings
- Core models with soft deletion and audit timestamps
- JWT auth, role-based permissions

**Phase 2 — API Layer**
- DRF endpoints, pagination, filtering, sorting
- API versioning (`/api/v1/`), error middleware
- drf-spectacular Swagger docs
- `/health/` endpoint

**Phase 3 — ETL Pipeline**
- CSV/JSON ingestion, incremental + idempotent logic
- Data quality validation pipeline, error quarantine
- Celery Beat nightly job with retry

**Phase 4 — Analytics**
- Revenue/AOV/top products/customer KPIs
- `AnalyticsSnapshot` model + nightly Celery snapshot job
- Analytics API endpoints + Plotly dashboard

**Phase 5 — Forecasting**
- scikit-learn trend projection
- Z-score anomaly detection
- Forecast API endpoint

---

## Project Structure

```
ecommerce_analytics/
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── users/               # Auth, roles, JWT
│   ├── products/            # Product, Category, Inventory
│   ├── orders/              # Order, OrderItem, Customer
│   ├── analytics/           # AnalyticsSnapshot, KPI computation
│   └── ingestion/           # ImportJob, ErrorQuarantine, pipeline
├── services/
│   ├── revenue_service.py
│   ├── import_service.py
│   ├── forecasting_service.py
│   └── analytics_service.py
├── tests/
├── docs/
│   ├── architecture.md
│   └── api.md
├── docker-compose.yml
├── Dockerfile
├── .env.example
└── requirements/
    ├── base.txt
    ├── development.txt
    └── production.txt
```

---

## Architecture Rules

### Service Layer (CRITICAL)
- **All business logic lives in `services/`, never in views or models.**
- Views call services. Services call models. Models are dumb.
- Example: `revenue_service.get_monthly_revenue(year, month)` — not inline in a viewset.
- This is non-negotiable. It is the single most important architectural decision in this project.

### Service Layer Conventions
- Services must be stateless — no instance variables that persist between calls.
- Services return structured data (dicts, dataclasses, model instances) — never `HttpResponse` or `Response`.
- Services never import or access `request` objects.
- Database transactions belong in services, not views.
- One service module = one responsibility (revenue, ingestion, forecasting, analytics).
- When in doubt: if logic would be duplicated across two views, it belongs in a service.

### Django Apps
- Each app owns its models, serializers, views, URLs, and tests.
- Cross-app logic belongs in `services/`, not in app-level code.
- No circular imports between apps.

### API
- All endpoints under `/api/v1/` prefix.
- Every list endpoint must have filtering, search, sorting, and pagination.
- Standardised error response format via middleware (see Standard API Response Format below).
- Auto-generated Swagger docs at `/api/v1/schema/redoc/` via drf-spectacular.

### Settings
- Never put secrets in code. Always use environment variables via `.env`.
- Use `config/settings/base.py` for shared config, `development.py` and `production.py` for overrides.

---

## Implementation Philosophy

When generating code, prefer:
- Readable, explicit logic over clever abstractions
- Django conventions over custom frameworks or patterns
- Flat structures over deeply nested inheritance
- Simple functions that do one thing over generic base classes
- Pragmatic solutions over theoretically perfect architecture

Avoid:
- Premature abstraction — don't generalise until there are at least two concrete cases
- Generic base classes unless they eliminate clear duplication
- Deeply nested inheritance chains
- Design patterns applied for their own sake (factory, strategy, observer etc.) unless the problem genuinely calls for them
- "Enterprise Java" style — this is a Python/Django project, not Spring Boot

---

## Data Models

All important models MUST have:
- `created_at = models.DateTimeField(auto_now_add=True)`
- `updated_at = models.DateTimeField(auto_now=True)`
- `is_deleted = models.BooleanField(default=False)` — soft deletion, never hard-delete business data

Core models:
- `User`, `Customer`, `Product`, `Category`, `Order`, `OrderItem`
- `Inventory`, `ImportJob`, `ErrorQuarantine`, `AnalyticsSnapshot`

---

## Standard API Response Format

All API responses must follow this structure. Implement via DRF renderer or middleware.

**Success:**
```json
{
  "success": true,
  "data": { }
}
```

**Paginated list:**
```json
{
  "success": true,
  "data": {
    "results": [],
    "count": 100,
    "next": "...",
    "previous": null
  }
}
```

**Error:**
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable description"
  }
}
```

Use consistent error codes: `VALIDATION_ERROR`, `NOT_FOUND`, `PERMISSION_DENIED`, `AUTHENTICATION_FAILED`, `RATE_LIMITED`, `INTERNAL_ERROR`.

---

## Serializer Rules

- Use separate read and write serializers when a model has different input vs output shapes.
- Avoid deeply nested serializers — flatten where possible or use a separate endpoint.
- Serializers handle transport validation only (types, required fields, formats).
- Business rule validation (e.g. "order total must be positive") belongs in services, not serializers.
- Keep serializers focused. If a serializer exceeds ~30 fields, question whether it should be split.

---

## Database Rules

- Use `select_related` / `prefetch_related` to prevent N+1 queries. Never leave N+1s in place.
- Use `aggregate()` and `annotate()` for analytics — do not compute in Python what PostgreSQL can do.
- Use `bulk_create()` for ETL inserts — never loop-insert rows one at a time.
- Add indexes on: date fields, foreign keys used in filters, fields used in analytics GROUP BY.
- Analytics figures go in `AnalyticsSnapshot` table (written by Celery job) — never recalculate live on every request.

---

## Query Performance Rules

- No endpoint should produce query count that grows with result set size (no O(n) query patterns).
- Use `select_related` / `prefetch_related` aggressively on any queryset with related objects.
- Expensive aggregations must be cached in Redis or precomputed in `AnalyticsSnapshot`.
- Never call a database query inside a loop.
- Every analytics endpoint reads from snapshots, not live aggregation.

---

## Migration Rules

- Never edit an existing migration file.
- One logical schema change per migration file.
- Add database indexes explicitly in migrations — do not rely on Django's automatic index creation alone.
- Name migrations descriptively: `0003_add_revenue_snapshot_index.py`, not `0003_auto_20250501.py`.
- Always run `python manage.py migrate` in Docker, never on the host directly.

---

## ETL & Data Pipeline Rules

- Ingestion must be **incremental and idempotent**: safe to re-run the same CSV/JSON file without creating duplicates.
- Every import runs through the data quality pipeline before touching the database.
- Failed/invalid rows go to the `ErrorQuarantine` table with a reason field — never silently dropped.
- Every `ImportJob` logs: start time, rows processed, rows failed, duration, status.
- Ingestion is triggered by Celery Beat (nightly) and also available via API endpoint.

### Data Quality Checks (required on every import)
- Missing required fields
- Invalid or future dates
- Negative prices or quantities
- Duplicate order IDs
- Malformed SKUs or category values
- Currency / timezone normalisation

---

## Dataset Assumptions

Design all analytics and ingestion logic for this expected scale:

- 50,000 – 200,000 orders total
- Seasonal sales trends (peaks around holidays)
- Mix of new and returning customers (~30% returning)
- Occasional refunds and cancellations (~5% of orders)
- Daily ingestion batches of 100–2,000 rows
- Multi-currency input normalised to EUR on import

This makes KPIs, forecasts, and anomaly detection feel realistic rather than toy-like.

---



## Core Relationships

- A `Customer` has many `Order` records.
- An `Order` has many `OrderItem` records.
- A `Product` belongs to one `Category`.
- An `OrderItem` belongs to one `Order` and one `Product`.
- An `Inventory` record belongs one-to-one with a `Product`.
- `AnalyticsSnapshot` stores precomputed KPI aggregates grouped by period/date.
- `ImportJob` tracks ingestion executions and owns many `ErrorQuarantine` rows.

---

## Initial API Endpoints

### Authentication
- `/api/v1/auth/login/`
- `/api/v1/auth/refresh/`

### Products
- `/api/v1/products/`
- `/api/v1/products/{id}/`

### Orders
- `/api/v1/orders/`
- `/api/v1/orders/{id}/`

### Customers
- `/api/v1/customers/`
- `/api/v1/customers/{id}/`

### Analytics
- `/api/v1/analytics/revenue/`
- `/api/v1/analytics/top-products/`
- `/api/v1/analytics/customers/`
- `/api/v1/analytics/forecast/`

### Ingestion
- `/api/v1/imports/`
- `/api/v1/imports/{id}/`

---

## AnalyticsSnapshot Purpose

`AnalyticsSnapshot` exists to avoid expensive live aggregations on production endpoints.

It stores:
- Daily revenue aggregates
- Weekly and monthly KPI summaries
- Rolling averages
- Top-product rankings
- Customer KPI summaries
- Forecast metadata and anomaly markers

Snapshots are written asynchronously by Celery jobs and treated as the source of truth for analytics endpoints.

---

## Caching Rules

Use Redis caching for:
- Analytics endpoints
- Dashboard KPI summaries
- Expensive aggregation queries
- Frequently accessed lookup endpoints

Cache invalidation should happen automatically after analytics snapshot refresh jobs complete.

Do not cache:
- Authentication endpoints
- Mutable write endpoints
- User-specific permission-sensitive responses

---

## Upload Constraints

- Maximum upload size: 10MB
- Accepted formats: CSV and JSON only
- Validate MIME type before ingestion begins
- Reject malformed files before processing
- Store uploaded files temporarily before validation
- Log upload failures with explicit error reasons

---

## README Requirements

README must include:
- Project overview and goals
- Architecture diagram
- Local setup instructions
- Docker usage instructions
- Environment variable reference
- API examples with request/response samples
- ETL pipeline explanation
- Analytics/KPI explanation
- Dashboard screenshots
- Deployment instructions
- Testing/linting commands

The README should be written as if onboarding another developer to the project.

## Celery Tasks

- `tasks/nightly_import.py` — runs ingestion pipeline, retries on failure (max 3 attempts)
- `tasks/analytics_snapshot.py` — writes precomputed KPIs to `AnalyticsSnapshot` table
- `tasks/cleanup.py` — soft-delete housekeeping

All tasks must have: retry logic, structured logging, error handling.

---

## Analytics & KPIs

Analytics are always served from `AnalyticsSnapshot` — never computed live.

Required KPIs:
- Revenue: daily / weekly / monthly with growth %
- Average Order Value (AOV): Revenue / Orders
- Top-selling products: by revenue and by quantity sold
- Customer breakdown: new vs. returning, simple lifetime value
- Sales trends: rolling 7-day and 30-day averages

Predictive layer (keep lightweight):
- Trend projection using scikit-learn linear regression
- Z-score anomaly detection on daily revenue
- Expose forecasts via `/api/v1/analytics/forecast/`

---

## Auth & Permissions

- JWT authentication via SimpleJWT. Access token + refresh token.
- Three roles: `admin`, `analyst`, `staff`
- Use DRF permission classes — never inline permission logic in views.
- Rate limiting via DRF throttling on all API endpoints.

---

## Logging

- Use Python's `logging` module with structured output (JSON in production).
- Log at every important boundary: ingestion start/end, task execution, auth events, errors.
- Never use `print()` — always `logger.info()` / `logger.error()` etc.
- Logger name = module name: `logger = logging.getLogger(__name__)`

---

## Health Check

`/health/` endpoint must return:
```json
{
  "status": "ok",
  "database": "ok",
  "redis": "ok",
  "celery": "ok"
}
```
Return HTTP 200 if all healthy, HTTP 503 if any component is down.

---

## Deployment Assumptions

- Single-server deployment only.
- Docker Compose — no Kubernetes, no container orchestration.
- No horizontal scaling required.
- Optimise for simplicity and interview credibility, not infinite scale.
- Target: Railway or Render free tier.

---

## Testing Rules

- Minimum 80% coverage — enforced in CI.
- Use `factory_boy` for all test data. Never hardcode fixture IDs.
- Test every service function independently (unit tests).
- Test every API endpoint: happy path, auth failure, invalid input, pagination.
- Run with: `pytest --cov=. --cov-report=term-missing`

---

## Code Style

- Linter: `ruff` — must pass with zero warnings before any commit.
- Formatter: `ruff format`
- Max line length: 100 characters
- Naming:
  - Files / modules: `snake_case`
  - Classes: `PascalCase`
  - Functions / variables: `snake_case`
  - Constants: `UPPER_SNAKE_CASE`
  - DB tables: `snake_case` (Django default)
- Imports: stdlib → third-party → local, separated by blank lines.
- Never use wildcard imports (`from module import *`).

---

## Unacceptable Patterns

Never generate code with these patterns:

- **Fat views** — any view with business logic beyond calling a service and returning a response
- **Business logic in serializers** — serializers validate transport, services validate business rules
- **Business logic in models** — models are data containers, not logic holders
- **Raw SQL** unless absolutely necessary and documented with a comment explaining why
- **Duplicate validation logic** — validate in one place, reference from others
- **Silent exception handling** — `except Exception: pass` is forbidden; always log or re-raise
- **`print()` debugging** — use the logging module
- **Circular imports** between apps
- **Hardcoded secrets or config values** in source files
- **Queryset calls inside loops** — always use bulk operations or prefetch

---

## Git Conventions

- Branch names: `feature/description` or `fix/description`
- Commit messages: conventional commits format
  - `feat: add revenue snapshot Celery task`
  - `fix: prevent duplicate import on re-run`
  - `chore: add ruff config to pyproject.toml`
- Never commit `.env`, secrets, or migration conflicts.

---

## Common Commands

```bash
# Start all services
docker-compose up

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# Run tests with coverage
docker-compose exec web pytest --cov=. --cov-report=term-missing

# Lint
ruff check .

# Format
ruff format .

# Trigger manual import
docker-compose exec web python manage.py import_orders --file=data/orders.csv

# Django shell
docker-compose exec web python manage.py shell_plus
```

---

## What NOT to Build

Do not suggest, implement, or scaffold any of the following — they are explicitly out of scope:

- React or any JS frontend framework (Django templates + Plotly only)
- GraphQL
- WebSockets / Django Channels
- Multi-tenancy
- Kubernetes or Helm charts
- Kafka or any message broker beyond Redis/Celery
- Elasticsearch or full-text search engines
- Microservices or service mesh
- Deep learning or neural networks
- Event sourcing or CQRS

If a simpler approach exists, always prefer it.

---

## Definition of Done

A feature is complete when:
1. Service function written and unit-tested
2. API endpoint (if applicable) written and integration-tested
3. `ruff check .` passes with zero warnings
4. `pytest` passes with no regressions
5. Relevant structured logging added
6. Swagger docs reflect the new endpoint (if applicable)

---

## Decision-Making Principle

When uncertain about scope, complexity, or approach, apply this test:

> "Does this make the project more credible to a hiring manager, or just more complicated?"

Choose credible over complicated every time.
