from rest_framework import viewsets

from apps.common.permissions import IsAdminOrAnalystOrReadOnly
from apps.products.serializers import (
    CategorySerializer,
    ProductReadSerializer,
    ProductWriteSerializer,
)
from services import product_service


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrAnalystOrReadOnly]
    filterset_fields = ["slug"]
    search_fields = ["name", "slug"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        return product_service.list_categories()

    def perform_create(self, serializer):
        serializer.instance = product_service.create_category(serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = product_service.update_category(
            serializer.instance, serializer.validated_data
        )

    def perform_destroy(self, instance):
        product_service.delete_category(instance)


class ProductViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrAnalystOrReadOnly]
    filterset_fields = ["category"]
    search_fields = ["name", "sku"]
    ordering_fields = ["name", "price", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        return product_service.list_products()

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ProductWriteSerializer
        return ProductReadSerializer

    def perform_create(self, serializer):
        serializer.instance = product_service.create_product(serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = product_service.update_product(
            serializer.instance, serializer.validated_data
        )

    def perform_destroy(self, instance):
        product_service.delete_product(instance)
