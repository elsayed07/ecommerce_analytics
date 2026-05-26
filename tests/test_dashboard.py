from datetime import UTC, datetime

import pytest
from rest_framework.test import APIClient

from services import analytics_service

from .factories import OrderFactory, OrderItemFactory, ProductFactory

pytestmark = pytest.mark.django_db


def test_dashboard_renders_plotly_charts():
    product = ProductFactory(sku="P1")
    order = OrderFactory(
        status="completed",
        total="100.00",
        order_date=datetime(2025, 1, 1, 12, 0, tzinfo=UTC),
    )
    OrderItemFactory(order=order, product=product, quantity=1, unit_price="100.00")
    analytics_service.build_snapshots()

    res = APIClient().get("/dashboard/")
    assert res.status_code == 200
    content = res.content.decode()
    assert "plotly" in content.lower()
