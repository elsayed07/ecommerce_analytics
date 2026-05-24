from rest_framework.permissions import BasePermission

from apps.users.models import User


class _RolePermission(BasePermission):
    role: str

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_superuser or user.role == self.role)
        )


class IsAdmin(_RolePermission):
    role = User.Role.ADMIN


class IsAnalyst(_RolePermission):
    role = User.Role.ANALYST


class IsStaff(_RolePermission):
    role = User.Role.STAFF
