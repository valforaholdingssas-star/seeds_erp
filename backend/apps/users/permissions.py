from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.users.models import Role


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == Role.ADMIN)


class IsAdminOrSupervisor(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.role in {Role.ADMIN, Role.SUPERVISOR}
        )


class IsModuleRole(BasePermission):
    """Allow if user has one of the given roles (set via view.module_roles)."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.role == Role.ADMIN:
            return True
        allowed = getattr(view, "module_roles", [])
        return user.role in allowed


class ReadOnlyOrAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return user.role == Role.ADMIN
