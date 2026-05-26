import json
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.ingestion.models import ImportJob
from apps.orders.models import Customer, Order, OrderItem
from services import import_service

from .factories import ProductFactory

pytestmark = pytest.mark.django_db

HEADER = (
    "order_ref,order_date,status,currency,customer_email,"
    "customer_name,product_sku,quantity,unit_price\n"
)


def _run_csv(tmp_path, body, name="orders.csv"):
    path = tmp_path / name
    path.write_text(HEADER + body)
    job = ImportJob.objects.create(
        source_filename=name, file_format=ImportJob.Format.CSV
    )
    import_service.process_import_job(job, str(path))
    job.refresh_from_db()
    return job


def test_csv_import_creates_orders_normalised_to_eur(tmp_path):
    ProductFactory(sku="SKU-1")
    job = _run_csv(
        tmp_path,
        "ORD-1,2025-01-15T10:00:00,completed,USD,a@example.com,Alice,SKU-1,2,10.00\n",
    )

    assert job.status == ImportJob.Status.COMPLETED
    assert job.rows_processed == 1
    assert job.rows_failed == 0

    order = Order.objects.get(external_ref="ORD-1")
    assert order.currency == "EUR"
    assert order.source_currency == "USD"
    assert order.total == Decimal("18.40")  # 2 * 10.00 * 0.92
    assert order.source_total == Decimal("20.00")
    assert order.items.count() == 1
    assert Customer.objects.filter(email="a@example.com").exists()


def test_reimport_is_idempotent(tmp_path):
    ProductFactory(sku="SKU-1")
    body = "ORD-1,2025-01-15T10:00:00,completed,EUR,a@example.com,Alice,SKU-1,2,10.00\n"
    _run_csv(tmp_path, body)
    _run_csv(tmp_path, body)

    assert Order.objects.filter(external_ref="ORD-1").count() == 1
    assert OrderItem.objects.filter(order__external_ref="ORD-1").count() == 1


def test_bad_rows_are_quarantined(tmp_path):
    ProductFactory(sku="GOOD")
    body = (
        "ORD-A,2025-01-15T10:00:00,completed,EUR,a@example.com,Alice,GOOD,1,5.00\n"
        "ORD-B,2025-01-15T10:00:00,completed,EUR,b@example.com,Bob,UNKNOWN,1,5.00\n"
        "ORD-C,2999-01-01T10:00:00,completed,EUR,c@example.com,Carol,GOOD,1,5.00\n"
        "ORD-D,2025-01-15T10:00:00,completed,EUR,d@example.com,Dan,GOOD,0,5.00\n"
        "ORD-E,2025-01-15T10:00:00,completed,EUR,e@example.com,Eve,GOOD,1,-5.00\n"
        "ORD-F,2025-01-15T10:00:00,completed,XYZ,f@example.com,Fred,GOOD,1,5.00\n"
        ",2025-01-15T10:00:00,completed,EUR,g@example.com,Gail,GOOD,1,5.00\n"
    )
    job = _run_csv(tmp_path, body)

    assert job.rows_processed == 7
    assert job.rows_failed == 6
    assert Order.objects.filter(external_ref="ORD-A").exists()

    reasons = " ".join(job.quarantined_rows.values_list("reason", flat=True))
    assert "unknown SKU" in reasons
    assert "future order_date" in reasons
    assert "non-positive quantity" in reasons
    assert "negative unit_price" in reasons
    assert "unsupported currency" in reasons
    assert "missing required field" in reasons


def test_json_import_normalises(tmp_path):
    ProductFactory(sku="JS-1")
    data = [
        {
            "order_ref": "J-1",
            "order_date": "2025-02-01T00:00:00",
            "status": "pending",
            "currency": "GBP",
            "customer_email": "j@example.com",
            "customer_name": "Jo",
            "product_sku": "JS-1",
            "quantity": 3,
            "unit_price": "4.00",
        }
    ]
    path = tmp_path / "orders.json"
    path.write_text(json.dumps(data))
    job = ImportJob.objects.create(
        source_filename="orders.json", file_format=ImportJob.Format.JSON
    )
    import_service.process_import_job(job, str(path))
    job.refresh_from_db()

    assert job.rows_failed == 0
    order = Order.objects.get(external_ref="J-1")
    assert order.total == Decimal("14.04")  # 3 * 4.00 * 1.17


def test_malformed_json_marks_job_failed(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"not": "a list"}')
    job = ImportJob.objects.create(
        source_filename="bad.json", file_format=ImportJob.Format.JSON
    )
    import_service.process_import_job(job, str(path))
    job.refresh_from_db()

    assert job.status == ImportJob.Status.FAILED
    assert job.error_message


def test_malformed_sku_is_quarantined(tmp_path):
    ProductFactory(sku="GOOD")
    job = _run_csv(
        tmp_path,
        "ORD-X,2025-01-15T10:00:00,completed,EUR,a@example.com,Alice,bad sku!,1,5.00\n",
    )
    assert job.rows_failed == 1
    assert "malformed SKU" in job.quarantined_rows.first().reason


def test_inconsistent_order_header_is_quarantined(tmp_path):
    ProductFactory(sku="A")
    ProductFactory(sku="B")
    job = _run_csv(
        tmp_path,
        "ORD-1,2025-01-15T10:00:00,completed,EUR,a@example.com,Alice,A,1,5.00\n"
        "ORD-1,2025-01-15T10:00:00,completed,USD,a@example.com,Alice,B,1,5.00\n",
    )
    assert job.rows_failed == 1
    assert "inconsistent order header" in job.quarantined_rows.first().reason
    # The first, consistent line still persists.
    assert Order.objects.get(external_ref="ORD-1").items.count() == 1


def test_unexpected_persist_error_marks_job_failed(tmp_path, monkeypatch):
    ProductFactory(sku="SKU-1")

    def boom(records):
        raise RuntimeError("db exploded")

    monkeypatch.setattr(import_service, "_persist", boom)
    job = _run_csv(
        tmp_path,
        "ORD-1,2025-01-15T10:00:00,completed,EUR,a@example.com,Alice,SKU-1,1,5.00\n",
    )

    assert job.status == ImportJob.Status.FAILED
    assert "persist error" in job.error_message


def test_scheduled_import_processes_each_file_once(tmp_path, settings):
    settings.IMPORT_INBOX_DIR = str(tmp_path)
    ProductFactory(sku="SKU-1")
    (tmp_path / "orders.csv").write_text(
        HEADER
        + "ORD-1,2025-01-15T10:00:00,completed,EUR,a@example.com,Alice,SKU-1,1,5.00\n"
    )

    first = import_service.run_scheduled_import()
    assert len(first) == 1
    assert ImportJob.objects.count() == 1

    # Re-scan: the already-completed file is skipped, no duplicate job.
    second = import_service.run_scheduled_import()
    assert second == []
    assert ImportJob.objects.count() == 1

    # A new file produces exactly one new job.
    (tmp_path / "more.csv").write_text(
        HEADER
        + "ORD-2,2025-01-16T10:00:00,completed,EUR,b@example.com,Bob,SKU-1,1,5.00\n"
    )
    third = import_service.run_scheduled_import()
    assert len(third) == 1
    assert ImportJob.objects.count() == 2


def test_management_command_imports_file(tmp_path):
    ProductFactory(sku="SKU-1")
    path = tmp_path / "orders.csv"
    path.write_text(
        HEADER
        + "CMD-1,2025-01-15T10:00:00,completed,EUR,a@example.com,Alice,SKU-1,2,5.00\n"
    )
    call_command("import_orders", file=str(path))

    assert Order.objects.filter(external_ref="CMD-1").exists()
    assert ImportJob.objects.filter(status=ImportJob.Status.COMPLETED).exists()


def test_management_command_rejects_bad_extension(tmp_path):
    path = tmp_path / "orders.txt"
    path.write_text("nope")
    with pytest.raises(CommandError):
        call_command("import_orders", file=str(path))
