from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.users.views import (
    LoginView,
    MeView,
    ModulesCatalogView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RoleChoicesView,
    RolePermissionsView,
    UserViewSet,
)

router = DefaultRouter()
router.register("users", UserViewSet, basename="users")

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/roles/", RoleChoicesView.as_view(), name="auth-roles"),
    path("auth/modules/", ModulesCatalogView.as_view(), name="auth-modules"),
    path(
        "auth/role-permissions/",
        RolePermissionsView.as_view(),
        name="auth-role-permissions",
    ),
    path(
        "auth/password-reset/",
        PasswordResetRequestView.as_view(),
        name="auth-password-reset",
    ),
    path(
        "auth/password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    path("", include(router.urls)),
]
