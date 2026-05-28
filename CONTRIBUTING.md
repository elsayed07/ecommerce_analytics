# Contributing

Thanks for your interest in this project! It is primarily a portfolio project, but
contributions, suggestions, and bug reports are welcome.

## Getting started

1. Fork and clone the repository.
2. Copy the environment template and start the stack:
   ```bash
   cp .env.example .env
   docker compose up --build -d
   docker compose exec web python manage.py migrate
   ```
3. (Optional) Seed demo data:
   ```bash
   docker compose exec web python manage.py generate_demo_data --orders=2000 --seed=42
   docker compose exec web python manage.py build_snapshots
   ```

## Development workflow

- **Branches:** `feature/<short-description>` or `fix/<short-description>`.
- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/) style —
  e.g. `feat: add revenue snapshot task`, `fix: prevent duplicate import`.
- **Architecture:** business logic lives in `services/`. Views call services, services
  call models, models stay dumb. Please keep this separation.

## Before opening a pull request

Run the same checks CI runs — all must pass:

```bash
docker compose exec web ruff check .
docker compose exec web ruff format --check .
docker compose exec web python manage.py makemigrations --check --dry-run
docker compose exec web pytest --cov=. --cov-report=term-missing
```

- Add or update tests for any behaviour change (the suite targets ≥80% coverage).
- Update the README / `.env.example` if you add settings or commands.
- Keep changes focused; avoid unrelated refactors in the same PR.

## Reporting bugs / requesting features

Open an issue using the provided templates and include reproduction steps,
expected vs. actual behaviour, and your environment where relevant.
