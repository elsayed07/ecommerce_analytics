from django.urls import path

from apps.analytics.views import (
    CustomersView,
    ForecastView,
    RevenueView,
    TopProductsView,
)

urlpatterns = [
    path("analytics/revenue/", RevenueView.as_view(), name="analytics-revenue"),
    path("analytics/top-products/", TopProductsView.as_view(), name="analytics-top-products"),
    path("analytics/customers/", CustomersView.as_view(), name="analytics-customers"),
    path("analytics/forecast/", ForecastView.as_view(), name="analytics-forecast"),
]
