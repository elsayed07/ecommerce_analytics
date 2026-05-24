from django.db import models

from apps.common.models import BaseModel


class Category(BaseModel):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(BaseModel):
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=64, unique=True)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products"
    )
    price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["category"])]

    def __str__(self):
        return f"{self.sku} - {self.name}"


class Inventory(BaseModel):
    product = models.OneToOneField(
        Product, on_delete=models.CASCADE, related_name="inventory"
    )
    quantity = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = "inventories"

    def __str__(self):
        return f"{self.product.sku}: {self.quantity}"
