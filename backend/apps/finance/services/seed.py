from __future__ import annotations

from apps.finance.models import (
    AccountingAccount,
    AccountingAttribution,
    Bank,
    BankKind,
    ClassificationRule,
    FinancialAccount,
    FinancialAccountKind,
    FinancialSign,
)


# (code, name, kind, is_leaf, parent_code, sign, order)
EFE_SEED: list[tuple] = [
    ("1", "VENTAS NETAS", FinancialAccountKind.VENTAS, False, None, FinancialSign.IN, 10),
    ("1.1", "VENTAS EARSEEDING", FinancialAccountKind.VENTAS, False, "1", FinancialSign.IN, 11),
    ("1.1.1", "Adquisición", FinancialAccountKind.VENTAS, False, "1.1", FinancialSign.IN, 12),
    ("1.1.1.1", "Ecommerce", FinancialAccountKind.VENTAS, True, "1.1.1", FinancialSign.IN, 13),
    ("1.1.1.2", "Kommo", FinancialAccountKind.VENTAS, True, "1.1.1", FinancialSign.IN, 14),
    ("1.1.2", "MRR (recurrente)", FinancialAccountKind.VENTAS, False, "1.1", FinancialSign.IN, 15),
    ("1.1.2.1", "Ecommerce", FinancialAccountKind.VENTAS, True, "1.1.2", FinancialSign.IN, 16),
    ("1.1.2.2", "Kommo", FinancialAccountKind.VENTAS, True, "1.1.2", FinancialSign.IN, 17),
    ("1.1.3", "Ferias", FinancialAccountKind.VENTAS, True, "1.1", FinancialSign.IN, 18),
    ("1.2", "Ventas flete", FinancialAccountKind.VENTAS, True, "1", FinancialSign.IN, 19),
    ("1.3", "Devolución en ventas", FinancialAccountKind.VENTAS, True, "1", FinancialSign.OUT, 20),
    ("3", "COGS", FinancialAccountKind.COGS, False, None, FinancialSign.OUT, 30),
    ("3.1", "Raw M", FinancialAccountKind.COGS, True, "3", FinancialSign.OUT, 31),
    ("3.2", "Manual", FinancialAccountKind.COGS, True, "3", FinancialSign.OUT, 32),
    ("3.3", "Sobre", FinancialAccountKind.COGS, True, "3", FinancialSign.OUT, 33),
    ("3.4", "Caja", FinancialAccountKind.COGS, True, "3", FinancialSign.OUT, 34),
    ("3.5", "Bolsa envío", FinancialAccountKind.COGS, True, "3", FinancialSign.OUT, 35),
    ("4", "INGRESO (RECAUDO)", FinancialAccountKind.INGRESO, False, None, FinancialSign.IN, 40),
    ("4.3.2", "Rendimientos financieros", FinancialAccountKind.INGRESO, True, "4", FinancialSign.IN, 41),
    ("4.4", "Auditoría ingresos", FinancialAccountKind.INGRESO, False, "4", FinancialSign.IN, 42),
    ("4.4.1", "Recaudo mes distinto", FinancialAccountKind.INGRESO, True, "4.4", FinancialSign.IN, 43),
    ("4.4.2", "Pago incompleto", FinancialAccountKind.INGRESO, True, "4.4", FinancialSign.IN, 44),
    ("4.4.3", "Otros ajustes auditoría", FinancialAccountKind.INGRESO, True, "4.4", FinancialSign.IN, 45),
    ("5", "GASTO ADMINISTRATIVO", FinancialAccountKind.ADMIN, False, None, FinancialSign.OUT, 50),
    ("5.1", "Personal administrativo", FinancialAccountKind.ADMIN, True, "5", FinancialSign.OUT, 51),
    ("6", "COSTOS OPERATIVOS", FinancialAccountKind.COSTO, False, None, FinancialSign.OUT, 60),
    ("6.1.1", "Salarios domicilios", FinancialAccountKind.COSTO, True, "6", FinancialSign.OUT, 61),
    ("6.1.4", "Warehousing", FinancialAccountKind.COSTO, True, "6", FinancialSign.OUT, 62),
    ("6.4", "Otros costos operativos", FinancialAccountKind.COSTO, True, "6", FinancialSign.OUT, 63),
    ("7", "GASTOS", FinancialAccountKind.GASTO, False, None, FinancialSign.OUT, 70),
    ("7.1", "Publicidad", FinancialAccountKind.GASTO, True, "7", FinancialSign.OUT, 71),
    ("7.2", "Gastos publicidad", FinancialAccountKind.GASTO, True, "7", FinancialSign.OUT, 72),
    ("7.3", "Personal ventas", FinancialAccountKind.GASTO, True, "7", FinancialSign.OUT, 73),
    ("7.4", "Comisión pasarela", FinancialAccountKind.GASTO, True, "7", FinancialSign.OUT, 74),
    ("7.5", "4x1000 / impuestos bancarios", FinancialAccountKind.GASTO, True, "7", FinancialSign.OUT, 75),
    ("8", "OTROS PASIVOS", FinancialAccountKind.PASIVO, False, None, "", 80),
    ("8.1", "Transferencias interbancarias", FinancialAccountKind.PASIVO, True, "8", "", 81),
]

PUC_SEED = [
    ("1105", "Caja", AccountingAttribution.COMPARTIDO),
    ("1110", "Bancos", AccountingAttribution.COMPARTIDO),
    ("1305", "Clientes", AccountingAttribution.VENTAS),
    ("5105", "Gastos de personal", AccountingAttribution.ADMINISTRATIVO),
    ("51", "Gastos de administración", AccountingAttribution.ADMINISTRATIVO),
    ("5205", "Gastos de personal ventas", AccountingAttribution.VENTAS),
    ("53", "Gastos financieros", AccountingAttribution.COMPARTIDO),
    ("5305", "Comisiones bancarias", AccountingAttribution.COMPARTIDO),
    ("5315", "Impuestos bancarios 4x1000", AccountingAttribution.COMPARTIDO),
    ("6135", "Costo de ventas", AccountingAttribution.OPERACIONAL),
]

BANK_SEED = [
    {
        "name": "BANCOLOMBIA",
        "kind": BankKind.BANK,
        "account_no": "60100006016",
        "importer": "bancolombia",
        "report_aliases": ["Bancolombia Seeds", "Bancolombia", "Bancolombia Maji"],
    },
    {
        "name": "MERCADO PAGO",
        "kind": BankKind.GATEWAY,
        "account_no": "",
        "importer": "mercadopago",
        "report_aliases": ["Mercadopago", "Mercado Pago", "MercadoPago"],
    },
    {
        "name": "BOLD",
        "kind": BankKind.GATEWAY,
        "account_no": "",
        "importer": "bold",
        "report_aliases": ["Tarjeta (Bold)", "Bold", "BOLD"],
    },
    {
        "name": "NEQUI",
        "kind": BankKind.GATEWAY,
        "account_no": "",
        "importer": "nequi",
        "report_aliases": ["Nequi", "Nequi Maji"],
    },
    {
        "name": "EFECTIVO",
        "kind": BankKind.CASH,
        "account_no": "",
        "importer": "",
        "report_aliases": ["Efectivo", "Efectivo Maji", "Efectivo Cami", "Efectivo Dani"],
    },
    {
        "name": "PAYU",
        "kind": BankKind.GATEWAY,
        "account_no": "",
        "importer": "",
        "report_aliases": ["PayU", "Payu", "PAYU"],
    },
]


def seed_finance(*, actor=None) -> dict:
    by_code: dict[str, FinancialAccount] = {}
    efe_created = 0
    for code, name, kind, is_leaf, parent_code, sign, order in EFE_SEED:
        parent = by_code.get(parent_code) if parent_code else None
        obj, created = FinancialAccount.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "full_label": f"{code}. {name}",
                "parent": parent,
                "kind": kind,
                "is_leaf": is_leaf,
                "sign": sign or "",
                "active": True,
                "order": order,
            },
        )
        by_code[code] = obj
        if created:
            efe_created += 1

    puc_created = 0
    for code, name, attr in PUC_SEED:
        _, created = AccountingAccount.objects.update_or_create(
            code=code,
            defaults={"name": name, "attribution": attr, "active": True},
        )
        if created:
            puc_created += 1

    banks_created = 0
    banks: dict[str, Bank] = {}
    for row in BANK_SEED:
        obj, created = Bank.objects.update_or_create(
            name=row["name"],
            defaults={
                "kind": row["kind"],
                "account_no": row["account_no"],
                "importer": row["importer"],
                "active": True,
                "report_aliases": row["report_aliases"],
            },
        )
        banks[obj.name] = obj
        if created:
            banks_created += 1

    interbank = by_code.get("8.1")
    commission = by_code.get("7.4")
    tax_4x = by_code.get("7.5")
    yields_acc = by_code.get("4.3.2")
    puc_comm = AccountingAccount.objects.filter(code="5305").first()
    puc_tax = AccountingAccount.objects.filter(code="5315").first()

    rules = [
        {
            "name": "Interbancario Bancolombia",
            "bank": banks.get("BANCOLOMBIA"),
            "concept_contains": "PAGO INTERBANCARIOS",
            "financial_account": interbank,
            "is_interbank": True,
            "priority": 10,
        },
        {
            "name": "Transferencia virtual → ingreso",
            "bank": banks.get("BANCOLOMBIA"),
            "concept_contains": "TRANSFERENCIA CTA SUC VIRTUAL",
            "financial_account": None,
            "is_interbank": False,
            "priority": 50,
            "auto_apply": False,
        },
        {
            "name": "4x1000",
            "bank": banks.get("BANCOLOMBIA"),
            "concept_contains": "IMPTO GOBIERNO 4X1000",
            "financial_account": tax_4x,
            "accounting_account": puc_tax,
            "attribution": AccountingAttribution.COMPARTIDO,
            "priority": 20,
        },
        {
            "name": "Comisión MercadoPago",
            "bank": banks.get("MERCADO PAGO"),
            "concept_contains": "Cargo por cobrar",
            "financial_account": commission,
            "accounting_account": puc_comm,
            "attribution": AccountingAttribution.COMPARTIDO,
            "priority": 20,
        },
        {
            "name": "Rendimientos",
            "bank": None,
            "concept_contains": "RENDIMIENTO",
            "financial_account": yields_acc,
            "priority": 30,
        },
    ]
    rules_created = 0
    for r in rules:
        _, created = ClassificationRule.objects.update_or_create(
            name=r["name"],
            defaults={
                "bank": r.get("bank"),
                "concept_contains": r["concept_contains"],
                "financial_account": r.get("financial_account"),
                "accounting_account": r.get("accounting_account"),
                "attribution": r.get("attribution", ""),
                "is_interbank": r.get("is_interbank", False),
                "priority": r.get("priority", 100),
                "active": True,
                "auto_apply": r.get("auto_apply", True),
            },
        )
        if created:
            rules_created += 1

    return {
        "efe_created": efe_created,
        "efe_total": FinancialAccount.objects.count(),
        "puc_created": puc_created,
        "banks_created": banks_created,
        "rules_created": rules_created,
    }
