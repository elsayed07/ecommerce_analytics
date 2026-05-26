"""Revenue/AOV/trend computations. Completed orders only. Stateless.

Returns JSON-serialisable structures (floats/ints/ISO dates) ready to store in
AnalyticsSnapshot.metrics. Aggregation is done in the database; only the sequential
rolling-window and growth calculations happen in Python.
"""
import calendar
from datetime import timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek

from apps.orders.models import Order


def _completed():
    return Order.objects.filter(status=Order.Status.COMPLETED)


def _aggregate_by(trunc):
    rows = (
        _completed()
        .annotate(period=trunc("order_date"))
        .values("period")
        .annotate(revenue=Sum("total"), orders=Count("id"))
        .order_by("period")
    )
    normalised = []
    for row in rows:
        period = row["period"]
        if hasattr(period, "date"):
            period = period.date()
        normalised.append({"period": period, "revenue": row["revenue"], "orders": row["orders"]})
    return normalised


def _aov(revenue, orders):
    return float(round(revenue / orders, 2)) if orders else 0.0


def daily_revenue():
    rows = _aggregate_by(TruncDate)
    series = []
    for row in rows:
        day = row["period"]
        series.append(
            {
                "period_start": day.isoformat(),
                "period_end": day.isoformat(),
                "revenue": float(round(row["revenue"], 2)),
                "orders": row["orders"],
                "aov": _aov(row["revenue"], row["orders"]),
            }
        )

    revenues = [row["revenue"] for row in rows]
    for i, item in enumerate(series):
        window7 = [float(v) for v in revenues[max(0, i - 6) : i + 1]]
        window30 = [float(v) for v in revenues[max(0, i - 29) : i + 1]]
        item["rolling_7"] = round(sum(window7) / len(window7), 2)
        item["rolling_30"] = round(sum(window30) / len(window30), 2)
    return series


def _with_growth(rows, period_end_for):
    series = []
    previous = None
    for row in rows:
        revenue = row["revenue"]
        growth = None
        if previous is not None and previous > 0:
            growth = float(round((revenue - previous) / previous * 100, 2))
        series.append(
            {
                "period_start": row["period"].isoformat(),
                "period_end": period_end_for(row["period"]).isoformat(),
                "revenue": float(round(revenue, 2)),
                "orders": row["orders"],
                "aov": _aov(revenue, row["orders"]),
                "growth_pct": growth,
            }
        )
        previous = revenue
    return series


def weekly_revenue():
    return _with_growth(_aggregate_by(TruncWeek), lambda d: d + timedelta(days=6))


def monthly_revenue():
    def month_end(d):
        return d.replace(day=calendar.monthrange(d.year, d.month)[1])

    return _with_growth(_aggregate_by(TruncMonth), month_end)
