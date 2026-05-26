"""ETL pipeline: validate, normalise, and idempotently load order-line imports.

Each input row is one order line. Customers are upserted by email; products must
already exist in the catalog (unknown SKUs are quarantined). Amounts are normalised
to EUR. All logic is stateless and free of request/Response objects.
"""
import csv
import hashlib
import json
import logging
import os
import re
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.text import get_valid_filename

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
SKU_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ORDER_FIELDS = [
    "customer",
    "order_date",
    "status",
    "currency",
    "source_currency",
    "total",
    "source_total",
    "updated_at",
]


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


def _file_checksum(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_and_normalise(row, products, seen, headers, fx_rates):
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
    if not SKU_PATTERN.match(sku):
        return None, f"malformed SKU: {sku}"
    product = products.get(sku)
    if product is None:
        return None, f"unknown SKU: {sku}"

    order_ref = str(row["order_ref"]).strip()
    customer_email = str(row["customer_email"]).strip()

    # Repeated order_ref lines must share the same order-level header.
    header = (customer_email, order_date.isoformat(), status, currency)
    if order_ref in headers:
        if headers[order_ref] != header:
            return None, "inconsistent order header for order_ref"
    else:
        headers[order_ref] = header

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
        "customer_email": customer_email,
        "customer_name": str(row["customer_name"]).strip(),
        "product": product,
        "quantity": quantity,
        "unit_price_source": unit_price,
        "unit_price_eur": (unit_price * rate).quantize(CENTS),
    }
    return record, None


def _upsert_customers(records, now):
    names = {}
    for record in records:
        names[record["customer_email"]] = record["customer_name"]

    existing = {c.email: c for c in Customer.objects.filter(email__in=names)}
    to_create = [
        Customer(email=email, name=name)
        for email, name in names.items()
        if email not in existing
    ]
    Customer.objects.bulk_create(to_create)

    to_update = []
    for customer in existing.values():
        if customer.name != names[customer.email]:
            customer.name = names[customer.email]
            customer.updated_at = now
            to_update.append(customer)
    if to_update:
        Customer.objects.bulk_update(to_update, ["name", "updated_at"])

    return {c.email: c for c in Customer.objects.filter(email__in=names)}


def _upsert_orders(order_groups, customers, now):
    headers = {}
    for order_ref, lines in order_groups.items():
        first = lines[0]
        headers[order_ref] = {
            "customer": customers[first["customer_email"]],
            "order_date": first["order_date"],
            "status": first["status"],
            "currency": "EUR",
            "source_currency": first["currency"],
            "total": sum(
                (line["unit_price_eur"] * line["quantity"] for line in lines),
                Decimal("0"),
            ).quantize(CENTS),
            "source_total": sum(
                (line["unit_price_source"] * line["quantity"] for line in lines),
                Decimal("0"),
            ).quantize(CENTS),
        }

    existing = {o.external_ref: o for o in Order.objects.filter(external_ref__in=order_groups)}
    to_create = [
        Order(external_ref=ref, **header)
        for ref, header in headers.items()
        if ref not in existing
    ]
    Order.objects.bulk_create(to_create)

    to_update = []
    for ref, order in existing.items():
        for field, value in headers[ref].items():
            setattr(order, field, value)
        order.updated_at = now
        to_update.append(order)
    if to_update:
        Order.objects.bulk_update(to_update, ORDER_FIELDS)

    return {o.external_ref: o for o in Order.objects.filter(external_ref__in=order_groups)}


def _upsert_order_items(order_groups, orders, now):
    desired = {}
    for order_ref, lines in order_groups.items():
        order = orders[order_ref]
        for line in lines:
            desired[(order.id, line["product"].id)] = line

    existing = {
        (item.order_id, item.product_id): item
        for item in OrderItem.objects.filter(order__in=orders.values())
    }

    to_create, to_update = [], []
    for (order_id, product_id), line in desired.items():
        item = existing.get((order_id, product_id))
        if item is None:
            to_create.append(
                OrderItem(
                    order_id=order_id,
                    product_id=product_id,
                    quantity=line["quantity"],
                    unit_price=line["unit_price_eur"],
                )
            )
        else:
            item.quantity = line["quantity"]
            item.unit_price = line["unit_price_eur"]
            item.updated_at = now
            to_update.append(item)

    OrderItem.objects.bulk_create(to_create)
    if to_update:
        OrderItem.objects.bulk_update(to_update, ["quantity", "unit_price", "updated_at"])


def _persist(records):
    """Idempotently load valid records using bulk operations (no per-row inserts)."""
    if not records:
        return
    now = timezone.now()
    order_groups = defaultdict(list)
    for record in records:
        order_groups[record["order_ref"]].append(record)

    with transaction.atomic():
        customers = _upsert_customers(records, now)
        orders = _upsert_orders(order_groups, customers, now)
        _upsert_order_items(order_groups, orders, now)


def _finalise(job, status, rows_processed, rows_failed, error_message=""):
    job.status = status
    job.rows_processed = rows_processed
    job.rows_failed = rows_failed
    job.error_message = error_message
    job.finished_at = timezone.now()
    job.duration_seconds = (job.finished_at - job.started_at).total_seconds()
    job.save()
    return job


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
        logger.error("Import job %s failed to parse: %s", job.pk, exc)
        return _finalise(
            job, ImportJob.Status.FAILED, 0, 0, f"Could not parse file: {exc}"
        )

    seen, headers, valid = set(), {}, []
    rows_failed = 0
    for row_number, row in enumerate(rows, start=1):
        record, reason = _validate_and_normalise(row, products, seen, headers, fx_rates)
        if reason:
            ErrorQuarantine.objects.create(
                import_job=job, row_number=row_number, reason=reason, raw_data=dict(row)
            )
            rows_failed += 1
        else:
            valid.append(record)

    try:
        _persist(valid)
    except Exception as exc:  # noqa: BLE001 - surface as a failed job, never silent
        logger.error("Import job %s failed during persist: %s", job.pk, exc)
        return _finalise(
            job, ImportJob.Status.FAILED, len(rows), rows_failed, f"persist error: {exc}"
        )

    logger.info(
        "Import job %s completed: %s processed, %s failed", job.pk, len(rows), rows_failed
    )
    return _finalise(job, ImportJob.Status.COMPLETED, len(rows), rows_failed)


def create_import_job_from_upload(uploaded_file, user):
    """Persist an uploaded file, create its ImportJob, and dispatch processing."""
    from tasks.nightly_import import process_import_job_task

    safe_name = get_valid_filename(os.path.basename(uploaded_file.name))
    ext = os.path.splitext(safe_name)[1].lower()
    file_format = ImportJob.Format.CSV if ext == ".csv" else ImportJob.Format.JSON

    job = ImportJob.objects.create(
        source_filename=safe_name, file_format=file_format, created_by=user
    )

    import_dir = os.path.join(settings.MEDIA_ROOT, "imports")
    os.makedirs(import_dir, exist_ok=True)
    dest = os.path.join(import_dir, f"{job.pk}_{safe_name}")
    with open(dest, "wb") as out:
        for chunk in uploaded_file.chunks():
            out.write(chunk)

    job.source_checksum = _file_checksum(dest)
    job.save(update_fields=["source_checksum", "updated_at"])

    process_import_job_task.delay(job.pk, dest)
    job.refresh_from_db()
    return job


def run_scheduled_import():
    """Process each new CSV/JSON file in the inbox once (skip already-imported files)."""
    inbox = Path(settings.IMPORT_INBOX_DIR)
    if not inbox.exists():
        logger.info("Import inbox %s does not exist; nothing to do", inbox)
        return []

    jobs = []
    for path in sorted(inbox.iterdir()):
        suffix = path.suffix.lower()
        if suffix not in (".csv", ".json"):
            continue
        checksum = _file_checksum(path)
        if ImportJob.objects.filter(
            source_checksum=checksum, status=ImportJob.Status.COMPLETED
        ).exists():
            logger.info("Skipping already-imported file: %s", path.name)
            continue
        job = ImportJob.objects.create(
            source_filename=path.name,
            file_format=ImportJob.Format.CSV if suffix == ".csv" else ImportJob.Format.JSON,
            source_checksum=checksum,
        )
        jobs.append(process_import_job(job, str(path)))
    return jobs
