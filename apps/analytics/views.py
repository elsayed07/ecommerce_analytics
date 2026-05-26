import plotly.graph_objects as go
from django.shortcuts import render
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from services import analytics_service


class RevenueView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        period = request.query_params.get("period", "daily")
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


def dashboard(request):
    """Server-side Plotly dashboard reading from analytics snapshots."""
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

    charts = [
        revenue_fig.to_html(full_html=False, include_plotlyjs="cdn"),
        products_fig.to_html(full_html=False, include_plotlyjs=False),
        customers_fig.to_html(full_html=False, include_plotlyjs=False),
    ]
    return render(request, "analytics/dashboard.html", {"charts": charts, "customers": customers})
