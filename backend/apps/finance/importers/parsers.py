from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass
class ParsedRow:
    date: date
    value: Decimal
    concept: str
    reference: str = ""
    comment: str = ""
    tx_code: str = ""
    account_no: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    @property
    def item(self) -> str:
        return "EGRESO" if self.value < 0 else "INGRESO"

    def dedupe_base(self) -> str:
        return "|".join(
            [
                self.date.isoformat(),
                f"{self.value:.2f}",
                (self.concept or "").strip().upper(),
                (self.reference or "").strip().upper(),
                (self.tx_code or "").strip(),
            ]
        )


def _dec(raw: str) -> Decimal:
    s = (raw or "").strip().replace("$", "").replace(" ", "")
    if "," in s and "." in s:
        # 1.234,56 vs 1,234.56
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(".", "").replace(",", ".")
    return Decimal(s)


def parse_bancolombia(text: str) -> list[ParsedRow]:
    """
    CSV sin encabezado (formato plano Bancolombia):
      col1 cuenta, col4 fecha DDMMYYYY, col6 valor con signo, col7 código, col8 concepto
    """
    rows: list[ParsedRow] = []
    for i, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        # try semicolon, then comma, then tab
        parts = line.split(";")
        if len(parts) < 6:
            parts = line.split(",")
        if len(parts) < 6:
            parts = line.split("\t")
        if len(parts) < 6:
            rows.append(ParsedRow(date=date.today(), value=Decimal("0"), concept="", error=f"L{i}: columnas insuficientes"))
            continue
        try:
            account = (parts[0] or "").strip()
            fecha_raw = (parts[3] or "").strip()
            if len(fecha_raw) == 8 and fecha_raw.isdigit():
                d = datetime.strptime(fecha_raw, "%d%m%Y").date()
            else:
                d = datetime.strptime(fecha_raw[:10], "%Y-%m-%d").date()
            valor = _dec(parts[5])
            tx = (parts[6] if len(parts) > 6 else "").strip()
            concept = (parts[7] if len(parts) > 7 else "").strip()
            rows.append(
                ParsedRow(
                    date=d,
                    value=valor,
                    concept=concept,
                    tx_code=tx,
                    account_no=account,
                    raw={"line": i, "parts": parts[:9]},
                )
            )
        except (ValueError, InvalidOperation, IndexError) as exc:
            rows.append(
                ParsedRow(
                    date=date.today(),
                    value=Decimal("0"),
                    concept="",
                    error=f"L{i}: {exc}",
                )
            )
    return rows


def parse_mercadopago(text: str) -> list[ParsedRow]:
    """CSV genérico con encabezado; busca columnas fecha/valor/concepto."""
    return _parse_headered(
        text,
        date_keys=("DATE", "FECHA", "RELEASE_DATE", "TRANSACTION_DATE"),
        value_keys=("TRANSACTION_AMOUNT", "NET_CREDIT_AMOUNT", "NET_DEBIT_AMOUNT", "AMOUNT", "VALOR", "NET_RECEIVED_AMOUNT"),
        concept_keys=("DESCRIPTION", "CONCEPTO", "EXTERNAL_REFERENCE", "REASON"),
        ref_keys=("EXTERNAL_REFERENCE", "SOURCE_ID", "ID", "REFERENCE"),
    )


def parse_bold(text: str) -> list[ParsedRow]:
    return _parse_headered(
        text,
        date_keys=("FECHA", "DATE", "CREATED_AT"),
        value_keys=("VALOR", "AMOUNT", "MONTO", "TOTAL"),
        concept_keys=("DESCRIPCION", "DESCRIPTION", "CONCEPTO", "TIPO"),
        ref_keys=("REFERENCIA", "REFERENCE", "ID"),
    )


def parse_nequi(text: str) -> list[ParsedRow]:
    return _parse_headered(
        text,
        date_keys=("FECHA", "DATE"),
        value_keys=("VALOR", "AMOUNT", "MONTO"),
        concept_keys=("DESCRIPCION", "DESCRIPTION", "CONCEPTO", "DETALLE"),
        ref_keys=("REFERENCIA", "REFERENCE", "ID"),
    )


def _parse_headered(
    text: str,
    *,
    date_keys: tuple[str, ...],
    value_keys: tuple[str, ...],
    concept_keys: tuple[str, ...],
    ref_keys: tuple[str, ...],
) -> list[ParsedRow]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    delim = ";" if lines[0].count(";") >= lines[0].count(",") else ","
    header = [h.strip().strip('"').upper() for h in lines[0].split(delim)]
    idx = {h: i for i, h in enumerate(header)}

    def find(keys: tuple[str, ...]) -> int | None:
        for k in keys:
            if k in idx:
                return idx[k]
        for h, i in idx.items():
            for k in keys:
                if k in h:
                    return i
        return None

    di, vi, ci, ri = find(date_keys), find(value_keys), find(concept_keys), find(ref_keys)
    rows: list[ParsedRow] = []
    for n, line in enumerate(lines[1:], start=2):
        parts = [p.strip().strip('"') for p in line.split(delim)]
        try:
            if di is None or vi is None:
                raise ValueError("faltan columnas fecha/valor")
            raw_d = parts[di]
            if len(raw_d) == 8 and raw_d.isdigit():
                d = datetime.strptime(raw_d, "%d%m%Y").date()
            elif "/" in raw_d:
                for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
                    try:
                        d = datetime.strptime(raw_d[:10], fmt).date()
                        break
                    except ValueError:
                        continue
                else:
                    raise ValueError(f"fecha {raw_d}")
            else:
                d = datetime.strptime(raw_d[:10], "%Y-%m-%d").date()
            valor = _dec(parts[vi])
            concept = parts[ci] if ci is not None and ci < len(parts) else ""
            ref = parts[ri] if ri is not None and ri < len(parts) else ""
            rows.append(ParsedRow(date=d, value=valor, concept=concept, reference=ref, raw={"line": n}))
        except Exception as exc:
            rows.append(
                ParsedRow(date=date.today(), value=Decimal("0"), concept="", error=f"L{n}: {exc}")
            )
    return rows


PARSERS = {
    "bancolombia": parse_bancolombia,
    "mercadopago": parse_mercadopago,
    "bold": parse_bold,
    "nequi": parse_nequi,
}


def assign_dedupe_hashes(rows: list[ParsedRow]) -> list[tuple[ParsedRow, str]]:
    """Reproduce COUNTIFS: misma firma + ocurrencia N."""
    counts: dict[str, int] = {}
    out: list[tuple[ParsedRow, str]] = []
    for row in rows:
        if row.error:
            out.append((row, ""))
            continue
        base = row.dedupe_base()
        counts[base] = counts.get(base, 0) + 1
        occ = counts[base]
        raw = f"{base}|#{occ}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]
        out.append((row, digest))
    return out
