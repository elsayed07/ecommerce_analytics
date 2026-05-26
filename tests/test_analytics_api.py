from datetime import UTC, datetime

import pytest
from rest_framework.test import APIClient

from services import analytics_service

from .factories import OrderFactory, OrderItemFactory, ProductFactory, UserFactory

pytestmark = pytest.mark.django_db


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _dt(year, month, day):
    return datetime(year, month, day, 12, 0, tzinfo=UTC)


def test_revenue_requires_authentication():
    assert APIClient().get("/api/v1/analytics/revenue/").status_code == 401


def test_revenue_endpoint_returns_snapshot_series():
    OrderFactory(status="completed", total="100.00", order_date=_dt(2025, 1, 1))
    analytics_service.build_snapshots()

    res = auth_client(UserFactory()).get("/api/v1/analytics/revenue/?period=daily")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["period"] == "daily"
    assert body["data"]["series"][0]["revenue"] == 100.0


def test_top_products_and_customers_endpoints():
    product = ProductFactory(sku="P1")
    order = OrderFactory(status="completed", total="20.00", order_date=_dt(2025, 1, 1))
    OrderItemFactory(order=order, product=product, quantity=2, unit_price="10.00")
    analytics_service.build_snapshots()
    client = auth_client(UserFactory())

    top = client.get("/api/v1/analytics/top-products/").json()
    assert top["data"]["by_revenue"][0]["sku"] == "P1"

    customers = client.get("/api/v1/analytics/customers/").json()
    assert customers["data"]["total_customers"] == 1


def test_revenue_is_empty_before_any_snapshot():
    res = auth_client(UserFactory()).get("/api/v1/analytics/revenue/")
    assert res.status_code == 200
    assert res.json()["data"]["series"] == []
