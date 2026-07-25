from __future__ import annotations

from decimal import Decimal
from typing import Callable

from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.utils import timezone

ResolverResult = dict  # {value, amount?, meta?}


def _dec(v) -> Decimal:
    return Decimal(v or 0)


def gastos_sin_factura() -> ResolverResult:
    from apps.expenses.models import AttachmentKind, Expense, ExpenseAttachment, ExpenseNature

    has_inv = ExpenseAttachment.objects.filter(
        expense_id=OuterRef("pk"), kind=AttachmentKind.PROVIDER_INVOICE
    )
    qs = Expense.objects.filter(nature=ExpenseNature.EMPRESA).filter(
        Q(status__key="FACTURA_SIN_SOPORTE") | ~Exists(has_inv)
    )
    agg = qs.aggregate(c=Count("id"), s=Sum("amount"))
    return {"value": agg["c"] or 0, "amount": _dec(agg["s"])}


def gastos_sin_comprobante() -> ResolverResult:
    from apps.expenses.models import AttachmentKind, Expense, ExpenseAttachment, ExpenseNature

    has_proof = ExpenseAttachment.objects.filter(
        expense_id=OuterRef("pk"), kind=AttachmentKind.PAYMENT_PROOF
    )
    qs = Expense.objects.filter(nature=ExpenseNature.EMPRESA).filter(~Exists(has_proof))
    agg = qs.aggregate(c=Count("id"), s=Sum("amount"))
    return {"value": agg["c"] or 0, "amount": _dec(agg["s"])}


def gastos_sin_cuenta_efe() -> ResolverResult:
    from apps.expenses.models import Expense, ExpenseNature

    qs = Expense.objects.filter(
        nature=ExpenseNature.EMPRESA,
        status__feeds_efe=True,
        efe_account__isnull=True,
    )
    agg = qs.aggregate(c=Count("id"), s=Sum("amount"))
    return {"value": agg["c"] or 0, "amount": _dec(agg["s"])}


def reembolsos_por_pagar() -> ResolverResult:
    from apps.expenses.models import Expense, ExpenseNature

    qs = Expense.objects.filter(
        nature=ExpenseNature.EMPRESA, status__key="REEMBOLSOS_POR_PAGAR"
    )
    agg = qs.aggregate(c=Count("id"), s=Sum("amount"))
    return {"value": agg["c"] or 0, "amount": _dec(agg["s"])}


def cuentas_por_pagar() -> ResolverResult:
    from apps.expenses.models import Expense, ExpenseNature

    qs = Expense.objects.filter(
        nature=ExpenseNature.EMPRESA, status__key="CUENTAS_POR_PAGAR"
    )
    agg = qs.aggregate(c=Count("id"), s=Sum("amount"))
    return {"value": agg["c"] or 0, "amount": _dec(agg["s"])}


def iva_por_descontar() -> ResolverResult:
    from apps.expenses.models import Expense, ExpenseNature

    qs = Expense.objects.filter(
        nature=ExpenseNature.EMPRESA,
        iva_discountable__isnull=False,
        iva_already_discounted=False,
    ).exclude(iva_discountable=0)
    agg = qs.aggregate(c=Count("id"), s=Sum("iva_discountable"))
    return {"value": agg["c"] or 0, "amount": _dec(agg["s"])}


def gastos_sin_conciliar() -> ResolverResult:
    from apps.expenses.models import Expense, ExpenseNature

    qs = Expense.objects.filter(
        nature=ExpenseNature.EMPRESA,
        status__feeds_efe=True,
        bank_movement__isnull=True,
    )
    agg = qs.aggregate(c=Count("id"), s=Sum("amount"))
    return {"value": agg["c"] or 0, "amount": _dec(agg["s"])}


def movimientos_sin_clasificar() -> ResolverResult:
    from apps.finance.models import BankMovement, MovementStatus

    pending = BankMovement.objects.filter(status=MovementStatus.POR_CLASIFICAR).count()
    total = BankMovement.objects.count()
    pct = (Decimal(total - pending) / Decimal(total) * 100) if total else Decimal(100)
    return {"value": pending, "amount": None, "meta": {"pct_classified": float(pct)}}


def egresos_sin_gasto() -> ResolverResult:
    from apps.expenses.models import Expense
    from apps.finance.models import BankMovement, MovementItem

    linked = Expense.objects.exclude(bank_movement_id=None).values_list(
        "bank_movement_id", flat=True
    )
    qs = BankMovement.objects.filter(item=MovementItem.EGRESO).exclude(id__in=linked)
    agg = qs.aggregate(c=Count("id"), s=Sum("value"))
    return {"value": agg["c"] or 0, "amount": abs(_dec(agg["s"]))}


def facturas_fallidas() -> ResolverResult:
    from apps.accounting.models import Invoice, InvoiceStatus

    qs = Invoice.objects.filter(status=InvoiceStatus.FALLIDA)
    agg = qs.aggregate(c=Count("id"), s=Sum("total"))
    return {"value": agg["c"] or 0, "amount": _dec(agg["s"])}


def facturas_por_generar() -> ResolverResult:
    from apps.accounting.models import Invoice, InvoiceStatus

    qs = Invoice.objects.filter(status=InvoiceStatus.POR_GENERAR)
    agg = qs.aggregate(c=Count("id"), s=Sum("total"))
    return {"value": agg["c"] or 0, "amount": _dec(agg["s"])}


def facturas_enviando_colgadas() -> ResolverResult:
    from datetime import timedelta

    from apps.accounting.models import Invoice, InvoiceStatus

    cutoff = timezone.now() - timedelta(hours=2)
    qs = Invoice.objects.filter(status=InvoiceStatus.ENVIANDO, updated_at__lt=cutoff)
    return {"value": qs.count(), "amount": None}


def clientes_sin_alegra() -> ResolverResult:
    from apps.accounting.models import Customer

    return {"value": Customer.objects.filter(alegra_synced=False).count(), "amount": None}


def reembolsos_anulacion_pendiente() -> ResolverResult:
    from apps.accounting.models import Refund

    return {
        "value": Refund.objects.filter(manual_void_pending=True).count(),
        "amount": None,
    }


def ventas_sin_vendedor() -> ResolverResult:
    from apps.sales.models import ConsolidatedSale, SaleState

    qs = ConsolidatedSale.objects.filter(
        state=SaleState.ACTIVE, seller__isnull=True
    )
    return {"value": qs.count(), "amount": None}


def webhooks_fallidos() -> ResolverResult:
    try:
        from apps.integrations.models import RawWebhookEvent

        return {
            "value": RawWebhookEvent.objects.filter(status="FAILED").count(),
            "amount": None,
        }
    except Exception:
        return {"value": 0, "amount": None}


def guias_fallidas() -> ResolverResult:
    from apps.logistics.models import Shipment, ShipmentStatus
    from apps.logistics.services.shipments import operational_shipments

    qs = operational_shipments(
        Shipment.objects.filter(status=ShipmentStatus.GUIA_FALLIDA)
    )
    return {"value": qs.count(), "amount": None}


def pedidos_por_generar_guia() -> ResolverResult:
    from apps.logistics.models import Shipment, ShipmentStatus
    from apps.logistics.services.shipments import operational_shipments

    qs = operational_shipments(
        Shipment.objects.filter(status=ShipmentStatus.POR_GENERAR)
    )
    return {"value": qs.count(), "amount": None}


def guias_con_warning() -> ResolverResult:
    from apps.logistics.models import Shipment
    from apps.logistics.services.shipments import operational_shipments

    qs = operational_shipments(Shipment.objects.filter(warning=True))
    return {"value": qs.count(), "amount": None}


def listos_sin_despachar() -> ResolverResult:
    from apps.logistics.models import Shipment, ShipmentStatus
    from apps.logistics.services.shipments import operational_shipments

    qs = operational_shipments(
        Shipment.objects.filter(status=ShipmentStatus.LISTO_PARA_ENVIAR)
    )
    return {"value": qs.count(), "amount": None}


def stock_bajo() -> ResolverResult:
    from django.db.models import F

    from apps.inventory.models import Product

    return {
        "value": Product.objects.filter(active=True, stock__lte=F("reorder_level")).count(),
        "amount": None,
    }


def stock_negativo() -> ResolverResult:
    try:
        from apps.inventory.models import Product

        return {
            "value": Product.objects.filter(stock__lt=0).count(),
            "amount": None,
        }
    except Exception:
        return {"value": 0, "amount": None}


RESOLVERS: dict[str, Callable[[], ResolverResult]] = {
    "gastos_sin_factura": gastos_sin_factura,
    "gastos_sin_comprobante": gastos_sin_comprobante,
    "gastos_sin_cuenta_efe": gastos_sin_cuenta_efe,
    "reembolsos_por_pagar": reembolsos_por_pagar,
    "cuentas_por_pagar": cuentas_por_pagar,
    "iva_por_descontar": iva_por_descontar,
    "gastos_sin_conciliar": gastos_sin_conciliar,
    "movimientos_sin_clasificar": movimientos_sin_clasificar,
    "egresos_sin_gasto": egresos_sin_gasto,
    "facturas_fallidas": facturas_fallidas,
    "facturas_por_generar": facturas_por_generar,
    "facturas_enviando_colgadas": facturas_enviando_colgadas,
    "clientes_sin_alegra": clientes_sin_alegra,
    "reembolsos_anulacion_pendiente": reembolsos_anulacion_pendiente,
    "ventas_sin_vendedor": ventas_sin_vendedor,
    "webhooks_fallidos": webhooks_fallidos,
    "guias_fallidas": guias_fallidas,
    "pedidos_por_generar_guia": pedidos_por_generar_guia,
    "guias_con_warning": guias_con_warning,
    "listos_sin_despachar": listos_sin_despachar,
    "stock_bajo": stock_bajo,
    "stock_negativo": stock_negativo,
}


def resolve(key: str) -> ResolverResult:
    fn = RESOLVERS.get(key)
    if not fn:
        return {"value": 0, "amount": None, "meta": {"error": "resolver_missing"}}
    try:
        return fn()
    except Exception as exc:
        return {"value": 0, "amount": None, "meta": {"error": str(exc)}}
