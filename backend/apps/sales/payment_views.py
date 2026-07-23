from rest_framework import serializers, status, viewsets
from rest_framework.response import Response

from apps.audit.services import log_audit_event
from apps.sales.models import PaymentMethod
from apps.sales.services.payment_methods import apply_payment_method_name, ensure_default_payment_methods
from apps.users.permissions import IsAdmin, IsModuleRole


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = [
            "id",
            "name",
            "active",
            "aliases",
            "is_system",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_system", "created_at", "updated_at"]


class PaymentMethodViewSet(viewsets.ModelViewSet):
    queryset = PaymentMethod.objects.all()
    serializer_class = PaymentMethodSerializer
    filterset_fields = ["active", "is_system", "name"]
    search_fields = ["name", "aliases"]
    ordering_fields = ["name", "created_at", "active"]

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            self.module_roles = ["VENTAS", "LOGISTICA", "CONTABILIDAD", "SUPERVISOR", "VIEWER"]
            return [IsModuleRole()]
        return [IsAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("active_only") == "1":
            qs = qs.filter(active=True)
        return qs

    def perform_create(self, serializer):
        method = serializer.save()
        log_audit_event(
            actor=self.request.user,
            action="PAYMENT_METHOD_CREATED",
            entity="PaymentMethod",
            entity_id=str(method.id),
            metadata={"name": method.name},
        )

    def perform_update(self, serializer):
        old_name = serializer.instance.name
        method = serializer.save()
        if method.name != old_name:
            apply_payment_method_name(method)
        log_audit_event(
            actor=self.request.user,
            action="PAYMENT_METHOD_UPDATED",
            entity="PaymentMethod",
            entity_id=str(method.id),
            metadata={"name": method.name, "was": old_name, "active": method.active},
        )

    def destroy(self, request, *args, **kwargs):
        method = self.get_object()
        if method.is_system:
            return Response(
                {
                    "detail": "No se puede eliminar un medio de sistema. Desactívalo.",
                    "code": "system_payment_method",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if method.sales.exists():
            return Response(
                {
                    "detail": "Hay ventas con este medio. Desactívalo o reasígnalas antes.",
                    "code": "in_use",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        entity_id = str(method.id)
        name = method.name
        method.delete()
        log_audit_event(
            actor=request.user,
            action="PAYMENT_METHOD_DELETED",
            entity="PaymentMethod",
            entity_id=entity_id,
            metadata={"name": name},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def list(self, request, *args, **kwargs):
        # Lazy seed so dropdown never arranca vacío en ambientes frescos
        if not PaymentMethod.objects.exists():
            ensure_default_payment_methods(actor=getattr(request, "user", None))
        return super().list(request, *args, **kwargs)
