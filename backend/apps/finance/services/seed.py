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

V = FinancialAccountKind.VENTAS
C = FinancialAccountKind.COGS
I = FinancialAccountKind.INGRESO
O = FinancialAccountKind.COSTO  # operativo
G = FinancialAccountKind.GASTO
P = FinancialAccountKind.PASIVO
A = FinancialAccountKind.AJUSTE
D = FinancialAccountKind.ADMIN  # administrativo
IN = FinancialSign.IN
OUT = FinancialSign.OUT

# (code, name, kind, is_leaf, parent_code, sign, order)
# Árbol completo del modelo financiero Seeds (fuente: plan EFE operativo).
EFE_SEED: list[tuple] = [
    # --- Liquidez apertura ---
    ("0", "Bancos a principio de mes", A, True, None, "", 1),
    # --- 1. Ventas ---
    ("1", "VENTAS NETAS", V, False, None, IN, 10),
    ("1.1", "VENTAS EARSEEDING", V, False, "1", IN, 11),
    ("1.1.1", "Adquisición", V, False, "1.1", IN, 12),
    ("1.1.1.1", "Ecommerce", V, True, "1.1.1", IN, 13),
    ("1.1.1.2", "Kommo", V, True, "1.1.1", IN, 14),
    ("1.1.2", "MRR", V, False, "1.1", IN, 15),
    ("1.1.2.1", "Ecommerce", V, True, "1.1.2", IN, 16),
    ("1.1.2.2", "Kommo", V, True, "1.1.2", IN, 17),
    ("1.1.3", "FERIAS", V, True, "1.1", IN, 18),
    ("1.2", "VENTAS FLETE", V, True, "1", IN, 19),
    ("1.3", "DEVOLUCIÓN EN VENTAS", V, True, "1", OUT, 20),
    ("2", "IVA GENERADO (CON DESCONTABLE)", A, True, None, "", 25),
    # --- 4. Ingreso / recaudo (antes de COGS en el modelo de caja) ---
    ("4", "INGRESO (RECAUDO)", I, False, None, IN, 40),
    ("4.1", "INGRESO OPERACIONAL (RECAUDO)", I, False, "4", IN, 41),
    ("4.1.1", "EARSEEDING Adquisición", I, True, "4.1", IN, 42),
    ("4.1.2", "EARSEEDING MRR", I, True, "4.1", IN, 43),
    ("4.2", "INGRESO FLETE", I, True, "4", IN, 44),
    ("4.3", "INGRESO NO OPERACIONAL (RECAUDO)", I, False, "4", IN, 45),
    ("4.3.1", "Ingreso de IVA GENERADO", I, True, "4.3", IN, 46),
    ("4.3.2", "Rendimientos financieros", I, True, "4.3", IN, 47),
    ("4.5", "DEVOLUCIÓN EN VENTAS", I, True, "4", OUT, 48),
    ("4.4", "AUDITORIA INGRESOS", I, False, "4", IN, 49),
    ("4.4.1", "Recaudo en mes diferente", I, True, "4.4", IN, 50),
    ("4.4.2", "No entro pago", I, True, "4.4", IN, 51),
    ("4.4.3", "Pago incompleto", I, True, "4.4", IN, 52),
    # --- 3. COGS ---
    ("3", "COGS", C, False, None, OUT, 60),
    ("3.1", "Raw M", C, True, "3", OUT, 61),
    ("3.2", "Manual", C, True, "3", OUT, 62),
    ("3.3", "Sobre", C, True, "3", OUT, 63),
    ("3.4", "Caja", C, True, "3", OUT, 64),
    ("3.5", "Bolsa envio", C, True, "3", OUT, 65),
    # --- 6. Costos operativos ---
    ("6", "COSTOS OPERATIVOS", O, False, None, OUT, 70),
    ("6.1", "COSTOS OPERATIVOS", O, False, "6", OUT, 71),
    ("6.1.1", "Salarios y honorarios domicilios", O, False, "6.1", OUT, 72),
    ("6.1.1.1", "Salarios y honorarios", O, True, "6.1.1", OUT, 73),
    ("6.1.1.2", "Seguridad social", O, True, "6.1.1", OUT, 74),
    ("6.1.1.3", "Pago a proveedores", O, True, "6.1.1", OUT, 75),
    ("6.1.1.4", "CUENTA TRANSITORIA: APROVISIONAMIENTOS", O, True, "6.1.1", OUT, 76),
    ("6.1.2", "Personal Overhead", O, False, "6.1", OUT, 77),
    ("6.1.2.1", "Salarios y honorarios", O, True, "6.1.2", OUT, 78),
    ("6.1.2.2", "Seguridad social", O, True, "6.1.2", OUT, 79),
    ("6.1.2.3", "CUENTA TRANSITORIA: APROVISIONAMIENTOS", O, True, "6.1.2", OUT, 80),
    ("6.1.3", "Salarios y honorarios empaquetado", O, False, "6.1", OUT, 81),
    ("6.1.3.1", "Salarios y honorarios", O, True, "6.1.3", OUT, 82),
    ("6.1.3.2", "Seguridad social", O, True, "6.1.3", OUT, 83),
    ("6.1.3.3", "Pago a proveedores", O, True, "6.1.3", OUT, 84),
    ("6.1.4", "Warehousin", O, True, "6.1", OUT, 85),
    ("6.1.5", "Replenishment", O, True, "6.1", OUT, 86),
    ("6.1.6", "Almacenamiento en puerto", O, True, "6.1", OUT, 87),
    ("6.2", "OTROS COSTOS OPERATIVOS", O, False, "6", OUT, 88),
    ("6.4.1", "Otros costos operativos", O, False, "6.2", OUT, 89),
    ("6.4.1.1", "Activos digitales enfocados en la operación / producto", O, True, "6.4.1", OUT, 90),
    ("6.4.1.2", "Licencias", O, True, "6.4.1", OUT, 91),
    ("6.4.1.3", "Servidores", O, True, "6.4.1", OUT, 92),
    # --- 7. Gastos (comercial / publicidad) ---
    ("7", "GASTOS", G, False, None, OUT, 100),
    ("7.1", "GASTO PERSONAL PUBLICIDAD", G, False, "7", OUT, 101),
    ("7.1.1", "Personal adquisición", G, False, "7.1", OUT, 102),
    ("7.1.1.1", "Salarios y honorarios", G, True, "7.1.1", OUT, 103),
    ("7.1.1.2", "Seguridad social", G, True, "7.1.1", OUT, 104),
    ("7.1.1.3", "CUENTA TRANSITORIA: APROVISIONAMIENTOS", G, True, "7.1.1", OUT, 105),
    ("7.1.2", "Otros gastos de personal adquisición", G, True, "7.1", OUT, 106),
    ("7.2", "GASTOS DE PUBLICIDAD", G, True, "7", OUT, 107),
    ("7.3", "GASTO PERSONAL VENTAS", G, False, "7", OUT, 108),
    ("7.3.1", "Personal ventas", G, False, "7.3", OUT, 109),
    ("7.3.1.1", "Salarios y honorarios", G, True, "7.3.1", OUT, 110),
    ("7.3.1.2", "Seguridad social", G, True, "7.3.1", OUT, 111),
    ("7.3.1.3", "Otras bonificaciones (OPS)", G, True, "7.3.1", OUT, 112),
    ("7.3.1.4", "CUENTA TRANSITORIA: APROVISIONAMIENTOS", G, True, "7.3.1", OUT, 113),
    ("7.3.2", "Otros gastos de personal ventas", G, True, "7.3", OUT, 114),
    ("7.3.3", "Honorarios Ventas (Vacaciones)", G, True, "7.3", OUT, 115),
    ("7.3.4", "Personal MRR", G, False, "7.3", OUT, 116),
    ("7.3.4.1", "Salarios y honorarios", G, True, "7.3.4", OUT, 117),
    ("7.3.4.2", "Seguridad social", G, True, "7.3.4", OUT, 118),
    ("7.3.4.3", "CUENTA TRANSITORIA: APROVISIONAMIENTOS", G, True, "7.3.4", OUT, 119),
    ("7.3.5", "Otros gastos de personal MRR", G, True, "7.3", OUT, 120),
    # --- 5. Gasto administrativo ---
    ("5", "GASTO ADMINISTRATIVO", D, False, None, OUT, 130),
    ("5.1", "GASTO PERSONAL ADMINISTRATIVO", D, False, "5", OUT, 131),
    ("5.1.1", "Gerencia", D, False, "5.1", OUT, 132),
    ("5.1.1.1", "Salarios y honorarios", D, True, "5.1.1", OUT, 133),
    ("5.1.1.2", "Seguridad social", D, True, "5.1.1", OUT, 134),
    ("5.1.1.3", "CUENTA TRANSITORIA: APROVISIONAMIENTOS", D, True, "5.1.1", OUT, 135),
    ("5.1.2", "Contabilidad y finanzas", D, False, "5.1", OUT, 136),
    ("5.1.2.1", "Salarios y honorarios", D, True, "5.1.2", OUT, 137),
    ("5.1.2.2", "Seguridad social", D, True, "5.1.2", OUT, 138),
    ("5.1.2.3", "CUENTA TRANSITORIA: APROVISIONAMIENTOS", D, True, "5.1.2", OUT, 139),
    ("5.1.2.4", "Telefonía", D, True, "5.1.2", OUT, 140),
    ("5.1.2.5", "Sistemas contables", D, True, "5.1.2", OUT, 141),
    ("5.1.3", "Servicios generales", D, False, "5.1", OUT, 142),
    ("5.1.3.1", "Salarios y honorarios", D, True, "5.1.3", OUT, 143),
    ("5.1.3.2", "Seguridad social", D, True, "5.1.3", OUT, 144),
    ("5.1.3.3", "CUENTA TRANSITORIA: APROVISIONAMIENTOS", D, True, "5.1.3", OUT, 145),
    ("5.1.4", "Recursos humanos", D, False, "5.1", OUT, 146),
    ("5.1.4.1", "Salarios y honorarios", D, True, "5.1.4", OUT, 147),
    ("5.1.4.2", "Seguridad social", D, True, "5.1.4", OUT, 148),
    ("5.1.4.3", "CUENTA TRANSITORIA: APROVISIONAMIENTOS", D, True, "5.1.4", OUT, 149),
    ("5.1.4.4", "Telefonía", D, True, "5.1.4", OUT, 150),
    ("5.1.4.5", "Otros costos de RRHH", D, True, "5.1.4", OUT, 151),
    ("5.1.5", "Legal", D, False, "5.1", OUT, 152),
    ("5.1.5.1", "Salarios y honorarios", D, True, "5.1.5", OUT, 153),
    ("5.1.5.2", "Seguridad social", D, True, "5.1.5", OUT, 154),
    ("5.1.5.3", "CUENTA TRANSITORIA: APROVISIONAMIENTOS", D, True, "5.1.5", OUT, 155),
    ("5.1.5.4", "Otros costos Legales", D, True, "5.1.5", OUT, 156),
    ("5.2", "ARRENDAMIENTO", D, False, "5", OUT, 157),
    ("5.2.1", "Arriendo oficina", D, True, "5.2", OUT, 158),
    ("5.2.2", "IVA Causado", D, True, "5.2", OUT, 159),
    ("5.3", "SERVICIOS", D, False, "5", OUT, 160),
    ("5.3.1", "Servicios publicos", D, True, "5.3", OUT, 161),
    ("5.3.2", "Seguridad", D, True, "5.3", OUT, 162),
    ("5.3.3", "Internet", D, True, "5.3", OUT, 163),
    ("5.3.4", "Otros servicios", D, True, "5.3", OUT, 164),
    ("5.4", "OTROS GASTOS ADMINISTRATIVOS", D, False, "5", OUT, 165),
    ("5.4.1", "Seguros", D, True, "5.4", OUT, 166),
    ("5.4.2", "Gastos legales", D, True, "5.4", OUT, 167),
    ("5.4.3", "Mantenimiento y reparaciones", D, True, "5.4", OUT, 168),
    ("5.4.4", "Gastos de viaje", D, True, "5.4", OUT, 169),
    ("5.4.7", "Diversos", D, True, "5.4", OUT, 170),
    ("5.4.8", "Honorarios (Vacaciones)", D, True, "5.4", OUT, 171),
    ("5.9", "Cuentas transitorias administrativas", D, False, "5", OUT, 172),
    ("5.9.1", "CUENTA TRANSITORIA: Amortizaciones Administrativo", D, True, "5.9", OUT, 173),
    ("5.9.2", "CUENTA TRANSITORIA: Depreciaciones Administrativo", D, True, "5.9", OUT, 174),
    # --- 9. Impuestos ---
    ("9", "IMPUESTOS", A, False, None, OUT, 180),
    ("9.0", "CUENTA TRANSITORIA: Reteica (ilustrativo)", A, True, "9", OUT, 181),
    ("9.1", "ICA PAGADO", A, True, "9", OUT, 182),
    ("9.2", "ICA GENERADO", A, True, "9", OUT, 183),
    ("9.3", "IVA GENERADO", A, True, "9", OUT, 184),
    ("9.4", "IVA PAGADO", A, True, "9", OUT, 185),
    ("9.5", "RENTA PAGADA", A, True, "9", OUT, 186),
    ("9.6", "RETEFUENTE PAGADA", A, True, "9", OUT, 187),
    ("9.7", "GASTOS NO DEDUCIBLES", A, True, "9", OUT, 188),
    ("9.8", "Diferencia en cambio", A, True, "9", OUT, 189),
    # --- 10. Gastos bancarios / pasarela (alimentados por extracto bancario) ---
    ("10", "Gastos Bancarios", A, False, None, OUT, 190),
    ("10.1", "Bancolombia GF", A, False, "10", OUT, 191),
    ("10.1.1", "Gastos fijos mensuales BGF", A, True, "10.1", OUT, 192),
    ("10.1.2", "Comisiones BGF", A, True, "10.1", OUT, 193),
    ("10.1.3", "Impuestos BGF", A, True, "10.1", OUT, 194),
    ("10.1.4", "4x1000 BGF", A, True, "10.1", OUT, 195),
    ("10.2", "Mercado pago GF", A, False, "10", OUT, 196),
    ("10.2.1", "Comision MGF", A, True, "10.2", OUT, 197),
    # Compat con reglas/clasificaciones previas
    ("7.4", "Comisión pasarela (legacy → 10.2.1)", A, True, "7", OUT, 198),
    ("7.5", "4x1000 / impuestos bancarios (legacy → 10.1.4)", A, True, "7", OUT, 199),
    # --- 11. Activo ---
    ("11", "ACTIVO", A, False, None, "", 210),
    ("11.1", "Compra de PPE", A, False, "11", "", 211),
    ("11.1.1", "Atribuible", A, True, "11.1", "", 212),
    ("11.1.2", "No atribuible", A, True, "11.1", "", 213),
    ("11.2", "Diferido", A, False, "11", "", 214),
    ("11.2.1", "Diferido Administrativo", A, True, "11.2", "", 215),
    ("11.2.2", "Diferido Operaciones", A, True, "11.2", "", 216),
    ("11.2.3", "Diferido Ventas", A, True, "11.2", "", 217),
    # --- 8. Pasivo ---
    ("8", "PASIVO", P, False, None, "", 220),
    ("8.1", "Transferencias interbancarias", P, True, "8", "", 221),
    ("8.2", "Nomina", P, True, "8", "", 222),
    ("8.3", "Cesantias", P, True, "8", "", 223),
    ("8.4", "Int Cesantias", P, True, "8", "", 224),
    ("8.5", "Vacaciones", P, True, "8", "", 225),
    ("8.6", "Liquidaciones", P, True, "8", "", 226),
    ("8.7", "Prima", P, True, "8", "", 227),
    ("8.8", "CUENTA TRANSITORIA: Retenciones para pago de planilla", P, True, "8", "", 228),
    ("8.9", "Otros", P, False, "8", "", 229),
    ("8.9.1", "Otros pasivos", P, True, "8.9", "", 230),
    ("8.9.2", "Dividendos", P, True, "8.9", "", 231),
    ("8.9.3", "Pauta acumulada", P, True, "8.9", "", 232),
    # --- 12. Cierre de bancos / EFE liquidez ---
    ("12", "EFE / bancos", A, False, None, "", 240),
    ("12.1", "EFE", A, True, "12", "", 241),
    ("12.2", "EFE - AHORRO", A, True, "12", "", 242),
    ("12.3", "BANCOS FIN DE MES", A, True, "12", "", 243),
    ("12.4", "BANCOS ACTUALES", A, True, "12", "", 244),
    ("12.5", "DIFERENCIA", A, True, "12", "", 245),
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
    efe_updated = 0
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
        # Parent may have been created later in a previous run without children —
        # refresh parent FK if the parent code now exists.
        if parent_code and obj.parent_id != (parent.id if parent else None):
            obj.parent = parent
            obj.save(update_fields=["parent", "updated_at"])
        by_code[code] = obj
        if created:
            efe_created += 1
        else:
            efe_updated += 1

    # Second pass: ensure parents point correctly once all codes exist.
    for code, name, kind, is_leaf, parent_code, sign, order in EFE_SEED:
        obj = by_code[code]
        parent = by_code.get(parent_code) if parent_code else None
        desired_parent_id = parent.id if parent else None
        if obj.parent_id != desired_parent_id:
            obj.parent = parent
            obj.save(update_fields=["parent", "updated_at"])

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
    commission = by_code.get("10.2.1") or by_code.get("7.4")
    tax_4x = by_code.get("10.1.4") or by_code.get("7.5")
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
        "efe_updated": efe_updated,
        "efe_total": FinancialAccount.objects.filter(active=True).count(),
        "efe_seed_rows": len(EFE_SEED),
        "puc_created": puc_created,
        "banks_created": banks_created,
        "rules_created": rules_created,
    }
