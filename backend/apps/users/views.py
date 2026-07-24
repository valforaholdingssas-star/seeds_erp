from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.services import log_audit_event
from apps.users.models import PasswordResetToken, UserStatus
from apps.users.permissions import IsAdmin
from apps.users.serializers import (
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
    modules_catalog_payload,
    role_choices,
)
from apps.users.module_access import load_role_modules, save_role_modules

User = get_user_model()


def _client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        user.mark_login()
        refresh = RefreshToken.for_user(user)
        log_audit_event(
            actor=user,
            action="LOGIN",
            entity="User",
            entity_id=str(user.id),
            ip=_client_ip(request),
        )
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            }
        )


class PasswordResetRequestView(APIView):
    """Always 200 — does not reveal whether the email exists."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = User.objects.normalize_email(serializer.validated_data["email"])
        user = User.objects.filter(email__iexact=email, status=UserStatus.ACTIVE).first()
        payload = {
            "detail": "Si el email existe, recibirás instrucciones para restablecer la contraseña."
        }
        if user:
            PasswordResetToken.objects.filter(
                email__iexact=email, used_at__isnull=True
            ).update(used_at=timezone.now())
            reset = PasswordResetToken.issue(email)
            log_audit_event(
                actor=None,
                action="PASSWORD_RESET_REQUESTED",
                entity="User",
                entity_id=str(user.id),
                metadata={"email": email},
                ip=_client_ip(request),
            )
            from django.conf import settings

            if settings.DEBUG:
                payload["debug_token"] = reset.token
        else:
            log_audit_event(
                actor=None,
                action="PASSWORD_RESET_REQUESTED",
                entity="User",
                entity_id="",
                metadata={"email": email, "found": False},
                ip=_client_ip(request),
            )
        return Response(payload, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token_value = serializer.validated_data["token"]
        password = serializer.validated_data["password"]
        reset = PasswordResetToken.objects.filter(token=token_value).first()
        if not reset or not reset.is_valid:
            return Response(
                {"detail": "Token inválido o expirado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = User.objects.filter(email__iexact=reset.email).first()
        if not user or user.status != UserStatus.ACTIVE:
            return Response(
                {"detail": "Token inválido o expirado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(password)
        user.save(update_fields=["password", "updated_at"])
        reset.mark_used()
        log_audit_event(
            actor=user,
            action="PASSWORD_RESET_CONFIRMED",
            entity="User",
            entity_id=str(user.id),
            metadata={"email": user.email},
            ip=_client_ip(request),
        )
        return Response({"detail": "Contraseña actualizada."}, status=status.HTTP_200_OK)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class RoleChoicesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(role_choices())


class ModulesCatalogView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        return Response(modules_catalog_payload())


class RolePermissionsView(APIView):
    """Configure which modules each role can see. Changes apply to all users of that role
    (unless the user has a personal modules override)."""

    permission_classes = [IsAdmin]

    def get(self, request):
        return Response(modules_catalog_payload())

    def put(self, request):
        raw = request.data.get("role_defaults") or request.data.get("roles") or request.data
        if not isinstance(raw, dict):
            return Response(
                {"detail": "Envía un objeto role_defaults: { ROL: [módulos...] }."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        saved = save_role_modules(
            raw,
            actor=request.user,
            ip=_client_ip(request),
        )
        log_audit_event(
            actor=request.user,
            action="ROLE_PERMISSIONS_UPDATED",
            entity="RolePermissions",
            entity_id="auth.role_modules",
            metadata={"roles": list(saved.keys())},
            ip=_client_ip(request),
        )
        return Response(
            {
                "detail": "Permisos por rol actualizados. Se aplican a todos los usuarios sin override personal.",
                "modules": modules_catalog_payload()["modules"],
                "role_defaults": saved,
            }
        )


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by("full_name")
    permission_classes = [IsAdmin]
    filterset_fields = ["role", "status", "email", "full_name"]
    search_fields = ["full_name", "email", "id_number", "phone"]
    ordering_fields = ["full_name", "email", "role", "created_at"]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        if self.action in {"update", "partial_update"}:
            return UserUpdateSerializer
        return UserSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        log_audit_event(
            actor=self.request.user,
            action="USER_CREATED",
            entity="User",
            entity_id=str(user.id),
            metadata={"email": user.email, "role": user.role},
            ip=_client_ip(self.request),
        )

    def perform_update(self, serializer):
        user = serializer.save()
        log_audit_event(
            actor=self.request.user,
            action="USER_UPDATED",
            entity="User",
            entity_id=str(user.id),
            metadata={"email": user.email, "role": user.role},
            ip=_client_ip(self.request),
        )

    def perform_destroy(self, instance):
        entity_id = str(instance.id)
        email = instance.email
        instance.delete()
        log_audit_event(
            actor=self.request.user,
            action="USER_DELETED",
            entity="User",
            entity_id=entity_id,
            metadata={"email": email},
            ip=_client_ip(self.request),
        )
