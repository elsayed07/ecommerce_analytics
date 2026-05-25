from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """Audit timestamps for all business models."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet whose bulk delete soft-deletes instead of removing rows."""

    def delete(self):
        count = super().update(is_deleted=True, updated_at=timezone.now())
        return count, {self.model._meta.label: count}


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """Default manager excluding soft-deleted rows."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class SoftDeleteModel(models.Model):
    """Soft deletion: never hard-delete business data."""

    is_deleted = models.BooleanField(default=False)

    objects = SoftDeleteManager()
    # Unfiltered (includes soft-deleted rows) but still soft-deletes on bulk delete.
    all_objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.save(using=using, update_fields=["is_deleted", "updated_at"])

    def restore(self):
        self.is_deleted = False
        self.save(update_fields=["is_deleted", "updated_at"])


class BaseModel(TimeStampedModel, SoftDeleteModel):
    """Audit timestamps + soft deletion for all core models."""

    class Meta:
        abstract = True
