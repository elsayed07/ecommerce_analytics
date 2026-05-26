import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_openapi_schema_is_served():
    res = APIClient().get("/api/v1/schema/")
    assert res.status_code == 200


def test_redoc_is_served():
    res = APIClient().get("/api/v1/schema/redoc/")
    assert res.status_code == 200
