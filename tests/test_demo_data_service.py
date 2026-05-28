import pytest
from django.core.management import call_command
from django.db.models import Count

from apps.orders.models import Customer, Order, OrderItem
from apps.products.models import Category, Inventory, Product
from services import analytics_service, demo_data_service, revenue_service

pytestmark = pytest.mark.django_db


def test_build_dataset_is_deterministic_with_seed():
    first = demo_data_service._build_dataset(orders=200, seed=42)
    second = demo_data_service._build_dataset(orders=200, seed=42)
    assert first == second


def test_different_seeds_produce_different_data():
    first = demo_data_service._build_dataset(orders=200, seed=1)
    second = demo_data_service._build_dataset(orders=200, seed=2)
    assert first["orders"] != second["orders"]


def test_generate_creates_all_expected_models():
    counts = demo_data_service.generate_demo_data(orders=300, seed=42)

    assert Category.objects.exists()
    assert Product.objects.exists()
    assert Inventory.objects.exists()
    assert Customer.objects.exists()
    assert OrderItem.objects.exists()
    assert Order.objects.count() == counts["orders"] == 300


def test_generate_is_idempotent_for_same_seed():
    demo_data_service.generate_demo_data(orders=150, seed=42)
    demo_data_service.generate_demo_data(orders=150, seed=42)
    assert Order.objects.count() == 150  # re-run does not duplicate


def test_cancellations_and_refunds_are_present():
    demo_data_service.generate_demo_data(orders=500, seed=42)
    assert Order.objects.filter(status="cancelled").exists()
    assert Order.objects.filter(status="refunded").exists()


def test_returning_customer_ratio_is_realistic():
    demo_data_service.generate_demo_data(orders=600, seed=42)
    per_customer = Order.objects.values("customer").annotate(n=Count("id"))
    total = len(per_customer)
    returning = sum(1 for row in per_customer if row["n"] >= 2)
    assert 0.15 <= returning / total <= 0.5


def test_generated_data_supports_analytics_and_forecasting():
    demo_data_service.generate_demo_data(orders=400, seed=42)
    assert revenue_service.daily_revenue()  # completed orders span multiple days

    analytics_service.build_snapshots()
    assert analytics_service.get_revenue("daily")
    assert analytics_service.get_forecast()["forecast"]


def test_management_command_generates_orders():
    call_command("generate_demo_data", "--orders=150", "--seed=7")
    assert Order.objects.count() == 150


def test_management_command_rejects_non_positive_orders():
    from django.core.management.base import CommandError

    with pytest.raises(CommandError):
        call_command("generate_demo_data", "--orders=0")
