# Screenshots & demo assets

The main README references the images in this folder. The committed `*.svg` files are
**placeholders** so the README renders cleanly before real captures exist. Replace them
with real screenshots when ready.

## How to capture

1. Start the stack and seed data:
   ```bash
   docker compose up -d
   docker compose exec web python manage.py generate_demo_data --orders=2000 --seed=42
   docker compose exec web python manage.py build_snapshots
   docker compose exec web python manage.py createsuperuser   # for dashboard access
   ```
2. Capture each screen below at ~1280px wide and save it here, then update the image
   path in the root `README.md` (swap the `.svg` placeholder for your `.png`/`.gif`).

| Screen | URL | Suggested file |
|---|---|---|
| Landing page (logged out) | `http://localhost:8000/` | `screenshot-landing.png` |
| Analytics dashboard (staff login) | `http://localhost:8000/dashboard/` | `screenshot-dashboard.png` |
| Swagger API docs | `http://localhost:8000/api/v1/schema/swagger-ui/` | `screenshot-swagger.png` |
| Short walkthrough recording | login → dashboard → an API call in Swagger | `demo.gif` |

Tips: keep the GIF under ~10 MB; tools like ScreenToGif (Windows), Kap (macOS), or
Peek (Linux) work well.
