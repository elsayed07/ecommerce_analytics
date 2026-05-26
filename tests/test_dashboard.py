from datetime import UTC, datetime

import pytest
from rest_framework.test import APIClient

from services import analytics_service

from .factories import OrderFactory, OrderItemFactory, ProductFactory, UserFactory

pytestmark = pytest.mark.django_db


def _seed_and_build():
    product = ProductFactory(sku="P1")
    order = OrderFactory(
        status="completed",
        total="100.00",
        order_date=datetime(2025, 1, 1, 12, 0, tzinfo=UTC),
    )
    OrderItemFactory(order=order, product=product, quantity=1, unit_price="100.00")
    analytics_service.build_snapshots()


def test_dashboard_requires_authentication():
    _seed_and_build()
    res = APIClient().get("/dashboard/")
    assert res.status_code == 302  # redirected to admin login


def test_dashboard_renders_plotly_for_staff():
    _seed_and_build()
    client = APIClient()
    client.force_login(UserFactory(is_staff=True))

    res = client.get("/dashboard/")
    assert res.status_code == 200
    assert "plotly" in res.content.decode().lower()
