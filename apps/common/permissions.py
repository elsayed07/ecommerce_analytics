from rest_framework.permissions import SAFE_METHODS, BasePermission

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


class IsAdminOrAnalystOrReadOnly(BasePermission):
    """Any authenticated user may read; only admin/analyst (or superuser) may write."""

    write_roles = {User.Role.ADMIN, User.Role.ANALYST}

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return user.is_superuser or user.role in self.write_roles
