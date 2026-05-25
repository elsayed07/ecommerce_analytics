import pytest
from rest_framework.test import APIClient

from apps.users.models import User

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
