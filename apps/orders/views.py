from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.orders.serializers import CustomerSerializer, OrderReadSerializer
from services import customer_service, order_service


class CustomerViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["email"]
    search_fields = ["name", "email"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        return customer_service.list_customers()


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderReadSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "customer", "currency"]
    search_fields = ["external_ref"]
    ordering_fields = ["order_date", "total", "created_at"]
    ordering = ["-order_date"]

    def get_queryset(self):
        return order_service.list_orders()
