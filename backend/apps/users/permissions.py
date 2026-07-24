from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.users.models import Role
from apps.users.module_access import crud_for_view, user_can


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
    """
    Allow if:
    - view.permission_module is set → user has CRUD letter for that module, OR
    - legacy: ADMIN always, else user.role in view.module_roles
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        module = getattr(view, "permission_module", None)
        if module:
            action = crud_for_view(view, request)
            return user_can(user, module, action)

        if user.role == Role.ADMIN:
            return True
        allowed = getattr(view, "module_roles", [])
        return user.role in allowed


class HasModulePermission(BasePermission):
    """Strict CRUD check for view.permission_module (required)."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        module = getattr(view, "permission_module", None)
        if not module:
            return False
        return user_can(user, module, crud_for_view(view, request))


class ReadOnlyOrAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return user.role == Role.ADMIN
