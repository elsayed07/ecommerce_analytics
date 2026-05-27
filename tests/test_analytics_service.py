from datetime import UTC, datetime

import pytest
from django.core.cache import cache
from django.core.management import call_command

from apps.analytics.models import AnalyticsSnapshot
from services import analytics_service, revenue_service

from .factories import (
    CustomerFactory,
    OrderFactory,
    OrderItemFactory,
    ProductFactory,
)

pytestmark = pytest.mark.django_db


def _dt(year, month, day):
    return datetime(year, month, day, 12, 0, tzinfo=UTC)


def test_revenue_counts_completed_orders_only():
    OrderFactory(status="completed", total="100.00", order_date=_dt(2025, 1, 1))
    OrderFactory(status="cancelled", total="999.00", order_date=_dt(2025, 1, 1))
    OrderFactory(status="refunded", total="999.00", order_date=_dt(2025, 1, 1))

    daily = revenue_service.daily_revenue()
    assert len(daily) == 1
    assert daily[0]["revenue"] == 100.0
    assert daily[0]["orders"] == 1


def test_daily_aov_and_rolling_average():
    OrderFactory(status="completed", total="100.00", order_date=_dt(2025, 1, 1))
    OrderFactory(status="completed", total="50.00", order_date=_dt(2025, 1, 1))

    daily = revenue_service.daily_revenue()
    assert daily[0]["revenue"] == 150.0
    assert daily[0]["aov"] == 75.0
    assert daily[0]["rolling_7"] == 150.0
    assert daily[0]["rolling_30"] == 150.0


def test_daily_revenue_includes_growth_pct():
    OrderFactory(status="completed", total="100.00", order_date=_dt(2025, 1, 1))
    OrderFactory(status="completed", total="150.00", order_date=_dt(2025, 1, 2))

    daily = revenue_service.daily_revenue()
    assert daily[0]["growth_pct"] is None
    assert daily[1]["growth_pct"] == 50.0


def test_monthly_growth_percentage():
    OrderFactory(status="completed", total="100.00", order_date=_dt(2025, 1, 15))
    OrderFactory(status="completed", total="150.00", order_date=_dt(2025, 2, 15))

    monthly = revenue_service.monthly_revenue()
    assert len(monthly) == 2
    assert monthly[0]["growth_pct"] is None
    assert monthly[1]["growth_pct"] == 50.0


def test_top_products_ranked_by_revenue_and_quantity():
    p1 = ProductFactory(sku="P1")
    p2 = ProductFactory(sku="P2")
    order = OrderFactory(status="completed", order_date=_dt(2025, 1, 1))
    OrderItemFactory(order=order, product=p1, quantity=1, unit_price="100.00")
    OrderItemFactory(order=order, product=p2, quantity=5, unit_price="10.00")
    cancelled = OrderFactory(status="cancelled", order_date=_dt(2025, 1, 1))
    OrderItemFactory(order=cancelled, product=p1, quantity=99, unit_price="100.00")

    top = analytics_service.top_products()
    assert top["by_revenue"][0]["sku"] == "P1"
    assert top["by_quantity"][0]["sku"] == "P2"


def test_customer_breakdown_new_vs_returning_and_ltv():
    c1 = CustomerFactory()
    c2 = CustomerFactory()
    OrderFactory(status="completed", customer=c1, total="100.00", order_date=_dt(2025, 1, 1))
    OrderFactory(status="completed", customer=c1, total="100.00", order_date=_dt(2025, 1, 2))
    OrderFactory(status="completed", customer=c2, total="50.00", order_date=_dt(2025, 1, 1))

    breakdown = analytics_service.customer_breakdown()
    assert breakdown["total_customers"] == 2
    assert breakdown["returning"] == 1
    assert breakdown["new"] == 1
    assert breakdown["total_revenue"] == 250.0
    assert breakdown["average_ltv"] == 125.0


def test_build_snapshots_is_idempotent_and_clears_cache():
    product = ProductFactory(sku="P1")
    order = OrderFactory(status="completed", total="100.00", order_date=_dt(2025, 1, 1))
    OrderItemFactory(order=order, product=product, quantity=1, unit_price="100.00")

    analytics_service.build_snapshots()
    first_count = AnalyticsSnapshot.objects.count()
    assert first_count > 0
    assert AnalyticsSnapshot.objects.filter(snapshot_type="forecast").exists()

    analytics_service.build_snapshots()
    assert AnalyticsSnapshot.objects.count() == first_count  # upsert, no duplicates

    assert analytics_service.get_revenue("daily")[0]["revenue"] == 100.0

    cache.set("analytics:revenue:daily", "STALE", 60)
    analytics_service.build_snapshots()
    assert cache.get("analytics:revenue:daily") is None


def test_rebuild_removes_stale_revenue_periods():
    order = OrderFactory(status="completed", total="100.00", order_date=_dt(2025, 1, 1))
    analytics_service.build_snapshots()
    assert AnalyticsSnapshot.objects.filter(snapshot_type="revenue_daily").count() == 1

    order.status = "cancelled"
    order.save()
    analytics_service.build_snapshots()
    assert AnalyticsSnapshot.objects.filter(snapshot_type="revenue_daily").count() == 0
    assert analytics_service.get_revenue("daily") == []


def test_reappearing_period_is_restored_after_being_stale():
    order = OrderFactory(status="completed", total="100.00", order_date=_dt(2025, 1, 1))
    analytics_service.build_snapshots()
    order.status = "cancelled"
    order.save()
    analytics_service.build_snapshots()
    order.status = "completed"
    order.save()
    analytics_service.build_snapshots()

    assert AnalyticsSnapshot.objects.filter(snapshot_type="revenue_daily").count() == 1
    assert analytics_service.get_revenue("daily")[0]["revenue"] == 100.0


def test_changed_horizon_leaves_single_active_forecast(settings):
    OrderFactory(status="completed", total="100.00", order_date=_dt(2025, 1, 1))
    OrderFactory(status="completed", total="120.00", order_date=_dt(2025, 1, 2))

    settings.FORECAST_HORIZON_DAYS = 30
    analytics_service.build_snapshots()
    settings.FORECAST_HORIZON_DAYS = 14
    analytics_service.build_snapshots()

    assert AnalyticsSnapshot.objects.filter(snapshot_type="forecast").count() == 1
    forecast = analytics_service.get_forecast()
    assert forecast["horizon"] == 14
    assert len(forecast["forecast"]) == 14


def test_snapshot_task_and_command_build_snapshots():
    from tasks.analytics_snapshot import run_analytics_snapshot

    OrderFactory(status="completed", total="10.00", order_date=_dt(2025, 1, 1))
    result = run_analytics_snapshot.delay()
    assert result.get()["revenue_daily"] == 1

    OrderFactory(status="completed", total="20.00", order_date=_dt(2025, 1, 2))
    call_command("build_snapshots")
    assert AnalyticsSnapshot.objects.filter(snapshot_type="revenue_daily").count() == 2
