from datetime import UTC, datetime, timedelta

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.analytics.models import AnalyticsSnapshot
from services import analytics_service

from .factories import OrderFactory, UserFactory

pytestmark = pytest.mark.django_db


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_forecast_requires_authentication():
    assert APIClient().get("/api/v1/analytics/forecast/").status_code == 401


def test_forecast_is_empty_before_any_snapshot():
    res = auth_client(UserFactory()).get("/api/v1/analytics/forecast/")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["forecast"] == []
    assert body["data"]["model"] is None


def test_forecast_endpoint_returns_projection_and_model():
    start = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
    for i in range(5):
        OrderFactory(
            status="completed",
            total=str(10 * (i + 1)),
            order_date=start + timedelta(days=i),
        )
    analytics_service.build_snapshots()

    res = auth_client(UserFactory()).get("/api/v1/analytics/forecast/")
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["forecast"]) == 30
    assert data["model"]["slope"] > 0


def test_forecast_endpoint_serves_snapshot_not_live_computation():
    day = datetime(2025, 1, 1, 12, tzinfo=UTC)
    OrderFactory(status="completed", total="100.00", order_date=day)
    OrderFactory(status="completed", total="200.00", order_date=day + timedelta(days=1))
    analytics_service.build_snapshots()

    # Overwrite the stored snapshot with a sentinel the live computation would never produce.
    snap = AnalyticsSnapshot.objects.get(snapshot_type="forecast")
    snap.metrics = {
        "forecast": [{"date": "2099-01-01", "predicted_revenue": 42.0}],
        "anomalies": [],
        "model": {"slope": 1.0, "intercept": 0.0, "r2": 1.0},
    }
    snap.save()
    cache.clear()

    data = auth_client(UserFactory()).get("/api/v1/analytics/forecast/").json()["data"]
    assert data["forecast"] == [{"date": "2099-01-01", "predicted_revenue": 42.0}]
