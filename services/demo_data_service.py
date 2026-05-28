"""Synthetic demo-data generation for development, screenshots, and interview demos.

Generation is split into a pure, deterministic builder (`_build_dataset`, no DB) and a
bulk persister (`_persist`). Given a seed the builder is fully reproducible. Persistence
is idempotent: catalog/customers upsert and orders/items use ignore_conflicts, so the
same seed can be re-run without creating duplicates. Not for production data.
"""
import logging
import random
import time
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from apps.orders.models import Customer, Order, OrderItem
from apps.products.models import Category, Inventory, Product

logger = logging.getLogger(__name__)

DEFAULT_ORDERS = 1000
BATCH_SIZE = 2000
DATE_RANGE_DAYS = 365
RETURNING_RATIO = 0.30
ORDERS_PER_CUSTOMER = 1.9  # tuned so ~30% of customers place more than one order
MAX_ITEMS_PER_ORDER = 4
CENTS = Decimal("0.01")

CATEGORIES = [
    ("Totes", "totes"),
    ("Clutches", "clutches"),
    ("Crossbody", "crossbody"),
    ("Accessories", "accessories"),
]

# (sku, name, category_slug, unit_price_eur)
PRODUCTS = [
    ("BAG-001", "Margherita Tote", "totes", "65.00"),
    ("BAG-002", "Limone Tote", "totes", "72.00"),
    ("BAG-003", "Giardino Tote", "totes", "89.00"),
    ("BAG-004", "Perla Clutch", "clutches", "38.00"),
    ("BAG-005", "Onda Clutch", "clutches", "42.00"),
    ("BAG-006", "Sole Crossbody", "crossbody", "55.00"),
    ("BAG-007", "Conchiglia Crossbody", "crossbody", "59.00"),
    ("BAG-008", "Mini Perla Clutch", "clutches", "29.00"),
    ("ACC-001", "Wooden Handle Set", "accessories", "18.00"),
    ("ACC-002", "Cotton Care Kit", "accessories", "12.00"),
]

STATUS_WEIGHTS = [("completed", 90), ("pending", 5), ("cancelled", 3), ("refunded", 2)]
QUANTITY_CHOICES = ([1, 2, 3, 4, 5], [50, 25, 13, 8, 4])

FIRST_NAMES = [
    "Giulia", "Marco", "Sofia", "Luca", "Chiara", "Matteo", "Anna", "Davide",
    "Elena", "Francesco", "Martina", "Alessio", "Sara", "Nicolo", "Greta",
    "Lorenzo", "Beatrice", "Tommaso", "Aurora", "Simone",
]
LAST_NAMES = [
    "Rossi", "Bianchi", "Ferrari", "Esposito", "Romano", "Colombo", "Ricci",
    "Marino", "Greco", "Bruno", "Gallo", "Conti", "De Luca", "Mancini",
]


def _day_weight(day):
    """Relative sales weight for a calendar day (holiday + weekend seasonality)."""
    weight = 1.0
    if day.month in (11, 12):  # holiday shopping season
        weight *= 2.2
    if day.month == 11 and day.day >= 24:  # Black Friday / Cyber week
        weight *= 1.8
    if day.month in (6, 7):  # summer uplift
        weight *= 1.3
    if day.weekday() >= 5:  # weekends
        weight *= 1.25
    return weight


def _build_dataset(orders, seed):
    """Build a deterministic in-memory dataset (no DB access)."""
    rng = random.Random(seed)
    run_tag = str(seed) if seed is not None else uuid4().hex[:8]

    today = date.today()
    days = [today - timedelta(days=DATE_RANGE_DAYS - i) for i in range(DATE_RANGE_DAYS + 1)]
    day_weights = [_day_weight(d) for d in days]

    inventory = [{"sku": sku, "quantity": rng.randint(20, 300)} for sku, *_ in PRODUCTS]

    pool_size = max(2, round(orders / ORDERS_PER_CUSTOMER))
    customers = [
        {
            "name": f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
            "email": f"demo.{run_tag}.c{i}@example.com",
        }
        for i in range(pool_size)
    ]
    returning_count = max(1, round(RETURNING_RATIO * pool_size))
    returning = customers[:returning_count]
    one_time = customers[returning_count:]

    # one order per one-time customer, the rest spread across returning customers
    assignments = [c["email"] for c in one_time]
    repeat_pool = returning or customers
    while len(assignments) < orders:
        assignments.append(rng.choice(repeat_pool)["email"])
    rng.shuffle(assignments)
    assignments = assignments[:orders]
    used_emails = set(assignments)

    statuses = rng.choices(
        [s for s, _ in STATUS_WEIGHTS], weights=[w for _, w in STATUS_WEIGHTS], k=orders
    )
    order_days = rng.choices(days, weights=day_weights, k=orders)

    order_rows, item_rows = [], []
    for i in range(orders):
        ref = f"DEMO-{run_tag}-{i:06d}"
        day = order_days[i]
        when = datetime(
            day.year, day.month, day.day,
            rng.randint(8, 21), rng.randint(0, 59), tzinfo=UTC,
        )
        chosen = rng.sample(PRODUCTS, k=rng.randint(1, MAX_ITEMS_PER_ORDER))
        total = Decimal("0")
        for sku, _name, _cat, price in chosen:
            quantity = rng.choices(QUANTITY_CHOICES[0], weights=QUANTITY_CHOICES[1])[0]
            total += Decimal(price) * quantity
            item_rows.append(
                {"order_ref": ref, "product_sku": sku, "quantity": quantity, "unit_price": price}
            )
        total = total.quantize(CENTS)
        order_rows.append(
            {
                "external_ref": ref,
                "customer_email": assignments[i],
                "order_date": when.isoformat(),
                "status": statuses[i],
                "currency": "EUR",
                "source_currency": "EUR",
                "total": str(total),
                "source_total": str(total),
            }
        )

    return {
        "run_tag": run_tag,
        "categories": [{"name": n, "slug": s} for n, s in CATEGORIES],
        "products": [
            {"sku": sku, "name": name, "category_slug": cat, "price": price}
            for sku, name, cat, price in PRODUCTS
        ],
        "inventory": inventory,
        "customers": [c for c in customers if c["email"] in used_emails],
        "orders": order_rows,
        "items": item_rows,
    }


def _get_or_restore(manager, defaults, **lookup):
    """get_or_create over all_objects, restoring a soft-deleted match so unique
    fields (slug/sku/product) are reused rather than colliding."""
    obj, created = manager.get_or_create(defaults=defaults, **lookup)
    if not created and obj.is_deleted:
        obj.is_deleted = False
        obj.save(update_fields=["is_deleted", "updated_at"])
    return obj


def _restore_soft_deleted(manager, objs, now):
    """Bulk-restore any soft-deleted rows among reused objects."""
    deleted = [o for o in objs if o.is_deleted]
    if not deleted:
        return
    for obj in deleted:
        obj.is_deleted = False
        obj.updated_at = now
    manager.bulk_update(deleted, ["is_deleted", "updated_at"])


def _persist(data):
    """Bulk-load a dataset idempotently and return per-model counts."""
    now = timezone.now()

    category_map = {}
    for row in data["categories"]:
        category_map[row["slug"]] = _get_or_restore(
            Category.all_objects, {"name": row["name"]}, slug=row["slug"]
        )

    product_map = {}
    for row in data["products"]:
        product_map[row["sku"]] = _get_or_restore(
            Product.all_objects,
            {
                "name": row["name"],
                "category": category_map[row["category_slug"]],
                "price": Decimal(row["price"]),
            },
            sku=row["sku"],
        )

    for row in data["inventory"]:
        _get_or_restore(
            Inventory.all_objects,
            {"quantity": row["quantity"]},
            product=product_map[row["sku"]],
        )

    names_by_email = {c["email"]: c["name"] for c in data["customers"]}
    existing_emails = set(
        Customer.all_objects.filter(email__in=names_by_email).values_list("email", flat=True)
    )
    Customer.objects.bulk_create(
        [Customer(email=e, name=n) for e, n in names_by_email.items() if e not in existing_emails],
        batch_size=BATCH_SIZE,
        ignore_conflicts=True,
    )
    customer_map = {c.email: c for c in Customer.all_objects.filter(email__in=names_by_email)}
    _restore_soft_deleted(Customer.all_objects, customer_map.values(), now)

    order_objs = [
        Order(
            external_ref=row["external_ref"],
            customer=customer_map[row["customer_email"]],
            order_date=datetime.fromisoformat(row["order_date"]),
            status=row["status"],
            total=Decimal(row["total"]),
            currency=row["currency"],
            source_currency=row["source_currency"],
            source_total=Decimal(row["source_total"]),
        )
        for row in data["orders"]
    ]
    Order.objects.bulk_create(order_objs, batch_size=BATCH_SIZE, ignore_conflicts=True)
    refs = [row["external_ref"] for row in data["orders"]]
    order_map = {o.external_ref: o for o in Order.all_objects.filter(external_ref__in=refs)}
    _restore_soft_deleted(Order.all_objects, order_map.values(), now)

    item_objs = [
        OrderItem(
            order=order_map[row["order_ref"]],
            product=product_map[row["product_sku"]],
            quantity=row["quantity"],
            unit_price=Decimal(row["unit_price"]),
        )
        for row in data["items"]
    ]
    OrderItem.objects.bulk_create(item_objs, batch_size=BATCH_SIZE, ignore_conflicts=True)

    return {
        "categories": len(category_map),
        "products": len(product_map),
        "inventory": len(data["inventory"]),
        "customers": len(names_by_email),
        "orders": len(order_map),
        "order_items": len(item_objs),
    }


def generate_demo_data(orders=DEFAULT_ORDERS, seed=None):
    """Generate and persist a realistic synthetic dataset; return per-model counts."""
    started = time.monotonic()
    logger.info("Demo data generation started: orders=%s seed=%s", orders, seed)

    data = _build_dataset(orders, seed)
    with transaction.atomic():
        counts = _persist(data)

    duration = time.monotonic() - started
    logger.info("Demo data generation finished in %.2fs: %s", duration, counts)
    return counts
