import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.orders.models import Order
from apps.users.models import User

from .factories import ProductFactory, UserFactory

pytestmark = pytest.mark.django_db

HEADER = (
    "order_ref,order_date,status,currency,customer_email,"
    "customer_name,product_sku,quantity,unit_price\n"
)


def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _csv_upload(name, body):
    return SimpleUploadedFile(name, (HEADER + body).encode(), content_type="text/csv")


def test_admin_upload_processes_and_completes():
    ProductFactory(sku="API-1")
    client = auth_client(UserFactory(role=User.Role.ADMIN))
    upload = _csv_upload(
        "orders.csv",
        "ORD-API,2025-01-15T10:00:00,completed,EUR,api@example.com,API,API-1,1,9.00\n",
    )

    res = client.post("/api/v1/imports/", {"file": upload}, format="multipart")
    assert res.status_code == 202
    body = res.json()
    assert body["success"] is True
    assert body["data"]["status"] == "completed"

    job_id = body["data"]["id"]
    detail = client.get(f"/api/v1/imports/{job_id}/").json()
    assert detail["data"]["rows_processed"] == 1
    assert Order.objects.filter(external_ref="ORD-API").exists()


def test_upload_with_bad_rows_exposes_errors():
    ProductFactory(sku="OK")
    client = auth_client(UserFactory(role=User.Role.ADMIN))
    upload = _csv_upload(
        "mixed.csv",
        "OK-1,2025-01-15T10:00:00,completed,EUR,ok@example.com,Ok,OK,1,5.00\n"
        "BAD-1,2025-01-15T10:00:00,completed,EUR,bad@example.com,Bad,MISSING,1,5.00\n",
    )

    job_id = client.post(
        "/api/v1/imports/", {"file": upload}, format="multipart"
    ).json()["data"]["id"]

    errors = client.get(f"/api/v1/imports/{job_id}/errors/").json()
    assert errors["data"]["count"] == 1
    assert "unknown SKU" in errors["data"]["results"][0]["reason"]


def test_staff_cannot_upload():
    client = auth_client(UserFactory(role=User.Role.STAFF))
    upload = _csv_upload("x.csv", "")
    res = client.post("/api/v1/imports/", {"file": upload}, format="multipart")
    assert res.status_code == 403


def test_wrong_extension_rejected():
    client = auth_client(UserFactory(role=User.Role.ADMIN))
    upload = SimpleUploadedFile("orders.txt", b"hello", content_type="text/plain")
    res = client.post("/api/v1/imports/", {"file": upload}, format="multipart")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_upload_filename_is_sanitised():
    ProductFactory(sku="SAFE-1")
    client = auth_client(UserFactory(role=User.Role.ADMIN))
    upload = SimpleUploadedFile(
        "../../etc/evil.csv",
        (HEADER + "S-1,2025-01-15T10:00:00,completed,EUR,s@example.com,S,SAFE-1,1,5.00\n").encode(),
        content_type="text/csv",
    )

    res = client.post("/api/v1/imports/", {"file": upload}, format="multipart")
    assert res.status_code == 202
    name = res.json()["data"]["source_filename"]
    assert name == "evil.csv"
    assert "/" not in name and ".." not in name


def test_oversized_upload_rejected(settings):
    settings.MAX_IMPORT_BYTES = 5
    client = auth_client(UserFactory(role=User.Role.ADMIN))
    upload = SimpleUploadedFile("orders.csv", b"way-too-large", content_type="text/csv")
    res = client.post("/api/v1/imports/", {"file": upload}, format="multipart")
    assert res.status_code == 400
