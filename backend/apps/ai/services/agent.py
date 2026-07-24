from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, Sum
from django.utils import timezone

from apps.ai.services.embeddings import similarity_search
from apps.audit.services import log_audit_event
from apps.config import settings_service as cfg
from apps.integrations.models import IntegrationLog, IntegrationSource
from apps.sales.models import ConsolidatedSale, SaleState


TOOLS = [
    {
        "name": "sales_summary",
        "description": "Resumen de ventas consolidadas por rango de días (estado ACTIVE).",
        "parameters": {"days": "int, default 7"},
    },
    {
        "name": "sales_by_seller",
        "description": "Totales de venta por vendedor en los últimos N días.",
        "parameters": {"days": "int, default 7"},
    },
    {
        "name": "knowledge_search",
        "description": "Búsqueda semántica en documentos (políticas, productos, casos).",
        "parameters": {"query": "string"},
    },
]


def tool_sales_summary(*, days: int = 7) -> dict[str, Any]:
    since = timezone.now() - timedelta(days=max(1, min(days, 90)))
    qs = ConsolidatedSale.objects.filter(
        state=SaleState.ACTIVE,
        closed_at__gte=since,
    )
    agg = qs.aggregate(total=Sum("total_value"), iva=Sum("iva_generated"))
    return {
        "days": days,
        "orders": qs.count(),
        "total": str(agg["total"] or Decimal("0")),
        "iva": str(agg["iva"] or Decimal("0")),
        "units": qs.count(),
    }


def tool_sales_by_seller(*, days: int = 7) -> dict[str, Any]:
    since = timezone.now() - timedelta(days=max(1, min(days, 90)))
    rows = (
        ConsolidatedSale.objects.filter(state=SaleState.ACTIVE, closed_at__gte=since)
        .values("seller__name")
        .annotate(total=Sum("total_value"), orders=Count("id"))
        .order_by("-total")[:20]
    )
    return {
        "days": days,
        "sellers": [
            {
                "seller": r["seller__name"] or "Sin asignar",
                "total": str(r["total"] or 0),
                "units": int(r["orders"] or 0),
            }
            for r in rows
        ],
    }


def run_tool(name: str, params: dict | None = None) -> dict[str, Any]:
    params = params or {}
    if name == "sales_summary":
        return tool_sales_summary(days=int(params.get("days") or 7))
    if name == "sales_by_seller":
        return tool_sales_by_seller(days=int(params.get("days") or 7))
    if name == "knowledge_search":
        return {"hits": similarity_search(str(params.get("query") or ""), limit=5)}
    raise ValueError(f"Herramienta desconocida: {name}")


def _pick_tool(question: str) -> tuple[str, dict]:
    q = (question or "").lower()
    if any(w in q for w in ("política", "politica", "síntoma", "sintoma", "producto", "caso")):
        return "knowledge_search", {"query": question}
    if any(w in q for w in ("vendedor", "comercial", "vendedora")):
        days = 7
        if "mes" in q:
            days = 30
        return "sales_by_seller", {"days": days}
    days = 7
    if "mes" in q:
        days = 30
    if "hoy" in q or "día" in q or "dia" in q:
        days = 1
    return "sales_summary", {"days": days}


def _format_answer(tool: str, data: dict, question: str) -> str:
    if tool == "sales_summary":
        return (
            f"En los últimos {data['days']} días hay {data['orders']} pedidos activos "
            f"por ${data['total']} COP (IVA ${data['iva']}, {data['units']} unidades)."
        )
    if tool == "sales_by_seller":
        lines = [f"Ventas por vendedor (últimos {data['days']} días):"]
        for row in data.get("sellers") or []:
            lines.append(f"· {row['seller']}: ${row['total']} ({row['units']} u)")
        if len(lines) == 1:
            lines.append("· Sin datos en el período.")
        return "\n".join(lines)
    hits = data.get("hits") or []
    if not hits:
        return "No encontré documentos relevantes en la base de conocimiento."
    parts = ["Encontré esto en el conocimiento interno:"]
    for h in hits[:3]:
        parts.append(f"· [{h['kind']}] {h.get('title') or 'sin título'} (score {h['score']}): {h['chunk'][:180]}")
    return "\n".join(parts)


def ask_agent(question: str, *, actor=None) -> dict[str, Any]:
    """
    Secure text-to-query agent: picks a validated tool, never runs arbitrary SQL.
    Without AI API key, uses rule-based routing + mock retrieval.
    """
    enabled = cfg.get("ai.enabled", True)
    if enabled is False or str(enabled).lower() in {"false", "0", "no"}:
        return {
            "answer": "La capa de IA está desactivada en configuración.",
            "tool": None,
            "sources": [],
            "mode": "disabled",
        }

    tool, params = _pick_tool(question)
    data = run_tool(tool, params)
    answer = _format_answer(tool, data, question)
    sources = []
    if tool == "knowledge_search":
        sources = data.get("hits") or []

    IntegrationLog.objects.create(
        provider=IntegrationSource.AI,
        method="AGENT",
        url="internal://ai/agent",
        request_headers={},
        request_body={"question": question[:500], "tool": tool, "params": params},
        response_status=200,
        response_body={"answer": answer[:1000]},
        latency_ms=0,
        success=True,
        error="",
        ref_type="User",
        ref_id=str(getattr(actor, "id", "") or ""),
    )
    log_audit_event(
        actor=actor,
        action="AI_AGENT_QUERY",
        entity="Agent",
        entity_id="",
        metadata={"tool": tool, "question": question[:200]},
    )
    return {
        "answer": answer,
        "tool": tool,
        "params": params,
        "data": data,
        "sources": sources,
        "mode": "tools+rag-mock",
        "tools_available": [t["name"] for t in TOOLS],
    }
