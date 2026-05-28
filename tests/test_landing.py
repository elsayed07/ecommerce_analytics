import pytest
from django.test import Client

from .factories import UserFactory

pytestmark = pytest.mark.django_db

EXPECTED_LINKS = [
    "/dashboard/",
    "/api/v1/schema/swagger-ui/",
    "/api/v1/schema/redoc/",
    "/health/",
    "/admin/",
]


def test_anonymous_user_sees_landing_page():
    response = Client().get("/")
    assert response.status_code == 200
    content = response.content.decode()
    assert "E-Commerce Analytics Dashboard" in content


def test_landing_page_includes_key_links():
    content = Client().get("/").content.decode()
    for link in EXPECTED_LINKS:
        assert link in content


def test_authenticated_user_redirected_to_dashboard():
    client = Client()
    client.force_login(UserFactory())
    response = client.get("/")
    assert response.status_code == 302
    assert response.url == "/dashboard/"


def test_github_link_shown_when_configured(settings):
    settings.GITHUB_REPO_URL = "https://github.com/example/repo"
    content = Client().get("/").content.decode()
    assert "https://github.com/example/repo" in content


def test_github_link_hidden_when_blank(settings):
    settings.GITHUB_REPO_URL = ""
    content = Client().get("/").content.decode()
    assert "Source code on GitHub" not in content
