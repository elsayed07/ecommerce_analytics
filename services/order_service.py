from apps.orders.models import Order


def list_orders():
    return Order.objects.select_related("customer").prefetch_related("items__product")
