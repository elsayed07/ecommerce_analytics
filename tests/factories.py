from datetime import UTC

import factory
from django.contrib.auth import get_user_model

from apps.orders.models import Customer, Order, OrderItem
from apps.products.models import Category, Inventory, Product

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    role = User.Role.STAFF

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        obj.set_password(extracted or "pass12345")
        if create:
            obj.save()


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"Category {n}")
    slug = factory.Sequence(lambda n: f"category-{n}")


class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product

    name = factory.Sequence(lambda n: f"Product {n}")
    sku = factory.Sequence(lambda n: f"SKU-{n}")
    category = factory.SubFactory(CategoryFactory)
    price = factory.Faker("pydecimal", left_digits=3, right_digits=2, positive=True)


class InventoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Inventory

    product = factory.SubFactory(ProductFactory)
    quantity = 10


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Customer

    name = factory.Faker("name")
    email = factory.Sequence(lambda n: f"customer{n}@example.com")


class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Order

    customer = factory.SubFactory(CustomerFactory)
    external_ref = factory.Sequence(lambda n: f"ORD-{n}")
    order_date = factory.Faker("date_time_this_year", tzinfo=UTC)
    total = factory.Faker("pydecimal", left_digits=4, right_digits=2, positive=True)


class OrderItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrderItem

    order = factory.SubFactory(OrderFactory)
    product = factory.SubFactory(ProductFactory)
    quantity = 1
    unit_price = factory.Faker("pydecimal", left_digits=3, right_digits=2, positive=True)
