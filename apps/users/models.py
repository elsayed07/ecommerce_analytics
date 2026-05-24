from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.db import models

from apps.common.models import BaseModel, SoftDeleteManager


class UserManager(DjangoUserManager, SoftDeleteManager):
    """Django's create_user/create_superuser plus soft-delete filtering."""

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", self.model.Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser, BaseModel):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        ANALYST = "analyst", "Analyst"
        STAFF = "staff", "Staff"

    role = models.CharField(max_length=16, choices=Role.choices, default=Role.STAFF)

    objects = UserManager()

    def __str__(self):
        return self.username
