from datetime import date, timedelta

import pytest

from services import forecasting_service


def _series(values, start=date(2025, 1, 1)):
    return [
        {"period_start": (start + timedelta(days=i)).isoformat(), "revenue": float(v)}
        for i, v in enumerate(values)
    ]


def test_rising_trend_projects_upward():
    series = _series([10, 20, 30, 40, 50])
    forecast, meta = forecasting_service.project_revenue(series, horizon=30)

    assert len(forecast) == 30
    assert meta["slope"] > 0
    assert forecast[-1]["predicted_revenue"] > 50
    # forecast starts the day after the last actual
    assert forecast[0]["date"] == "2025-01-06"


def test_declining_trend_clamps_at_zero():
    series = _series([100, 80, 60, 40, 20])
    forecast, _ = forecasting_service.project_revenue(series, horizon=30)

    assert all(point["predicted_revenue"] >= 0 for point in forecast)
    assert forecast[-1]["predicted_revenue"] == 0.0


def test_insufficient_data_returns_empty_forecast():
    forecast, meta = forecasting_service.project_revenue(_series([42]), horizon=30)
    assert forecast == []
    assert meta is None


def test_spike_is_flagged_as_anomaly():
    series = _series([100] * 20 + [1000])
    anomalies = forecasting_service.detect_anomalies(series, threshold=3.0)

    assert len(anomalies) == 1
    assert anomalies[0]["revenue"] == 1000.0
    assert abs(anomalies[0]["z_score"]) > 3.0


def test_flat_series_has_no_anomalies():
    anomalies = forecasting_service.detect_anomalies(_series([100] * 10), threshold=3.0)
    assert anomalies == []


def test_missing_days_are_filled_with_zero_before_fitting():
    # Two observed days a week apart: gap-filling inserts 5 zero-revenue days,
    # so the fit/forecast span the full calendar range, not just observed days.
    series = [
        {"period_start": "2025-01-01", "revenue": 100.0},
        {"period_start": "2025-01-08", "revenue": 100.0},
    ]
    forecast, meta = forecasting_service.project_revenue(series, horizon=3)

    assert meta is not None  # 8 contiguous days, not 2 sparse points
    assert forecast[0]["date"] == "2025-01-09"


def test_zero_filled_gap_lowers_anomaly_baseline():
    # A lone high day surrounded by absent (zero) days is an anomaly once gaps fill.
    series = [{"period_start": "2025-01-01", "revenue": 1000.0}]
    series += [{"period_start": (date(2025, 1, 2) + timedelta(days=i)).isoformat(),
                "revenue": 100.0} for i in range(20)]
    anomalies = forecasting_service.detect_anomalies(series, threshold=3.0)

    assert any(a["date"] == "2025-01-01" for a in anomalies)


def test_non_positive_horizon_is_rejected():
    with pytest.raises(ValueError, match="horizon"):
        forecasting_service.project_revenue(_series([10, 20, 30]), horizon=0)
    with pytest.raises(ValueError, match="horizon"):
        forecasting_service.project_revenue(_series([10, 20, 30]), horizon=-5)


def test_non_positive_threshold_is_rejected():
    with pytest.raises(ValueError, match="threshold"):
        forecasting_service.detect_anomalies(_series([10, 20, 30]), threshold=0)


def test_build_forecast_combines_projection_and_anomalies():
    series = _series([100] * 20 + [1000])
    result = forecasting_service.build_forecast(series, horizon=14, threshold=3.0)

    assert result["horizon"] == 14
    assert result["threshold"] == 3.0
    assert len(result["forecast"]) == 14
    assert len(result["anomalies"]) == 1
    assert result["model"]["r2"] is not None
