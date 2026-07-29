from __future__ import annotations

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import log_audit_event
from apps.integrations.models import IntegrationSource, RawEventStatus
from apps.sales.models import ConsolidatedSale, SaleState
from apps.sales.serializers import (
    BulkUpdateSerializer,
    ConsolidatedSaleSerializer,
    ConsolidatedSaleUpdateSerializer,
    InternalSaleCreateSerializer,
    ManualSaleCreateSerializer,
    WithdrawSerializer,
)
from apps.sales.services.csv_import import commit_csv, commit_xlsx, dry_run_csv, dry_run_xlsx
from apps.sales.services.internal_forms import create_feria_sale, create_manual_sale
from apps.sales.services.normalization import calc_fiscal, guide_cost_for_sale, withdraw_from_consolidated
from apps.sales.services.failed_ecommerce import list_failed_ecommerce, update_follow_up
from apps.sales.services.resync import start_shopify_resync, start_woo_resync
from apps.sales.models import FollowUpStatus
from apps.sales.tasks import (
    enqueue_shopify_resync,
    enqueue_woo_resync,
    persist_raw_event,
    process_raw_event,
    verify_shopify_signature,
    verify_woo_signature,
)
from apps.logistics.serializers import BatchJobSerializer
from apps.users.permissions import IsAdmin, IsAdminOrSupervisor, IsModuleRole


def _client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class ConsolidatedSaleViewSet(viewsets.ModelViewSet):
    permission_module = "sales"
    queryset = ConsolidatedSale.objects.select_related(
        "seller", "shipment", "invoice", "payment_method"
    ).prefetch_related("items")
    filterset_fields = [
        "source",
        "state",
        "status",
        "seller",
        "city_raw",
        "income_source",
        "payment_account",
        "external_id",
        "requires_shipping",
        "fulfillment_type",
    ]
    search_fields = [
        "external_id",
        "customer_name",
        "email",
        "phone",
        "id_number",
        "city_raw",
        "deal_name",
    ]
    ordering_fields = [
        "closed_at",
        "total_value",
        "customer_name",
        "created_at",
        "city_raw",
    ]

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            self.module_roles = ["VENTAS", "LOGISTICA", "CONTABILIDAD", "SUPERVISOR", "VIEWER"]
            return [IsModuleRole()]
        if self.action in {"create", "update", "partial_update", "bulk_update", "withdraw", "import_csv"}:
            self.module_roles = ["VENTAS"]
            return [IsModuleRole()]
        return [IsAdmin()]

    def get_serializer_class(self):
        if self.action in {"update", "partial_update"}:
            return ConsolidatedSaleUpdateSerializer
        return ConsolidatedSaleSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        # Default: only ACTIVE unless explicitly filtered
        state = self.request.query_params.get("state")
        if not state and self.action == "list":
            qs = qs.filter(state=SaleState.ACTIVE)
        return qs

    def perform_update(self, serializer):
        sale = serializer.save()
        products, iva, net = calc_fiscal(sale.total_value, guide_cost_for_sale(sale))
        sale.amount_products = products
        sale.iva_generated = iva
        sale.net_value = net
        sale.save(update_fields=["amount_products", "iva_generated", "net_value", "updated_at"])
        log_audit_event(
            actor=self.request.user,
            action="SALE_UPDATED",
            entity="ConsolidatedSale",
            entity_id=str(sale.id),
            ip=_client_ip(self.request),
        )

    @action(detail=False, methods=["post"])
    def bulk_update(self, request):
        ser = BulkUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        allowed = {
            "payment_account",
            "payment_method",
            "city_raw",
            "state_raw",
            "requires_shipping",
            "fulfillment_type",
            "symptoms",
        }
        fields = {k: v for k, v in ser.validated_data["fields"].items() if k in allowed}
        if not fields:
            return Response({"detail": "Sin campos permitidos."}, status=400)

        from apps.sales.models import PaymentMethod
        from apps.sales.services.payment_methods import resolve_payment_method
        from apps.sales.services.fulfillment import apply_fulfillment, sync_shipment_for_fulfillment

        if "payment_method" in fields:
            pm = PaymentMethod.objects.filter(id=fields["payment_method"]).first()
            if not pm:
                return Response({"detail": "Medio de pago inválido."}, status=400)
            fields["payment_method"] = pm
            fields["payment_account"] = pm.name
        elif "payment_account" in fields:
            pm = resolve_payment_method(str(fields.get("payment_account") or ""))
            if pm:
                fields["payment_method"] = pm
                fields["payment_account"] = pm.name

        if "fulfillment_type" in fields or "requires_shipping" in fields:
            apply_fulfillment(fields)

        qs = ConsolidatedSale.objects.filter(id__in=ser.validated_data["ids"])
        updated = qs.update(**fields, updated_at=timezone.now())
        for sale in qs:
            sync_shipment_for_fulfillment(sale, actor=request.user)
        return Response({"updated": updated})

    @action(detail=True, methods=["post"])
    def withdraw(self, request, pk=None):
        sale = self.get_object()
        ser = WithdrawSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        # UI "eliminar": purga venta + envío + factura local
        withdraw_from_consolidated(
            sale,
            reason=ser.validated_data.get("reason") or "",
            actor=request.user,
            purge=True,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="import")
    def import_csv(self, request):
        """
        CSV / XLSX import.
        Body JSON: { csv: "...", dry_run: true|false, on_duplicate: skip|update, mapping?: {...} }
        Or multipart file field `file` (.csv or .xlsx).
        """
        mapping = request.data.get("mapping")
        if isinstance(mapping, str) and mapping.strip():
            import json

            try:
                mapping = json.loads(mapping)
            except json.JSONDecodeError:
                return Response({"detail": "mapping inválido"}, status=400)
        dry = str(request.data.get("dry_run", "true")).lower() in {"1", "true", "yes"}
        on_duplicate = request.data.get("on_duplicate") or "skip"
        if on_duplicate not in {"skip", "update"}:
            return Response({"detail": "on_duplicate debe ser skip|update"}, status=400)

        text = request.data.get("csv") or ""
        upload = request.FILES.get("file")
        xlsx_raw: bytes | None = None
        if upload:
            name = (getattr(upload, "name", "") or "").lower()
            raw = upload.read()
            if name.endswith((".xlsx", ".xlsm")):
                xlsx_raw = raw
            else:
                text = raw.decode("utf-8-sig", errors="replace")
        if xlsx_raw is None and not str(text).strip():
            return Response({"detail": "CSV/XLSX vacío."}, status=400)

        if dry:
            if xlsx_raw is not None:
                return Response(dry_run_xlsx(xlsx_raw, mapping=mapping))
            return Response(dry_run_csv(text, mapping=mapping))
        if xlsx_raw is not None:
            result = commit_xlsx(
                xlsx_raw,
                mapping=mapping,
                on_duplicate=on_duplicate,
                actor=request.user,
            )
        else:
            result = commit_csv(
                text,
                mapping=mapping,
                on_duplicate=on_duplicate,
                actor=request.user,
            )
        return Response(result, status=201)


class FeriaSaleCreateView(APIView):
    permission_module = "sales"
    module_roles = ["VENTAS"]
    permission_classes = [IsModuleRole]

    def post(self, request):
        ser = InternalSaleCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        source, consolidated = create_feria_sale(ser.validated_data, actor=request.user)
        return Response(
            {
                "source_id": str(source.id),
                "sale": ConsolidatedSaleSerializer(consolidated).data if consolidated else None,
            },
            status=status.HTTP_201_CREATED,
        )


class ManualSaleCreateView(APIView):
    permission_module = "sales"
    module_roles = ["VENTAS"]
    permission_classes = [IsModuleRole]

    def post(self, request):
        ser = ManualSaleCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        source, consolidated = create_manual_sale(ser.validated_data, actor=request.user)
        return Response(
            {
                "source_id": str(source.id),
                "sale": ConsolidatedSaleSerializer(consolidated).data if consolidated else None,
            },
            status=status.HTTP_201_CREATED,
        )


class WooCommerceWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request, event: str):
        signature = request.headers.get("X-Seeds-Signature") or request.headers.get(
            "X-WC-Webhook-Signature", ""
        )
        raw = request.body or b"{}"
        if not verify_woo_signature(raw, signature):
            return Response({"detail": "Firma inválida"}, status=401)

        payload = request.data if isinstance(request.data, dict) else {"raw": str(request.data)}
        order_id = str(payload.get("id") or payload.get("body", {}).get("id") or "unknown")
        status_val = str(payload.get("status") or "unknown")
        dedupe = f"woo:order:{order_id}:{event}:{status_val}"
        event_obj, created = persist_raw_event(
            source=IntegrationSource.WOOCOMMERCE,
            event_type=f"order-{event}",
            payload=payload,
            headers={k: v for k, v in request.headers.items() if k.lower().startswith("x-")},
            signature=signature,
            dedupe_key=dedupe,
        )
        if created:
            process_raw_event.delay(str(event_obj.id))
        return Response({"status": "accepted", "event_id": str(event_obj.id)}, status=200)


class EcommerceResyncView(APIView):
    """Reconcile WooCommerce orders in a date range → BatchJob WOO_RESYNC."""

    permission_module = "sales"
    permission_crud = "u"
    module_roles = ["VENTAS", "SUPERVISOR"]
    permission_classes = [IsModuleRole]

    def post(self, request):
        after = (request.data.get("after") or "").strip()
        before = (request.data.get("before") or "").strip()
        status_filter = (request.data.get("status") or "").strip() or None
        if not after or not before:
            return Response(
                {"detail": "after y before (YYYY-MM-DD) son obligatorios."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        batch = start_woo_resync(
            after=after,
            before=before,
            status=status_filter,
            actor=request.user,
        )
        if batch.total > 0 and batch.status != "COMPLETED":
            enqueue_woo_resync.delay(str(batch.id))
        return Response(BatchJobSerializer(batch).data, status=status.HTTP_201_CREATED)


class ShopifyWebhookView(APIView):
    """
    HTTPS webhook for Shopify order topics.
    Topics: orders/create, orders/updated, orders/paid, orders/cancelled, …
    Verify X-Shopify-Hmac-SHA256 (base64 HMAC-SHA256 of raw body).
    Respond 200 quickly; process async via Celery.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        signature = request.headers.get("X-Shopify-Hmac-SHA256") or request.headers.get(
            "X-Shopify-Hmac-Sha256", ""
        )
        raw = request.body or b"{}"
        if not verify_shopify_signature(raw, signature):
            return Response({"detail": "Firma inválida"}, status=401)

        topic = (
            request.headers.get("X-Shopify-Topic")
            or request.headers.get("x-shopify-topic")
            or "orders/updated"
        )
        webhook_id = (
            request.headers.get("X-Shopify-Webhook-Id")
            or request.headers.get("x-shopify-webhook-id")
            or ""
        )
        payload = request.data if isinstance(request.data, dict) else {"raw": str(request.data)}
        order_id = str(payload.get("id") or "unknown")
        financial = str(payload.get("financial_status") or "unknown")
        # Prefer Shopify delivery id for exact dedupe; fallback to order+topic+status
        dedupe = (
            f"shopify:webhook:{webhook_id}"
            if webhook_id
            else f"shopify:order:{order_id}:{topic}:{financial}"
        )
        headers = {
            k: v
            for k, v in request.headers.items()
            if k.lower().startswith("x-shopify") or k.lower().startswith("x-")
        }
        event_obj, created = persist_raw_event(
            source=IntegrationSource.SHOPIFY,
            event_type=str(topic),
            payload=payload,
            headers=headers,
            signature=signature,
            dedupe_key=dedupe,
        )
        if created:
            process_raw_event.delay(str(event_obj.id))
        return Response({"status": "accepted", "event_id": str(event_obj.id)}, status=200)


class ShopifyResyncView(APIView):
    """Reconcile Shopify orders in a date range → BatchJob SHOPIFY_RESYNC."""

    permission_module = "sales"
    permission_crud = "u"
    module_roles = ["VENTAS", "SUPERVISOR"]
    permission_classes = [IsModuleRole]

    def post(self, request):
        after = (request.data.get("after") or "").strip()
        before = (request.data.get("before") or "").strip()
        financial_status = (request.data.get("financial_status") or "").strip() or None
        if not after or not before:
            return Response(
                {"detail": "after y before (YYYY-MM-DD) son obligatorios."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        batch = start_shopify_resync(
            after=after,
            before=before,
            financial_status=financial_status,
            actor=request.user,
        )
        if batch.total > 0 and batch.status != "COMPLETED":
            enqueue_shopify_resync.delay(str(batch.id))
        return Response(BatchJobSerializer(batch).data, status=status.HTTP_201_CREATED)


class FailedEcommerceListView(APIView):
    """
    Pedidos Woo/Shopify que no consolidaron (pending/failed/cancelled/…)
    para seguimiento comercial diario.
    """

    permission_module = "sales"
    module_roles = ["VENTAS", "SUPERVISOR", "VIEWER"]
    permission_classes = [IsModuleRole]

    def get(self, request):
        rows = list_failed_ecommerce(
            channel=(request.query_params.get("channel") or "").strip().upper() or None,
            follow_up_status=(request.query_params.get("follow_up_status") or "").strip()
            or None,
            order_status=(request.query_params.get("status") or "").strip() or None,
            search=(request.query_params.get("search") or "").strip() or None,
            contacted=(request.query_params.get("contacted") or "").strip() or None,
        )
        counts = {
            "total": len(rows),
            "por_contactar": sum(
                1 for r in rows if r["follow_up_status"] == FollowUpStatus.POR_CONTACTAR
            ),
            "contactados": sum(1 for r in rows if r.get("contacted_at")),
        }
        return Response({"count": len(rows), "counts": counts, "results": rows})


class FailedEcommerceDetailView(APIView):
    permission_module = "sales"
    permission_crud = "u"
    module_roles = ["VENTAS", "SUPERVISOR"]
    permission_classes = [IsModuleRole]

    def patch(self, request, pk):
        channel = (
            (request.data.get("channel") or request.query_params.get("channel") or "")
            .strip()
            .upper()
        )
        if channel not in {"ECOMMERCE", "SHOPIFY"}:
            return Response(
                {"detail": "channel es obligatorio (ECOMMERCE|SHOPIFY)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        mark = request.data.get("mark_contacted")
        mark_contacted = str(mark).lower() in {"1", "true", "yes"} if mark is not None else False
        try:
            row = update_follow_up(
                channel=channel,
                pk=str(pk),
                actor=request.user,
                follow_up_status=(request.data.get("follow_up_status") or None),
                follow_up_notes=(
                    request.data.get("follow_up_notes")
                    if "follow_up_notes" in request.data
                    else None
                ),
                mark_contacted=mark_contacted,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except LookupError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(row)


class KommoWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request, token=None):
        # token = path id for /webhook/<id> (Kommo UI); ignored by handler
        # Kommo sends form-encoded; DRF parses to QueryDict
        data = request.data
        if hasattr(data, "dict"):
            flat = data.dict()
        else:
            flat = dict(data) if data else {}

        # Support enriched JSON testing payload as well as raw form keys
        lead_id = (
            flat.get("leads[status][0][id]")
            or flat.get("lead_id")
            or (flat.get("lead") or {}).get("id")
            or "unknown"
        )
        status_id = (
            flat.get("leads[status][0][status_id]")
            or flat.get("status_id")
            or (flat.get("lead") or {}).get("status_id")
            or "unknown"
        )
        dedupe = f"kommo:lead:{lead_id}:{status_id}"
        event_obj, created = persist_raw_event(
            source=IntegrationSource.KOMMO,
            event_type="lead-status-changed",
            payload=flat,
            headers={},
            signature="",
            dedupe_key=dedupe,
        )
        if not created:
            # Same lead+status resent (e.g. after deleting the sale): re-queue.
            event_obj.payload = flat
            event_obj.status = RawEventStatus.RECEIVED
            event_obj.error = ""
            event_obj.processed_at = None
            event_obj.save(
                update_fields=[
                    "payload",
                    "status",
                    "error",
                    "processed_at",
                    "updated_at",
                ]
            )
        process_raw_event.delay(str(event_obj.id))
        # Digital Pipeline / salesbot: HTTP 200 = recibido. El avance a la
        # columna «registrado en ERP» ocurre al terminar el proceso async.
        return Response(
            {
                "ok": True,
                "status": "accepted",
                "message": "Lead aceptado; se registrará en el ERP y se moverá de etapa si está configurado.",
                "event_id": str(event_obj.id),
                "lead_id": str(lead_id),
                "status_id": str(status_id),
                "reprocessed": not created,
            },
            status=200,
        )
