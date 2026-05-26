from datetime import UTC, datetime, timedelta

import pytest
from rest_framework.test import APIClient

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
