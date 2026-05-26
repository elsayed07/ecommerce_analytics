import pytest
from rest_framework.test import APIClient

from apps.users.models import User
from services import product_service

from .factories import CategoryFactory, UserFactory

pytestmark = pytest.mark.django_db


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_not_found_uses_error_envelope():
    res = auth_client(UserFactory()).get("/api/v1/products/999999/")

    assert res.status_code == 404
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"


def test_validation_error_uses_error_envelope():
    category = CategoryFactory()
    client = auth_client(UserFactory(role=User.Role.ADMIN))
    res = client.post(
        "/api/v1/products/", {"name": "x", "category": category.id}, format="json"
    )

    assert res.status_code == 400
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_unhandled_exception_returns_internal_error_envelope(monkeypatch):
    def boom():
        raise RuntimeError("unexpected failure with secret details")

    monkeypatch.setattr(product_service, "list_products", boom)

    client = APIClient(raise_request_exception=False)
    client.force_authenticate(user=UserFactory())
    res = client.get("/api/v1/products/")

    assert res.status_code == 500
    body = res.json()
    assert body == {
        "success": False,
        "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"},
    }
    assert "secret details" not in res.content.decode()
