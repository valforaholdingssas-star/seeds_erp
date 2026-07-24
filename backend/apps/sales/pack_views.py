from rest_framework import serializers, viewsets

from apps.audit.services import log_audit_event
from apps.sales.models import ProductPackRule
from apps.users.permissions import IsModuleRole


class ProductPackRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductPackRule
        fields = [
            "id",
            "woo_product_id",
            "name_contains",
            "multiplier",
            "active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        woo = (attrs.get("woo_product_id") or getattr(self.instance, "woo_product_id", "") or "").strip()
        name = (attrs.get("name_contains") or getattr(self.instance, "name_contains", "") or "").strip()
        if not woo and not name:
            raise serializers.ValidationError(
                "Indica woo_product_id o name_contains para la regla."
            )
        mult = attrs.get("multiplier", getattr(self.instance, "multiplier", 1))
        if mult is not None and int(mult) < 1:
            raise serializers.ValidationError({"multiplier": "Debe ser ≥ 1."})
        return attrs


class ProductPackRuleViewSet(viewsets.ModelViewSet):
    permission_module = "pack_rules"
    queryset = ProductPackRule.objects.all()
    serializer_class = ProductPackRuleSerializer
    filterset_fields = ["active", "woo_product_id"]
    search_fields = ["woo_product_id", "name_contains"]
    ordering_fields = ["woo_product_id", "multiplier", "created_at"]

    def get_permissions(self):
        return [IsModuleRole()]

    def perform_create(self, serializer):
        rule = serializer.save()
        log_audit_event(
            actor=self.request.user,
            action="PACK_RULE_CREATED",
            entity="ProductPackRule",
            entity_id=str(rule.id),
            metadata={"woo": rule.woo_product_id, "mult": rule.multiplier},
        )

    def perform_update(self, serializer):
        rule = serializer.save()
        log_audit_event(
            actor=self.request.user,
            action="PACK_RULE_UPDATED",
            entity="ProductPackRule",
            entity_id=str(rule.id),
            metadata={"woo": rule.woo_product_id, "mult": rule.multiplier, "active": rule.active},
        )
