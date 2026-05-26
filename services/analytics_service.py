"""Analytics orchestration: build snapshots (source of truth) and serve cached reads.

KPIs are precomputed into AnalyticsSnapshot by build_snapshots() (nightly Celery job /
management command). The get_* readers serve only from snapshots and are cached in Redis;
the cache is cleared whenever snapshots are rebuilt.
"""
import logging
from datetime import date

from django.core.cache import cache
from django.db.models import Count, F, Sum
from django.utils import timezone

from apps.analytics.models import AnalyticsSnapshot
from apps.orders.models import Order, OrderItem
from services import revenue_service

logger = logging.getLogger(__name__)

TOP_N = 10
CACHE_TTL = 3600

REVENUE_PERIODS = {
    "daily": AnalyticsSnapshot.Type.REVENUE_DAILY,
    "weekly": AnalyticsSnapshot.Type.REVENUE_WEEKLY,
    "monthly": AnalyticsSnapshot.Type.REVENUE_MONTHLY,
}

CACHE_KEYS = [
    "analytics:revenue:daily",
    "analytics:revenue:weekly",
    "analytics:revenue:monthly",
    "analytics:top_products",
    "analytics:customers",
]


def _completed_orders():
    return Order.objects.filter(status=Order.Status.COMPLETED)


def top_products(limit=TOP_N):
    rows = list(
        OrderItem.objects.filter(order__status=Order.Status.COMPLETED)
        .values("product__sku", "product__name")
        .annotate(
            revenue=Sum(F("quantity") * F("unit_price")),
            quantity=Sum("quantity"),
        )
    )
    for row in rows:
        row["sku"] = row.pop("product__sku")
        row["name"] = row.pop("product__name")
        row["revenue"] = float(round(row["revenue"], 2))
        row["quantity"] = int(row["quantity"])

    by_revenue = sorted(rows, key=lambda r: r["revenue"], reverse=True)[:limit]
    by_quantity = sorted(rows, key=lambda r: r["quantity"], reverse=True)[:limit]
    return {"by_revenue": by_revenue, "by_quantity": by_quantity}


def customer_breakdown():
    order_counts = list(
        _completed_orders().values("customer").annotate(n=Count("id"))
    )
    total_customers = len(order_counts)
    new = sum(1 for c in order_counts if c["n"] == 1)
    returning = total_customers - new
    total_revenue = _completed_orders().aggregate(s=Sum("total"))["s"] or 0
    average_ltv = (
        float(round(total_revenue / total_customers, 2)) if total_customers else 0.0
    )
    return {
        "total_customers": total_customers,
        "new": new,
        "returning": returning,
        "average_ltv": average_ltv,
        "total_revenue": float(round(total_revenue, 2)),
    }


def _upsert(snapshot_type, period_start, period_end, metrics):
    AnalyticsSnapshot.objects.update_or_create(
        snapshot_type=snapshot_type,
        period_start=period_start,
        period_end=period_end,
        defaults={"metrics": metrics},
    )


def build_snapshots():
    """Recompute all KPI snapshots and invalidate the analytics cache."""
    today = timezone.now().date()
    counts = {"revenue_daily": 0, "revenue_weekly": 0, "revenue_monthly": 0}

    for item in revenue_service.daily_revenue():
        _upsert(
            AnalyticsSnapshot.Type.REVENUE_DAILY,
            date.fromisoformat(item["period_start"]),
            date.fromisoformat(item["period_end"]),
            item,
        )
        counts["revenue_daily"] += 1

    for item in revenue_service.weekly_revenue():
        _upsert(
            AnalyticsSnapshot.Type.REVENUE_WEEKLY,
            date.fromisoformat(item["period_start"]),
            date.fromisoformat(item["period_end"]),
            item,
        )
        counts["revenue_weekly"] += 1

    for item in revenue_service.monthly_revenue():
        _upsert(
            AnalyticsSnapshot.Type.REVENUE_MONTHLY,
            date.fromisoformat(item["period_start"]),
            date.fromisoformat(item["period_end"]),
            item,
        )
        counts["revenue_monthly"] += 1

    _upsert(AnalyticsSnapshot.Type.TOP_PRODUCTS, today, today, top_products())
    _upsert(AnalyticsSnapshot.Type.CUSTOMERS, today, today, customer_breakdown())

    cache.delete_many(CACHE_KEYS)
    logger.info("Analytics snapshots rebuilt: %s", counts)
    return counts


def _latest_metrics(snapshot_type, default):
    snapshot = (
        AnalyticsSnapshot.objects.filter(snapshot_type=snapshot_type)
        .order_by("-period_start", "-created_at")
        .first()
    )
    return snapshot.metrics if snapshot else default


def get_revenue(period="daily"):
    snapshot_type = REVENUE_PERIODS.get(period, AnalyticsSnapshot.Type.REVENUE_DAILY)
    cache_key = f"analytics:revenue:{period if period in REVENUE_PERIODS else 'daily'}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    series = list(
        AnalyticsSnapshot.objects.filter(snapshot_type=snapshot_type)
        .order_by("period_start")
        .values_list("metrics", flat=True)
    )
    cache.set(cache_key, series, CACHE_TTL)
    return series


def get_top_products():
    cached = cache.get("analytics:top_products")
    if cached is not None:
        return cached
    data = _latest_metrics(
        AnalyticsSnapshot.Type.TOP_PRODUCTS, {"by_revenue": [], "by_quantity": []}
    )
    cache.set("analytics:top_products", data, CACHE_TTL)
    return data


def get_customers():
    cached = cache.get("analytics:customers")
    if cached is not None:
        return cached
    data = _latest_metrics(
        AnalyticsSnapshot.Type.CUSTOMERS,
        {"total_customers": 0, "new": 0, "returning": 0, "average_ltv": 0.0, "total_revenue": 0.0},
    )
    cache.set("analytics:customers", data, CACHE_TTL)
    return data
