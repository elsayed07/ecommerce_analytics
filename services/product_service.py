from apps.products.models import Category, Product


def list_products():
    return Product.objects.select_related("category", "inventory")


def list_categories():
    return Category.objects.all()


def create_product(data):
    return Product.objects.create(**data)


def update_product(product, data):
    for field, value in data.items():
        setattr(product, field, value)
    product.save()
    return product


def delete_product(product):
    product.delete()


def create_category(data):
    return Category.objects.create(**data)


def update_category(category, data):
    for field, value in data.items():
        setattr(category, field, value)
    category.save()
    return category


def delete_category(category):
    category.delete()
