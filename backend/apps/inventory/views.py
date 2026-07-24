from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.inventory.models import KardexEntry, Material, Product
from apps.inventory.serializers import (
    KardexEntrySerializer,
    ManualEntrySerializer,
    MaterialSerializer,
    ProductSerializer,
)
from apps.inventory.services import create_manual_entry, low_stock_materials, low_stock_products
from apps.sales.kit_types import normalize_kit_type
from apps.users.permissions import IsModuleRole


class ProductViewSet(viewsets.ModelViewSet):
    permission_module = "inventory"
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filterset_fields = ["active", "color", "tipo", "is_generic", "sku"]
    search_fields = ["sku", "name", "tipo", "woo_product_id"]
    ordering_fields = ["name", "sku", "stock", "created_at"]

    def get_permissions(self):
        self.module_roles = ["LOGISTICA", "VENTAS", "CONTABILIDAD", "SUPERVISOR", "VIEWER"]
        if self.action in {"list", "retrieve", "alerts"}:
            return [IsModuleRole()]
        self.module_roles = ["LOGISTICA"]
        return [IsModuleRole()]

    def perform_create(self, serializer):
        tipo = normalize_kit_type(serializer.validated_data.get("tipo") or "")
        serializer.save(tipo=tipo)

    def perform_update(self, serializer):
        tipo = serializer.validated_data.get("tipo")
        if tipo is not None:
            serializer.save(tipo=normalize_kit_type(tipo))
        else:
            serializer.save()

    @action(detail=False, methods=["get"])
    def alerts(self, request):
        qs = low_stock_products()
        return Response(ProductSerializer(qs, many=True).data)


class MaterialViewSet(viewsets.ModelViewSet):
    permission_module = "inventory"
    queryset = Material.objects.all()
    serializer_class = MaterialSerializer
    filterset_fields = ["active", "sku"]
    search_fields = ["sku", "name"]
    ordering_fields = ["name", "sku", "stock"]

    def get_permissions(self):
        self.module_roles = ["LOGISTICA", "SUPERVISOR", "VIEWER"]
        if self.action in {"list", "retrieve", "alerts"}:
            return [IsModuleRole()]
        self.module_roles = ["LOGISTICA"]
        return [IsModuleRole()]

    @action(detail=False, methods=["get"])
    def alerts(self, request):
        qs = low_stock_materials()
        return Response(MaterialSerializer(qs, many=True).data)


class KardexViewSet(viewsets.ReadOnlyModelViewSet):
    permission_module = "inventory"
    queryset = KardexEntry.objects.select_related("product", "material", "created_by").all()
    serializer_class = KardexEntrySerializer
    filterset_fields = ["item_type", "movement", "reason", "product", "material", "ref_type", "ref_id"]
    search_fields = ["product__sku", "product__name", "material__sku", "material__name", "ref_id", "notes"]
    ordering_fields = ["created_at", "quantity", "balance"]

    def get_permissions(self):
        self.module_roles = ["LOGISTICA", "CONTABILIDAD", "SUPERVISOR", "VIEWER"]
        return [IsModuleRole()]


class ManualEntryView(APIView):
    permission_module = "inventory"
    module_roles = ["LOGISTICA"]
    permission_classes = [IsModuleRole]

    def post(self, request):
        ser = ManualEntrySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        product = None
        material = None
        if data.get("product_id"):
            product = Product.objects.filter(id=data["product_id"]).first()
            if not product:
                return Response({"detail": "Producto no encontrado"}, status=404)
        if data.get("material_id"):
            material = Material.objects.filter(id=data["material_id"]).first()
            if not material:
                return Response({"detail": "Material no encontrado"}, status=404)
        try:
            entry = create_manual_entry(
                product=product,
                material=material,
                movement=data["movement"],
                quantity=data["quantity"],
                reason=data.get("reason") or "MANUAL_ADJUST",
                notes=data.get("notes") or "",
                actor=request.user,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(KardexEntrySerializer(entry).data, status=status.HTTP_201_CREATED)
