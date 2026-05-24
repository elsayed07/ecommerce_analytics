from rest_framework.permissions import BasePermission

from apps.users.models import User


class _RolePermission(BasePermission):
    role: str

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == self.role
        )


class IsAdmin(_RolePermission):
    role = User.Role.ADMIN


class IsAnalyst(_RolePermission):
    role = User.Role.ANALYST


class IsStaff(_RolePermission):
    role = User.Role.STAFF
