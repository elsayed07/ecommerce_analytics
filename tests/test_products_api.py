import pytest
from rest_framework.test import APIClient

from apps.users.models import User
from services import product_service

from .factories import CategoryFactory, ProductFactory, UserFactory

pytestmark = pytest.mark.django_db


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_products_list_is_enveloped_and_paginated():
    ProductFactory.create_batch(3)
    res = auth_client(UserFactory()).get("/api/v1/products/")

    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["count"] == 3
    assert "results" in body["data"]


def test_products_require_authentication():
    res = APIClient().get("/api/v1/products/")
    assert res.status_code == 401


def test_products_search_and_ordering():
    category = CategoryFactory()
    ProductFactory(name="Alpha", sku="A1", price="10.00", category=category)
    ProductFactory(name="Beta", sku="B1", price="5.00", category=category)
    client = auth_client(UserFactory())

    searched = client.get("/api/v1/products/?search=Alpha").json()
    assert searched["data"]["count"] == 1

    ordered = client.get("/api/v1/products/?ordering=price").json()
    prices = [float(row["price"]) for row in ordered["data"]["results"]]
    assert prices == sorted(prices)


def test_staff_cannot_create_product():
    category = CategoryFactory()
    client = auth_client(UserFactory(role=User.Role.STAFF))
    res = client.post(
        "/api/v1/products/",
        {"name": "X", "sku": "X1", "price": "1.00", "category": category.id},
        format="json",
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "PERMISSION_DENIED"


def test_admin_can_create_product():
    category = CategoryFactory()
    client = auth_client(UserFactory(role=User.Role.ADMIN))
    res = client.post(
        "/api/v1/products/",
        {"name": "X", "sku": "X1", "price": "1.00", "category": category.id},
        format="json",
    )
    assert res.status_code == 201
    body = res.json()
    assert body["success"] is True
    assert body["data"]["sku"] == "X1"


def test_products_filter_by_category():
    cat_a = CategoryFactory()
    cat_b = CategoryFactory()
    ProductFactory(category=cat_a)
    ProductFactory(category=cat_a)
    ProductFactory(category=cat_b)
    client = auth_client(UserFactory())

    res = client.get(f"/api/v1/products/?category={cat_a.id}")
    assert res.status_code == 200
    assert res.json()["data"]["count"] == 2


def test_category_filter_by_slug():
    CategoryFactory(slug="keep-me")
    CategoryFactory(slug="other")
    client = auth_client(UserFactory())

    res = client.get("/api/v1/categories/?slug=keep-me")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["count"] == 1
    assert data["results"][0]["slug"] == "keep-me"


def test_product_create_goes_through_service(monkeypatch):
    category = CategoryFactory()
    real_create = product_service.create_product
    calls = {}

    def spy(data):
        calls["data"] = data
        return real_create(data)

    monkeypatch.setattr(product_service, "create_product", spy)
    client = auth_client(UserFactory(role=User.Role.ADMIN))
    res = client.post(
        "/api/v1/products/",
        {"name": "Svc", "sku": "SVC-1", "price": "2.00", "category": category.id},
        format="json",
    )

    assert res.status_code == 201
    assert calls["data"]["sku"] == "SVC-1"
