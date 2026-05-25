from apps.products.models import Category, Product


def list_products():
    return Product.objects.select_related("category", "inventory")


def list_categories():
    return Category.objects.all()
