"""Lightweight predictive layer: linear-regression revenue projection and
z-score anomaly detection over a daily-revenue series. Pure and stateless.

Input series: list of {"period_start": "YYYY-MM-DD", "revenue": float} ordered by date.
"""
import logging
from datetime import date, timedelta

import numpy as np
from sklearn.linear_model import LinearRegression

logger = logging.getLogger(__name__)


def _fill_daily_gaps(daily_series):
    """Return a contiguous daily series, inserting zero-revenue days for any gaps.

    A daily revenue series omits days with no completed orders. Leaving those days
    out skews both the trend fit and the z-score baseline, so they are represented
    as explicit zero-revenue days between the first and last observed date.
    """
    by_date = {date.fromisoformat(d["period_start"]): float(d["revenue"]) for d in daily_series}
    if not by_date:
        return []
    day, last = min(by_date), max(by_date)
    filled = []
    while day <= last:
        filled.append({"period_start": day.isoformat(), "revenue": by_date.get(day, 0.0)})
        day += timedelta(days=1)
    return filled


def project_revenue(daily_series, horizon):
    """Fit a linear trend on daily revenue and project `horizon` days ahead."""
    if horizon < 1:
        raise ValueError(f"horizon must be a positive integer, got {horizon}")

    series = _fill_daily_gaps(daily_series)
    points = [(date.fromisoformat(d["period_start"]), d["revenue"]) for d in series]
    if len(points) < 2:
        return [], None

    ordinals = np.array([[p[0].toordinal()] for p in points])
    revenues = np.array([p[1] for p in points])

    model = LinearRegression().fit(ordinals, revenues)
    last_day = points[-1][0]
    future = np.array([[(last_day + timedelta(days=i)).toordinal()] for i in range(1, horizon + 1)])
    predictions = model.predict(future)

    forecast = [
        {
            "date": (last_day + timedelta(days=i + 1)).isoformat(),
            "predicted_revenue": round(max(float(value), 0.0), 2),
        }
        for i, value in enumerate(predictions)
    ]
    meta = {
        "slope": round(float(model.coef_[0]), 6),
        "intercept": round(float(model.intercept_), 4),
        "r2": round(float(model.score(ordinals, revenues)), 4),
    }
    return forecast, meta


def detect_anomalies(daily_series, threshold):
    """Flag days whose revenue z-score exceeds the threshold."""
    if threshold <= 0:
        raise ValueError(f"threshold must be positive, got {threshold}")

    series = _fill_daily_gaps(daily_series)
    if len(series) < 2:
        return []
    revenues = np.array([d["revenue"] for d in series])
    mean = revenues.mean()
    std = revenues.std()
    if std == 0:
        return []

    anomalies = []
    for item, revenue in zip(series, revenues, strict=True):
        z = (revenue - mean) / std
        if abs(z) > threshold:
            anomalies.append(
                {
                    "date": item["period_start"],
                    "revenue": round(float(revenue), 2),
                    "z_score": round(float(z), 2),
                }
            )
    return anomalies


def build_forecast(daily_series, horizon, threshold):
    forecast, meta = project_revenue(daily_series, horizon)
    return {
        "horizon": horizon,
        "threshold": threshold,
        "forecast": forecast,
        "anomalies": detect_anomalies(daily_series, threshold),
        "model": meta,
    }
