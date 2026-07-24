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


def _parse_date(raw: str) -> date:
    s = (raw or "").strip().strip('"').strip("'").strip()
    if not s:
        raise ValueError("fecha vacía")
    # solo dígitos: DDMMYYYY o YYYYMMDD
    if len(s) >= 8 and s[:8].isdigit():
        eight = s[:8]
        for fmt in ("%d%m%Y", "%Y%m%d"):
            try:
                return datetime.strptime(eight, fmt).date()
            except ValueError:
                continue
    # quitar hora si viene pegada
    head = s.replace("T", " ").split(" ")[0]
    for fmt in (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(head[:10], fmt).date()
        except ValueError:
            continue
    raise ValueError(f"fecha no reconocida: {raw[:40]!r}")


def _split_csv_line(line: str) -> list[str]:
    # Delimitador dominante; respeta comillas simples de CSV
    if line.count(";") >= line.count(",") and line.count(";") >= 2:
        delim = ";"
    elif line.count("\t") >= 2:
        delim = "\t"
    else:
        delim = ","
    parts: list[str] = []
    cur = []
    in_q = False
    for ch in line:
        if ch == '"':
            in_q = not in_q
            continue
        if ch == delim and not in_q:
            parts.append("".join(cur).strip())
            cur = []
            continue
        cur.append(ch)
    parts.append("".join(cur).strip())
    return parts


def _looks_like_header(parts: list[str]) -> bool:
    blob = " ".join(parts).upper()
    return any(
        k in blob
        for k in ("FECHA", "DATE", "DESCRIP", "CONCEPTO", "VALOR", "MONTO", "REFEREN")
    )


def parse_bancolombia(text: str) -> list[ParsedRow]:
    """
    Soporta:
    1) Plano sin encabezado (legado): col1 cuenta, col4 fecha DDMMYYYY,
       col6 valor, col7 código, col8 concepto
    2) CSV con encabezado (extracto web reciente): Fecha / Valor / Descripción…
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []

    first_parts = _split_csv_line(lines[0])
    if _looks_like_header(first_parts):
        return _parse_headered(
            text,
            date_keys=(
                "FECHA CONTABLE",
                "FECHA TRANSACCION",
                "FECHA TRANSACCIÓN",
                "FECHA",
                "DATE",
            ),
            value_keys=("VALOR", "MONTO", "AMOUNT", "VALOR COP"),
            concept_keys=("DESCRIPCION", "DESCRIPCIÓN", "CONCEPTO", "DETALLE", "DESCRIPTION"),
            ref_keys=("REFERENCIA", "DOCUMENTO", "SUCURSAL", "OFICINA", "REFERENCE"),
        )

    rows: list[ParsedRow] = []
    for i, line in enumerate(lines, start=1):
        parts = _split_csv_line(line)
        if len(parts) < 6:
            rows.append(
                ParsedRow(
                    date=date.today(),
                    value=Decimal("0"),
                    concept="",
                    error=f"L{i}: columnas insuficientes ({len(parts)}) · {line[:80]!r}",
                )
            )
            continue
        try:
            account = parts[0]
            # Prefer col4 (índice 3); si no parsea, prueba col1/col5 (formatos raros)
            fecha_raw = parts[3]
            try:
                d = _parse_date(fecha_raw)
            except ValueError:
                d = None
                for idx in (0, 1, 2, 4):
                    if idx < len(parts):
                        try:
                            d = _parse_date(parts[idx])
                            fecha_raw = parts[idx]
                            break
                        except ValueError:
                            continue
                if d is None:
                    raise ValueError(f"fecha no reconocida: {parts[3]!r}")
            valor = _dec(parts[5])
            # a veces valor está en otra columna si el layout cambió
            if valor == 0 and len(parts) > 6:
                for idx in (4, 6, 5):
                    if idx < len(parts):
                        try:
                            cand = _dec(parts[idx])
                            if cand != 0:
                                valor = cand
                                break
                        except Exception:
                            continue
            tx = parts[6] if len(parts) > 6 else ""
            concept = parts[7] if len(parts) > 7 else (parts[6] if len(parts) > 6 else "")
            rows.append(
                ParsedRow(
                    date=d,
                    value=valor,
                    concept=concept,
                    tx_code=tx,
                    account_no=account,
                    raw={"line": i, "fecha_raw": fecha_raw, "parts": parts[:9]},
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
    header_parts = _split_csv_line(lines[0])
    header = [h.strip().strip('"').upper() for h in header_parts]
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
        parts = _split_csv_line(line)
        try:
            if di is None or vi is None:
                raise ValueError(
                    f"faltan columnas fecha/valor · headers={header[:8]}"
                )
            if di >= len(parts) or vi >= len(parts):
                raise ValueError("fila más corta que el encabezado")
            d = _parse_date(parts[di])
            valor = _dec(parts[vi])
            concept = parts[ci] if ci is not None and ci < len(parts) else ""
            ref = parts[ri] if ri is not None and ri < len(parts) else ""
            rows.append(
                ParsedRow(
                    date=d,
                    value=valor,
                    concept=concept,
                    reference=ref,
                    raw={"line": n},
                )
            )
        except Exception as exc:
            rows.append(
                ParsedRow(
                    date=date.today(),
                    value=Decimal("0"),
                    concept="",
                    error=f"L{n}: {exc}",
                )
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
