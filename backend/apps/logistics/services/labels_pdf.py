from __future__ import annotations

import io
import logging
from typing import Iterable

import httpx
from pypdf import PdfReader, PdfWriter

from apps.logistics.models import Shipment

logger = logging.getLogger(__name__)


def merge_shipment_label_pdfs(shipment_ids: Iterable) -> bytes:
    """
    Download each shipment label_url and merge into a single PDF.
    Skips shipments without label_url; raises if none can be merged.
    """
    shipments = list(
        Shipment.objects.filter(id__in=list(shipment_ids))
        .exclude(label_url="")
        .order_by("tracking_number", "created_at")
    )
    if not shipments:
        raise ValueError("Ninguna guía seleccionada tiene PDF (label_url).")

    writer = PdfWriter()
    merged = 0
    errors: list[str] = []

    with httpx.Client(timeout=45.0, follow_redirects=True) as client:
        for shipment in shipments:
            url = (shipment.label_url or "").strip()
            if not url:
                continue
            try:
                res = client.get(url)
                res.raise_for_status()
                reader = PdfReader(io.BytesIO(res.content))
                for page in reader.pages:
                    writer.add_page(page)
                merged += 1
            except Exception as exc:
                logger.warning(
                    "No se pudo unir PDF de shipment %s: %s", shipment.id, exc
                )
                errors.append(
                    f"{shipment.tracking_number or shipment.sale_id}: {exc}"
                )

    if merged == 0:
        detail = "; ".join(errors[:3]) if errors else "sin detalle"
        raise ValueError(f"No se pudo descargar ningún PDF de guía ({detail}).")

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
