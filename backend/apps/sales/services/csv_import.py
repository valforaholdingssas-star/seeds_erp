from __future__ import annotations

import csv
import io
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.audit.services import log_audit_event
from apps.sales.models import EcommerceSale, FeriaSale, KommoSale, ManualSale, SaleSource
from apps.sales.services.normalization import promote_to_consolidated
from apps.sales.services.payment_methods import resolve_payment_method
from apps.sales.services.fulfillment import apply_fulfillment, normalize_fulfillment_type
from apps.sales.kit_types import normalize_kit_type

CANONICAL_FIELDS = [
    "external_id",
    "source",
    "customer_name",
    "email",
    "phone",
    "id_number",
    "address_raw",
    "city_raw",
    "state_raw",
    "total_value",
    "amount_shipping",
    "payment_account",
    "commercial_raw",
    "qty_dorados",
    "qty_plateados",
    "tipo_dorados",
    "tipo_plateados",
    "status",
    "closed_at",
    "order_notes",
    "fulfillment_type",
]

HEADER_ALIASES: dict[str, str] = {
    "id": "external_id",
    "external_id": "external_id",
    "order_id": "external_id",
    "lead_id": "external_id",
    "canal": "source",
    "source": "source",
    "income_source": "source",
    "cliente": "customer_name",
    "customer_name": "customer_name",
    "nombre": "customer_name",
    "email": "email",
    "correo": "email",
    "telefono": "phone",
    "phone": "phone",
    "celular": "phone",
    "cedula": "id_number",
    "cc": "id_number",
    "id_number": "id_number",
    "direccion": "address_raw",
    "address": "address_raw",
    "address_raw": "address_raw",
    "ciudad": "city_raw",
    "city": "city_raw",
    "city_raw": "city_raw",
    "departamento": "state_raw",
    "state_raw": "state_raw",
    "valor": "total_value",
    "total": "total_value",
    "total_value": "total_value",
    "transporte": "amount_shipping",
    "shipping": "amount_shipping",
    "amount_shipping": "amount_shipping",
    "cuenta": "payment_account",
    "payment_account": "payment_account",
    "vendedor": "commercial_raw",
    "comercial": "commercial_raw",
    "commercial_raw": "commercial_raw",
    "dorados": "qty_dorados",
    "qty_dorados": "qty_dorados",
    "plateados": "qty_plateados",
    "qty_plateados": "qty_plateados",
    "tipo_dorados": "tipo_dorados",
    "tipo dorados": "tipo_dorados",
    "tipo_plateados": "tipo_plateados",
    "tipo plateados": "tipo_plateados",
    "status": "status",
    "estado": "status",
    "fecha": "closed_at",
    "closed_at": "closed_at",
    "fecha_cierre": "closed_at",
    "notas": "order_notes",
    "order_notes": "order_notes",
    "fulfillment_type": "fulfillment_type",
    "tipo_entrega": "fulfillment_type",
    "entrega": "fulfillment_type",
    "fulfillment": "fulfillment_type",
}

SOURCE_MODELS = {
    SaleSource.ECOMMERCE: EcommerceSale,
    SaleSource.KOMMO: KommoSale,
    SaleSource.FERIAS: FeriaSale,
    SaleSource.MANUAL: ManualSale,
}


def _norm_header(h: str) -> str:
    return (h or "").strip().lower().replace(" ", "_")


def detect_mapping(headers: list[str]) -> dict[str, str | None]:
    """Map canonical field -> CSV header name (or None)."""
    mapping: dict[str, str | None] = {f: None for f in CANONICAL_FIELDS}
    for header in headers:
        key = HEADER_ALIASES.get(_norm_header(header))
        if key and mapping.get(key) is None:
            mapping[key] = header
    return mapping


def _dec(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    raw = str(value).strip().replace("$", "").replace(" ", "")
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        return Decimal(raw)
    except InvalidOperation:
        raise ValueError(f"Monto inválido: {value}")


def _int(value: Any) -> int:
    if value is None or value == "":
        return 0
    return int(float(str(value).strip().replace(",", ".")))


def _parse_closed_at(value: Any):
    if not value:
        return timezone.now()
    text = str(value).strip()
    dt = parse_datetime(text)
    if dt:
        if timezone.is_naive(dt):
            return timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
    try:
        # YYYY-MM-DD
        from datetime import date, datetime, time

        d = date.fromisoformat(text[:10])
        return timezone.make_aware(datetime.combine(d, time(12, 0)), timezone.get_current_timezone())
    except ValueError:
        return timezone.now()


def _normalize_source(raw: str | None) -> str:
    s = (raw or "MANUAL").strip().upper()
    aliases = {
        "E-COMMERCE": SaleSource.ECOMMERCE,
        "ECOMMERCE": SaleSource.ECOMMERCE,
        "WOO": SaleSource.ECOMMERCE,
        "WOOCOMMERCE": SaleSource.ECOMMERCE,
        "KOMMO": SaleSource.KOMMO,
        "FERIA": SaleSource.FERIAS,
        "FERIAS": SaleSource.FERIAS,
        "MANUAL": SaleSource.MANUAL,
        "MANUALES": SaleSource.MANUAL,
    }
    return aliases.get(s, SaleSource.MANUAL)


def parse_csv_text(text: str) -> tuple[list[str], list[dict[str, str]]]:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = reader.fieldnames or []
    rows = [dict(row) for row in reader]
    return headers, rows


def rows_to_csv_text(headers: list[str], rows: list[dict[str, Any]]) -> str:
    """Serialize header+row dicts to CSV text for reuse of dry_run/commit_csv."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({h: "" if row.get(h) is None else str(row.get(h)) for h in headers})
    return buf.getvalue()


def parse_xlsx_bytes(data: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """Read first sheet of an .xlsx workbook into CSV-like headers + row dicts."""
    from openpyxl import load_workbook

    wb = load_workbook(filename=io.BytesIO(data), read_only=True, data_only=True)
    try:
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)
        try:
            header_row = next(rows_iter)
        except StopIteration:
            return [], []
        headers = [str(c).strip() if c is not None else "" for c in header_row]
        # Drop trailing empty header names
        while headers and not headers[-1]:
            headers.pop()
        parsed: list[dict[str, str]] = []
        for values in rows_iter:
            if values is None:
                continue
            row = {}
            empty = True
            for i, header in enumerate(headers):
                if not header:
                    continue
                val = values[i] if i < len(values) else None
                if val is None:
                    row[header] = ""
                else:
                    row[header] = str(val).strip() if not isinstance(val, str) else val.strip()
                    if row[header]:
                        empty = False
            if not empty:
                parsed.append(row)
        return headers, parsed
    finally:
        wb.close()


def xlsx_to_csv_text(data: bytes) -> str:
    headers, rows = parse_xlsx_bytes(data)
    if not headers:
        return ""
    return rows_to_csv_text(headers, rows)


def validate_row(row: dict[str, Any], mapping: dict[str, str | None], row_num: int) -> dict[str, Any]:
    def get(field: str) -> str:
        header = mapping.get(field)
        if not header:
            return ""
        return str(row.get(header) or "").strip()

    errors: list[str] = []
    source = _normalize_source(get("source"))
    external_id = get("external_id") or f"CSV-{uuid.uuid4().hex[:10].upper()}"
    customer_name = get("customer_name")
    if not customer_name:
        errors.append("customer_name obligatorio")
    try:
        total_value = _dec(get("total_value"))
    except ValueError as exc:
        total_value = Decimal("0")
        errors.append(str(exc))
    try:
        amount_shipping = _dec(get("amount_shipping"))
        qty_dorados = _int(get("qty_dorados"))
        qty_plateados = _int(get("qty_plateados"))
    except Exception as exc:
        amount_shipping = Decimal("0")
        qty_dorados = qty_plateados = 0
        errors.append(str(exc))

    if qty_dorados <= 0 and qty_plateados <= 0:
        qty_dorados = 1  # default 1 kit for historical rows without qty

    commercial_raw = get("commercial_raw")
    if source == SaleSource.MANUAL and not commercial_raw:
        commercial_raw = "MANUAL"
    if source == SaleSource.FERIAS and not commercial_raw:
        commercial_raw = "FERIAS"
    if source == SaleSource.ECOMMERCE and not commercial_raw:
        commercial_raw = "ECOMMERCE"

    status = (get("status") or "completed").lower()
    if status not in {"processing", "completed", "cancelled", "failed", "refunded", "pending"}:
        status = "completed"

    fulfillment = normalize_fulfillment_type(
        get("fulfillment_type"),
        requires_shipping=bool(get("address_raw") or get("city_raw")),
    )
    payload = {
        "external_id": external_id,
        "source": source,
        "customer_name": customer_name,
        "email": get("email"),
        "phone": get("phone"),
        "id_number": get("id_number"),
        "address_raw": get("address_raw"),
        "city_raw": get("city_raw"),
        "state_raw": get("state_raw"),
        "total_value": total_value,
        "amount_shipping": amount_shipping,
        "payment_account": get("payment_account"),
        "commercial_raw": commercial_raw,
        "qty_dorados": qty_dorados,
        "qty_plateados": qty_plateados,
        "tipo_dorados": normalize_kit_type(get("tipo_dorados")),
        "tipo_plateados": normalize_kit_type(get("tipo_plateados")),
        "status": status,
        "closed_at": _parse_closed_at(get("closed_at")),
        "order_notes": get("order_notes"),
        "income_source": source,
        "fulfillment_type": fulfillment,
        "requires_shipping": fulfillment == "ENVIA",
    }
    return {"row": row_num, "ok": not errors, "errors": errors, "data": payload}


def dry_run_csv(text: str, mapping: dict[str, str | None] | None = None) -> dict[str, Any]:
    headers, rows = parse_csv_text(text)
    mapping = mapping or detect_mapping(headers)
    results = []
    for i, row in enumerate(rows, start=2):
        results.append(validate_row(row, mapping, i))
    return {
        "headers": headers,
        "mapping": mapping,
        "total": len(results),
        "valid": sum(1 for r in results if r["ok"]),
        "invalid": sum(1 for r in results if not r["ok"]),
        "rows": results,
    }


@transaction.atomic
def commit_csv(
    text: str,
    *,
    mapping: dict[str, str | None] | None = None,
    on_duplicate: str = "skip",
    actor=None,
) -> dict[str, Any]:
    report = dry_run_csv(text, mapping=mapping)
    created = updated = skipped = rejected = 0
    details: list[dict] = []

    for item in report["rows"]:
        if not item["ok"]:
            rejected += 1
            details.append({"row": item["row"], "status": "rejected", "errors": item["errors"]})
            continue
        data = item["data"]
        source = data["source"]
        model = SOURCE_MODELS[source]
        existing = model.objects.filter(external_id=data["external_id"]).first()
        if existing and on_duplicate == "skip":
            skipped += 1
            details.append({"row": item["row"], "status": "skipped", "external_id": data["external_id"]})
            continue

        defaults = {
            "deal_name": data["customer_name"],
            "closed_at": data["closed_at"],
            "total_value": data["total_value"],
            "amount_shipping": data["amount_shipping"],
            "payment_account": data["payment_account"],
            "payment_method": resolve_payment_method(data.get("payment_account") or "", actor=actor),
            "income_source": data["income_source"],
            "status": data["status"],
            "stage": "Import CSV",
            "commercial_raw": data["commercial_raw"],
            "customer_name": data["customer_name"],
            "email": data["email"],
            "phone": data["phone"],
            "id_number": data["id_number"],
            "address_raw": data["address_raw"],
            "city_raw": data["city_raw"],
            "state_raw": data["state_raw"],
            "qty_dorados": data["qty_dorados"],
            "qty_plateados": data["qty_plateados"],
            "tipo_dorados": data.get("tipo_dorados") or "",
            "tipo_plateados": data.get("tipo_plateados") or "",
            "order_notes": data["order_notes"],
            "requires_shipping": data["requires_shipping"],
            "fulfillment_type": data.get("fulfillment_type") or "ENVIA",
            "extra": {"imported": True},
        }
        apply_fulfillment(defaults)
        if defaults["payment_method"]:
            defaults["payment_account"] = defaults["payment_method"].name
        if existing and on_duplicate == "update":
            for k, v in defaults.items():
                setattr(existing, k, v)
            existing.save()
            source_sale = existing
            updated += 1
            status = "updated"
        else:
            source_sale = model.objects.create(external_id=data["external_id"], **defaults)
            created += 1
            status = "created"

        promote_to_consolidated(source_sale, source=source, actor=actor)
        details.append({"row": item["row"], "status": status, "external_id": data["external_id"]})

    log_audit_event(
        actor=actor,
        action="SALES_CSV_IMPORT",
        entity="ImportJob",
        entity_id="",
        metadata={
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "rejected": rejected,
            "on_duplicate": on_duplicate,
        },
    )
    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "rejected": rejected,
        "details": details[:200],
        "mapping": report["mapping"],
    }
