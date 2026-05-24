import pytest
from rest_framework.test import APIClient

from .factories import UserFactory

pytestmark = pytest.mark.django_db


def test_login_returns_token_pair():
    UserFactory(username="alice", password="secret12345")
    client = APIClient()

    response = client.post(
        "/api/v1/auth/login/",
        {"username": "alice", "password": "secret12345"},
        format="json",
    )

    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data


def test_refresh_returns_new_access():
    UserFactory(username="bob", password="secret12345")
    client = APIClient()
    login = client.post(
        "/api/v1/auth/login/",
        {"username": "bob", "password": "secret12345"},
        format="json",
    )

    response = client.post(
        "/api/v1/auth/refresh/",
        {"refresh": login.data["refresh"]},
        format="json",
    )

    assert response.status_code == 200
    assert "access" in response.data


def test_login_with_bad_credentials_fails():
    UserFactory(username="carol", password="secret12345")
    client = APIClient()

    response = client.post(
        "/api/v1/auth/login/",
        {"username": "carol", "password": "wrong"},
        format="json",
    )

    assert response.status_code == 401
