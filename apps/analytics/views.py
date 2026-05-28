import plotly.graph_objects as go
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from services import analytics_service

VALID_PERIODS = ("daily", "weekly", "monthly")


class RevenueView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        period = request.query_params.get("period", "daily")
        if period not in VALID_PERIODS:
            raise ValidationError(
                f"Invalid period '{period}'. Choose one of: {', '.join(VALID_PERIODS)}."
            )
        return Response({"period": period, "series": analytics_service.get_revenue(period)})


class TopProductsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(analytics_service.get_top_products())


class CustomersView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(analytics_service.get_customers())


class ForecastView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(analytics_service.get_forecast())


@staff_member_required
def dashboard(request):
    """Server-side Plotly dashboard reading from analytics snapshots (staff only)."""
    revenue = analytics_service.get_revenue("daily")
    top = analytics_service.get_top_products()
    customers = analytics_service.get_customers()

    dates = [row["period_start"] for row in revenue]
    revenue_fig = go.Figure()
    revenue_fig.add_trace(
        go.Scatter(x=dates, y=[r["revenue"] for r in revenue], name="Revenue", mode="lines+markers")
    )
    revenue_fig.add_trace(
        go.Scatter(x=dates, y=[r.get("rolling_7") for r in revenue], name="7-day avg", mode="lines")
    )
    revenue_fig.add_trace(
        go.Scatter(
            x=dates,
            y=[r.get("rolling_30") for r in revenue],
            name="30-day avg",
            mode="lines",
        )
    )
    revenue_fig.update_layout(title="Daily revenue (EUR)")

    by_revenue = top.get("by_revenue", [])
    products_fig = go.Figure(
        go.Bar(x=[p["sku"] for p in by_revenue], y=[p["revenue"] for p in by_revenue])
    )
    products_fig.update_layout(title="Top products by revenue (EUR)")

    customers_fig = go.Figure(
        go.Pie(
            labels=["New", "Returning"],
            values=[customers.get("new", 0), customers.get("returning", 0)],
        )
    )
    customers_fig.update_layout(title="Customers: new vs returning")

    forecast = analytics_service.get_forecast()
    forecast_fig = go.Figure()
    forecast_fig.add_trace(
        go.Scatter(x=dates, y=[r["revenue"] for r in revenue], name="Actual", mode="lines")
    )
    forecast_fig.add_trace(
        go.Scatter(
            x=[f["date"] for f in forecast["forecast"]],
            y=[f["predicted_revenue"] for f in forecast["forecast"]],
            name="Forecast",
            mode="lines",
            line={"dash": "dash"},
        )
    )
    anomalies = forecast.get("anomalies", [])
    forecast_fig.add_trace(
        go.Scatter(
            x=[a["date"] for a in anomalies],
            y=[a["revenue"] for a in anomalies],
            name="Anomaly",
            mode="markers",
            marker={"color": "red", "size": 10},
        )
    )
    forecast_fig.update_layout(title="Revenue forecast (EUR)")

    responsive = {"responsive": True}
    charts = [
        revenue_fig.to_html(full_html=False, include_plotlyjs="cdn", config=responsive),
        forecast_fig.to_html(full_html=False, include_plotlyjs=False, config=responsive),
        products_fig.to_html(full_html=False, include_plotlyjs=False, config=responsive),
        customers_fig.to_html(full_html=False, include_plotlyjs=False, config=responsive),
    ]
    return render(request, "analytics/dashboard.html", {"charts": charts, "customers": customers})
