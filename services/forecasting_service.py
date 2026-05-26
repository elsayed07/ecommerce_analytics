"""Lightweight predictive layer: linear-regression revenue projection and
z-score anomaly detection over a daily-revenue series. Pure and stateless.

Input series: list of {"period_start": "YYYY-MM-DD", "revenue": float} ordered by date.
"""
import logging
from datetime import date, timedelta

import numpy as np
from sklearn.linear_model import LinearRegression

logger = logging.getLogger(__name__)


def project_revenue(daily_series, horizon):
    """Fit a linear trend on daily revenue and project `horizon` days ahead."""
    points = [(date.fromisoformat(d["period_start"]), float(d["revenue"])) for d in daily_series]
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
    if len(daily_series) < 2:
        return []
    revenues = np.array([float(d["revenue"]) for d in daily_series])
    mean = revenues.mean()
    std = revenues.std()
    if std == 0:
        return []

    anomalies = []
    for item, revenue in zip(daily_series, revenues, strict=True):
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
