"""Analytics orchestration: build snapshots (source of truth) and serve cached reads.

KPIs are precomputed into AnalyticsSnapshot by build_snapshots() (nightly Celery job /
management command). The get_* readers serve only from snapshots and are cached in Redis;
the cache is cleared whenever snapshots are rebuilt.
"""
import logging
from datetime import date, timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, F, Sum
from django.utils import timezone

from apps.analytics.models import AnalyticsSnapshot
from apps.orders.models import Order, OrderItem
from services import forecasting_service, revenue_service

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
    "analytics:forecast",
]


def _completed_orders():
    return Order.objects.filter(status=Order.Status.COMPLETED)


def _format_product_rows(rows):
    formatted = []
    for row in rows:
        formatted.append(
            {
                "sku": row["product__sku"],
                "name": row["product__name"],
                "revenue": float(round(row["revenue"], 2)),
                "quantity": int(row["quantity"]),
            }
        )
    return formatted


def top_products(limit=TOP_N):
    base = (
        OrderItem.objects.filter(order__status=Order.Status.COMPLETED)
        .values("product__sku", "product__name")
        .annotate(revenue=Sum(F("quantity") * F("unit_price")), quantity=Sum("quantity"))
    )
    return {
        "by_revenue": _format_product_rows(base.order_by("-revenue")[:limit]),
        "by_quantity": _format_product_rows(base.order_by("-quantity")[:limit]),
    }


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
    """Create/update a snapshot, restoring a previously soft-deleted period if present."""
    obj = AnalyticsSnapshot.all_objects.filter(
        snapshot_type=snapshot_type, period_start=period_start, period_end=period_end
    ).first()
    if obj is not None:
        obj.metrics = metrics
        obj.is_deleted = False
        obj.save()
    else:
        obj = AnalyticsSnapshot.objects.create(
            snapshot_type=snapshot_type,
            period_start=period_start,
            period_end=period_end,
            metrics=metrics,
        )
    return obj


def _sync_revenue(snapshot_type, items):
    """Upsert the fresh period set and drop periods that no longer exist in source data."""
    fresh_pks = []
    for item in items:
        obj = _upsert(
            snapshot_type,
            date.fromisoformat(item["period_start"]),
            date.fromisoformat(item["period_end"]),
            item,
        )
        fresh_pks.append(obj.pk)
    AnalyticsSnapshot.objects.filter(snapshot_type=snapshot_type).exclude(
        pk__in=fresh_pks
    ).delete()
    return len(fresh_pks)


def build_snapshots():
    """Recompute all KPI snapshots and invalidate the analytics cache."""
    today = timezone.now().date()

    daily = revenue_service.daily_revenue()

    with transaction.atomic():
        counts = {
            "revenue_daily": _sync_revenue(AnalyticsSnapshot.Type.REVENUE_DAILY, daily),
            "revenue_weekly": _sync_revenue(
                AnalyticsSnapshot.Type.REVENUE_WEEKLY, revenue_service.weekly_revenue()
            ),
            "revenue_monthly": _sync_revenue(
                AnalyticsSnapshot.Type.REVENUE_MONTHLY, revenue_service.monthly_revenue()
            ),
        }
        _upsert(AnalyticsSnapshot.Type.TOP_PRODUCTS, today, today, top_products())
        _upsert(AnalyticsSnapshot.Type.CUSTOMERS, today, today, customer_breakdown())

        horizon = settings.FORECAST_HORIZON_DAYS
        forecast = forecasting_service.build_forecast(
            daily, horizon, settings.ANOMALY_Z_THRESHOLD
        )
        _upsert(
            AnalyticsSnapshot.Type.FORECAST,
            today,
            today + timedelta(days=horizon),
            forecast,
        )

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


def get_forecast():
    cached = cache.get("analytics:forecast")
    if cached is not None:
        return cached
    data = _latest_metrics(
        AnalyticsSnapshot.Type.FORECAST,
        {"forecast": [], "anomalies": [], "model": None},
    )
    cache.set("analytics:forecast", data, CACHE_TTL)
    return data
