"""ETL pipeline: validate, normalise, and idempotently load order-line imports.

Each input row is one order line. Customers are upserted by email; products must
already exist in the catalog (unknown SKUs are quarantined). Amounts are normalised
to EUR. All logic is stateless and free of request/Response objects.
"""
import csv
import json
import logging
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.ingestion.models import ErrorQuarantine, ImportJob
from apps.orders.models import Customer, Order, OrderItem
from apps.products.models import Product

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = (
    "order_ref",
    "order_date",
    "status",
    "currency",
    "customer_email",
    "customer_name",
    "product_sku",
    "quantity",
    "unit_price",
)

CENTS = Decimal("0.01")


def _read_rows(file_path, file_format):
    if file_format == ImportJob.Format.CSV:
        with open(file_path, newline="", encoding="utf-8-sig") as fh:
            return list(csv.DictReader(fh))
    with open(file_path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError("JSON import must be a list of objects")
    return data


def _parse_order_date(value):
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _validate_and_normalise(row, products, seen, fx_rates):
    """Return (record, None) for a valid row or (None, reason) for a bad one."""
    for field in REQUIRED_FIELDS:
        if not str(row.get(field, "")).strip():
            return None, f"missing required field: {field}"

    try:
        order_date = _parse_order_date(row["order_date"])
    except (ValueError, TypeError):
        return None, "invalid order_date"
    if order_date > timezone.now():
        return None, "future order_date"

    status = str(row["status"]).strip().lower()
    if status not in Order.Status.values:
        return None, f"invalid status: {status}"

    currency = str(row["currency"]).strip().upper()
    if currency not in fx_rates:
        return None, f"unsupported currency: {currency}"

    try:
        quantity = int(str(row["quantity"]).strip())
    except (ValueError, TypeError):
        return None, "invalid quantity"
    if quantity <= 0:
        return None, "non-positive quantity"

    try:
        unit_price = Decimal(str(row["unit_price"]).strip())
    except (InvalidOperation, ValueError, TypeError):
        return None, "invalid unit_price"
    if unit_price < 0:
        return None, "negative unit_price"

    sku = str(row["product_sku"]).strip()
    product = products.get(sku)
    if product is None:
        return None, f"unknown SKU: {sku}"

    order_ref = str(row["order_ref"]).strip()
    dedupe_key = (order_ref, sku)
    if dedupe_key in seen:
        return None, "duplicate (order_ref, product_sku) line"
    seen.add(dedupe_key)

    rate = fx_rates[currency]
    record = {
        "order_ref": order_ref,
        "order_date": order_date,
        "status": status,
        "currency": currency,
        "customer_email": str(row["customer_email"]).strip(),
        "customer_name": str(row["customer_name"]).strip(),
        "product": product,
        "quantity": quantity,
        "unit_price_source": unit_price,
        "unit_price_eur": (unit_price * rate).quantize(CENTS),
    }
    return record, None


def _persist_order(order_ref, lines):
    first = lines[0]
    customer, _ = Customer.objects.update_or_create(
        email=first["customer_email"],
        defaults={"name": first["customer_name"]},
    )
    source_total = sum(
        (line["unit_price_source"] * line["quantity"] for line in lines), Decimal("0")
    ).quantize(CENTS)
    total_eur = sum(
        (line["unit_price_eur"] * line["quantity"] for line in lines), Decimal("0")
    ).quantize(CENTS)

    order, _ = Order.objects.update_or_create(
        external_ref=order_ref,
        defaults={
            "customer": customer,
            "order_date": first["order_date"],
            "status": first["status"],
            "total": total_eur,
            "currency": "EUR",
            "source_currency": first["currency"],
            "source_total": source_total,
        },
    )
    for line in lines:
        OrderItem.objects.update_or_create(
            order=order,
            product=line["product"],
            defaults={"quantity": line["quantity"], "unit_price": line["unit_price_eur"]},
        )


def process_import_job(job, file_path):
    """Run the full pipeline for one ImportJob against a file on disk."""
    job.status = ImportJob.Status.RUNNING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at", "updated_at"])
    logger.info("Import job %s started: %s", job.pk, job.source_filename)

    fx_rates = settings.FX_RATES_TO_EUR
    products = {p.sku: p for p in Product.objects.all()}

    try:
        rows = _read_rows(file_path, job.file_format)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        job.status = ImportJob.Status.FAILED
        job.error_message = f"Could not parse file: {exc}"
        job.finished_at = timezone.now()
        job.duration_seconds = (job.finished_at - job.started_at).total_seconds()
        job.save()
        logger.error("Import job %s failed to parse: %s", job.pk, exc)
        return job

    seen = set()
    valid_by_order = defaultdict(list)
    rows_failed = 0

    for row_number, row in enumerate(rows, start=1):
        record, reason = _validate_and_normalise(row, products, seen, fx_rates)
        if reason:
            ErrorQuarantine.objects.create(
                import_job=job, row_number=row_number, reason=reason, raw_data=dict(row)
            )
            rows_failed += 1
        else:
            valid_by_order[record["order_ref"]].append(record)

    for order_ref, lines in valid_by_order.items():
        try:
            with transaction.atomic():
                _persist_order(order_ref, lines)
        except Exception as exc:  # noqa: BLE001 - quarantine, never silently drop
            logger.warning("Order %s failed to persist: %s", order_ref, exc)
            ErrorQuarantine.objects.create(
                import_job=job,
                row_number=0,
                reason=f"persist error for order {order_ref}: {exc}",
                raw_data={"order_ref": order_ref},
            )
            rows_failed += len(lines)

    job.rows_processed = len(rows)
    job.rows_failed = rows_failed
    job.status = ImportJob.Status.COMPLETED
    job.finished_at = timezone.now()
    job.duration_seconds = (job.finished_at - job.started_at).total_seconds()
    job.save()
    logger.info(
        "Import job %s completed: %s processed, %s failed",
        job.pk,
        job.rows_processed,
        job.rows_failed,
    )
    return job


def run_scheduled_import():
    """Scan the inbox directory and process every CSV/JSON file (idempotent)."""
    from pathlib import Path

    inbox = Path(settings.IMPORT_INBOX_DIR)
    if not inbox.exists():
        logger.info("Import inbox %s does not exist; nothing to do", inbox)
        return []

    jobs = []
    for path in sorted(inbox.iterdir()):
        suffix = path.suffix.lower()
        if suffix not in (".csv", ".json"):
            continue
        job = ImportJob.objects.create(
            source_filename=path.name,
            file_format=ImportJob.Format.CSV if suffix == ".csv" else ImportJob.Format.JSON,
        )
        jobs.append(process_import_job(job, str(path)))
    return jobs
