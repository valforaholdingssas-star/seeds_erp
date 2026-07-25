from __future__ import annotations

from apps.expenses.models import AttachmentKind, Expense, ExpenseStatus
from apps.expenses.services.amortization import regenerate_amortization


class TransitionError(ValueError):
    pass


def validate_feeds_efe_transition(expense: Expense) -> list[str]:
    errors: list[str] = []
    if not expense.efe_account_id:
        errors.append("Se requiere cuenta EFE atribuida.")
    elif expense.efe_account and not expense.efe_account.is_leaf:
        errors.append("La cuenta EFE debe ser una hoja imputable.")
    if expense.amount is None:
        errors.append("Se requiere monto.")
    if not expense.expense_date:
        errors.append("Se requiere fecha del gasto.")
    if not expense.bank_account_id:
        errors.append("Se requiere cuenta bancaria.")
    has_proof = expense.attachments.filter(kind=AttachmentKind.PAYMENT_PROOF).exists()
    if not has_proof:
        # Spec: warning by default; we soft-warn via warnings list, not hard block
        pass
    return errors


def transition_expense(
    expense: Expense,
    *,
    status: ExpenseStatus,
    actor=None,
    allow_closed: bool = False,
) -> tuple[Expense, list[str]]:
    warnings: list[str] = []
    if not status.active:
        raise TransitionError("El estado destino no está activo.")

    if status.feeds_efe:
        errors = validate_feeds_efe_transition(expense)
        if errors:
            raise TransitionError(" ".join(errors))
        has_proof = expense.attachments.filter(kind=AttachmentKind.PAYMENT_PROOF).exists()
        if not has_proof:
            warnings.append("Sin comprobante de pago adjunto.")
        has_invoice = expense.attachments.filter(
            kind=AttachmentKind.PROVIDER_INVOICE
        ).exists()
        if not has_invoice and status.key != "FACTURA_SIN_SOPORTE":
            warnings.append(
                "Sin factura del proveedor; considera FACTURA_SIN_SOPORTE si aplica."
            )

    expense.status = status
    if actor and status.feeds_efe:
        expense.approved_by = actor
    expense.save(update_fields=["status", "approved_by", "updated_at"])

    if status.feeds_efe:
        regenerate_amortization(expense, allow_closed=allow_closed)
    else:
        # Leaving feeds_efe clears future EFE imputations
        regenerate_amortization(expense, allow_closed=True)

    return expense, warnings
