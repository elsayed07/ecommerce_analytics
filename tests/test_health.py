import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_health_reports_ok(monkeypatch):
    from config import celery_app

    monkeypatch.setattr(
        celery_app.control, "ping", lambda timeout=1: [{"worker": {"ok": "pong"}}]
    )
    res = APIClient().get("/health/")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["redis"] == "ok"
    assert body["celery"] == "ok"
