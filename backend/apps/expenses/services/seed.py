from __future__ import annotations

from apps.expenses.models import ExpenseStatus

DEFAULT_STATUSES: list[dict] = [
    {
        "key": "REEMBOLSOS_POR_PAGAR",
        "label": "Reembolsos por pagar",
        "order": 10,
        "feeds_efe": False,
        "color": "clay",
    },
    {
        "key": "CUENTAS_POR_PAGAR",
        "label": "Cuentas por pagar",
        "order": 20,
        "feeds_efe": False,
        "color": "clay",
    },
    {
        "key": "GASTOS_POR_REGISTRAR",
        "label": "Gastos por registrar",
        "order": 30,
        "feeds_efe": False,
        "color": "sage",
    },
    {
        "key": "GASTOS_REGISTRADOS",
        "label": "Gastos registrados",
        "order": 40,
        "feeds_efe": True,
        "color": "sage",
    },
    {
        "key": "FACTURAS_PARA_DESCONTAR",
        "label": "Facturas para descontar",
        "order": 50,
        "feeds_efe": False,
        "color": "sage",
    },
    {
        "key": "FACTURAS_DE_DESCUENTO",
        "label": "Facturas de descuento",
        "order": 60,
        "feeds_efe": False,
        "color": "sage",
    },
    {
        "key": "FACTURA_SIN_SOPORTE",
        "label": "Factura sin soporte",
        "order": 70,
        "feeds_efe": False,
        "color": "wine",
    },
    {
        "key": "DOCUMENTO_CONTABLE",
        "label": "Documento contable",
        "order": 80,
        "feeds_efe": False,
        "color": "sage",
    },
    {
        "key": "PAGOS_POR_CONTABILIZAR",
        "label": "Pagos por contabilizar",
        "order": 90,
        "feeds_efe": False,
        "color": "clay",
    },
    {
        "key": "DOCUMENTO_SOPORTE",
        "label": "Documento soporte",
        "order": 100,
        "feeds_efe": False,
        "color": "sage",
    },
]


def seed_expense_statuses(*, actor=None) -> dict:
    created = 0
    updated = 0
    for row in DEFAULT_STATUSES:
        obj, was_created = ExpenseStatus.objects.update_or_create(
            key=row["key"],
            defaults={
                "label": row["label"],
                "order": row["order"],
                "feeds_efe": row["feeds_efe"],
                "color": row.get("color", ""),
                "active": True,
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1
    return {"created": created, "updated": updated, "total": ExpenseStatus.objects.count()}
