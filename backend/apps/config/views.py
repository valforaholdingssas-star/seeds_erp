from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.config import settings_service as cfg
from apps.config.models import SettingAudit
from apps.config.registry import GROUPS
from apps.config.serializers import SettingPatchSerializer
from apps.users.permissions import IsModuleRole


def _client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class ConfigListView(APIView):
    permission_module = "settings"
    permission_classes = [IsModuleRole]

    def get(self, request):
        return Response(
            {
                "groups": GROUPS,
                "settings": cfg.list_group(),
            }
        )

    def patch(self, request):
        serializer = SettingPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = []
        for item in serializer.validated_data["settings"]:
            row = cfg.set_value(
                item["key"],
                item.get("value"),
                actor=request.user,
                ip=_client_ip(request),
            )
            updated.append(cfg.describe(row.key))
        return Response({"settings": updated})


class ConfigGroupView(APIView):
    permission_module = "settings"
    permission_classes = [IsModuleRole]

    def get(self, request, group: str):
        return Response(
            {
                "group": group.upper(),
                "settings": cfg.list_group(group),
            }
        )


class ConfigTestView(APIView):
    """Live provider ping when credentials exist; mock-aware messages otherwise."""

    permission_module = "settings"
    permission_crud = "u"
    permission_classes = [IsModuleRole]

    def post(self, request, group: str):
        group = group.upper()
        settings = cfg.list_group(group)
        secrets_set = [s for s in settings if s["is_secret"] and s["is_set"]]
        has_secret_defs = any(s["is_secret"] for s in settings)

        if group == "ENVIA":
            from apps.logistics.services.envia import ping_envia

            result = ping_envia()
            return Response(result, status=200)

        if group == "ALEGRA":
            from apps.accounting.services.alegra import ping_alegra

            result = ping_alegra()
            return Response(result, status=200)

        if group == "WOOCOMMERCE":
            from apps.sales.services.woo_client import ping_woocommerce

            result = ping_woocommerce()
            return Response(result, status=200)

        if group == "KOMMO":
            from apps.sales.services.kommo_client import ping_kommo

            result = ping_kommo()
            return Response(result, status=200)

        if has_secret_defs and not secrets_set:
            return Response(
                {
                    "ok": False,
                    "message": (
                        f"Faltan credenciales de {group}. "
                        "Configúralas en Configuración → Integraciones."
                    ),
                },
                status=200,
            )
        return Response(
            {
                "ok": True,
                "message": f"Grupo {group}: configuración presente (sin ping específico).",
            }
        )


class ConfigAuditView(APIView):
    permission_module = "settings"
    permission_classes = [IsModuleRole]

    def get(self, request):
        qs = SettingAudit.objects.select_related("actor").all()[:100]
        key = request.query_params.get("key")
        if key:
            qs = SettingAudit.objects.select_related("actor").filter(key=key)[:100]
        data = [
            {
                "id": str(a.id),
                "key": a.key,
                "action": a.action,
                "old_value_masked": a.old_value_masked,
                "new_value_masked": a.new_value_masked,
                "actor": a.actor.email if a.actor else None,
                "created_at": a.created_at.isoformat(),
            }
            for a in qs
        ]
        return Response(data)


class IntegrationStatusView(APIView):
    """
    Lightweight status for banners across the ERP.
    Reveals only mode (live/mock), never secrets.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.accounting.services.alegra import ping_alegra
        from apps.logistics.services.envia import ping_envia

        envia = ping_envia()
        alegra = ping_alegra()
        return Response(
            {
                "envia": {
                    "ok": bool(envia.get("ok")),
                    "mode": envia.get("mode") or ("live" if envia.get("ok") else "error"),
                    "message": envia.get("message") or "",
                },
                "alegra": {
                    "ok": bool(alegra.get("ok")),
                    "mode": alegra.get("mode") or ("live" if alegra.get("ok") else "error"),
                    "message": alegra.get("message") or "",
                },
            }
        )
