from apps.orders.models import Customer


def list_customers():
    return Customer.objects.all()
