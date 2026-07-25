from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils.dateparse import parse_date

from apps.expenses.models import AttachmentKind, Expense, ExpenseAttachment, ExpenseStatus
from apps.expenses.services.transitions import TransitionError, transition_expense
from apps.finance.models import Bank, FinancialAccount


PAYABLE_STATUS_KEYS = ("REEMBOLSOS_POR_PAGAR", "CUENTAS_POR_PAGAR")


def _parse_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return parse_date(str(value))


@transaction.atomic
def mark_payable_paid(
    expense: Expense,
    *,
    payment_date,
    bank_account_id=None,
    efe_account_id=None,
    register_in_efe: bool = False,
    payment_proof=None,
    provider_invoice=None,
    actor=None,
) -> tuple[Expense, list[str]]:
    """
    Cierra un reembolso / cuenta por pagar:
    guarda datos de pago, adjuntos y mueve a gastos (por registrar o registrados).
    """
    if expense.status.key not in PAYABLE_STATUS_KEYS:
        raise TransitionError(
            "Solo se pueden pagar ítems en Reembolsos o Cuentas por pagar."
        )

    pay_date = _parse_date(payment_date)
    if not pay_date:
        raise TransitionError("La fecha de pago es obligatoria.")

    bank = None
    if bank_account_id:
        bank = Bank.objects.filter(id=bank_account_id).first()
        if not bank:
            raise TransitionError("Cuenta bancaria inválida.")

    efe = None
    if efe_account_id:
        efe = FinancialAccount.objects.filter(id=efe_account_id, is_leaf=True).first()
        if not efe:
            raise TransitionError("Cuenta EFE inválida (debe ser hoja).")

    expense.payment_date = pay_date
    if bank:
        expense.bank_account = bank
    if efe:
        expense.efe_account = efe
    # Si no tenía fecha de gasto, usar la de pago
    if not expense.expense_date:
        expense.expense_date = pay_date
    expense.save()

    if payment_proof:
        ExpenseAttachment.objects.create(
            expense=expense,
            kind=AttachmentKind.PAYMENT_PROOF,
            file=payment_proof,
            filename=getattr(payment_proof, "name", "comprobante")[:255],
            mime_type=getattr(payment_proof, "content_type", "") or "",
            uploaded_by=actor,
        )
    if provider_invoice:
        ExpenseAttachment.objects.create(
            expense=expense,
            kind=AttachmentKind.PROVIDER_INVOICE,
            file=provider_invoice,
            filename=getattr(provider_invoice, "name", "factura")[:255],
            mime_type=getattr(provider_invoice, "content_type", "") or "",
            uploaded_by=actor,
        )

    if register_in_efe and expense.efe_account_id and expense.bank_account_id:
        dest_key = "GASTOS_REGISTRADOS"
    else:
        dest_key = "GASTOS_POR_REGISTRAR"

    dest = ExpenseStatus.objects.filter(key=dest_key, active=True).first()
    if not dest:
        raise TransitionError(f"Estado destino {dest_key} no configurado.")

    return transition_expense(expense, status=dest, actor=actor)


def create_payable(
    *,
    kind: str,
    title: str,
    amount,
    expense_date,
    concept: str = "",
    bank_account_id=None,
    efe_account_id=None,
    responsible_id=None,
    actor=None,
) -> Expense:
    key = (
        "REEMBOLSOS_POR_PAGAR"
        if kind == "reembolso"
        else "CUENTAS_POR_PAGAR"
    )
    status = ExpenseStatus.objects.filter(key=key, active=True).first()
    if not status:
        raise TransitionError(f"Estado {key} no configurado. Ejecuta seed_expenses.")

    exp_date = _parse_date(expense_date)
    if not exp_date:
        raise TransitionError("La fecha es obligatoria.")

    amount_dec = Decimal(str(amount or 0))
    if amount_dec <= 0:
        raise TransitionError("El monto debe ser mayor a 0.")

    return Expense.objects.create(
        title=title.strip(),
        concept=(concept or title).strip(),
        amount=amount_dec,
        expense_date=exp_date,
        bank_account_id=bank_account_id or None,
        efe_account_id=efe_account_id or None,
        responsible_id=responsible_id or None,
        status=status,
        created_by=actor,
    )
