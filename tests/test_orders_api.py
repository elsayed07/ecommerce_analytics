import pytest
from rest_framework.test import APIClient

from apps.users.models import User

from .factories import OrderFactory, OrderItemFactory, UserFactory

pytestmark = pytest.mark.django_db


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_orders_list_is_enveloped():
    OrderFactory.create_batch(2)
    res = auth_client(UserFactory()).get("/api/v1/orders/")

    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["count"] == 2


def test_order_detail_includes_items():
    order = OrderFactory()
    OrderItemFactory.create_batch(2, order=order)
    res = auth_client(UserFactory()).get(f"/api/v1/orders/{order.id}/")

    assert res.status_code == 200
    assert len(res.json()["data"]["items"]) == 2


def test_orders_are_read_only():
    client = auth_client(UserFactory(role=User.Role.ADMIN))
    res = client.post("/api/v1/orders/", {}, format="json")
    assert res.status_code == 405


def test_customers_are_read_only():
    client = auth_client(UserFactory(role=User.Role.ADMIN))
    res = client.post(
        "/api/v1/customers/", {"name": "x", "email": "x@y.z"}, format="json"
    )
    assert res.status_code == 405
