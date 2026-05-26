import pytest
from rest_framework.test import APIClient

from apps.users.models import User

from .factories import CustomerFactory, OrderFactory, OrderItemFactory, UserFactory

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


def test_orders_filter_by_status_customer_and_currency():
    target = OrderFactory(status="completed", currency="USD")
    OrderFactory(status="pending", currency="EUR")
    client = auth_client(UserFactory())

    assert client.get("/api/v1/orders/?status=completed").json()["data"]["count"] == 1
    assert client.get("/api/v1/orders/?currency=USD").json()["data"]["count"] == 1
    by_customer = client.get(f"/api/v1/orders/?customer={target.customer_id}")
    assert by_customer.json()["data"]["count"] == 1


def test_customers_filter_by_email():
    CustomerFactory(email="match@example.com")
    CustomerFactory(email="other@example.com")
    client = auth_client(UserFactory())

    res = client.get("/api/v1/customers/?email=match@example.com")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["count"] == 1
    assert data["results"][0]["email"] == "match@example.com"
