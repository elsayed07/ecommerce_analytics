import pytest

from apps.products.models import Category

from .factories import CategoryFactory

pytestmark = pytest.mark.django_db


def test_soft_delete_hides_from_default_manager():
    category = CategoryFactory()
    category.delete()

    assert not Category.objects.filter(pk=category.pk).exists()
    assert Category.all_objects.filter(pk=category.pk).exists()

    category.refresh_from_db()
    assert category.is_deleted is True


def test_restore_brings_row_back():
    category = CategoryFactory()
    category.delete()
    category.restore()

    assert Category.objects.filter(pk=category.pk).exists()


def test_timestamps_populated():
    category = CategoryFactory()
    assert category.created_at is not None
    assert category.updated_at is not None
