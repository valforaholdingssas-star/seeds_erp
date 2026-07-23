from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from apps.ai.models import Document, Embedding
from apps.audit.services import log_audit_event


def _embed_text(text: str, *, dims: int = 64) -> list[float]:
    """Deterministic mock embedding from token hashes (no API key required)."""
    tokens = re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ0-9]+", (text or "").lower())
    vec = [0.0] * dims
    if not tokens:
        return vec
    for tok in tokens:
        digest = hashlib.sha256(tok.encode("utf-8")).digest()
        for i in range(dims):
            vec[i] += ((digest[i % len(digest)] / 255.0) * 2) - 1
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def chunk_text(text: str, *, size: int = 500) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    return [text[i : i + size] for i in range(0, len(text), size)]


def ingest_document(
    *,
    kind: str,
    content: str,
    title: str = "",
    ref_type: str = "",
    ref_id: str = "",
    metadata: dict | None = None,
    actor=None,
) -> Document:
    doc = Document.objects.create(
        kind=kind,
        title=title,
        content=content,
        ref_type=ref_type,
        ref_id=ref_id,
        metadata=metadata or {},
    )
    Embedding.objects.filter(document=doc).delete()
    text = f"{title}\n{content}".strip()
    for chunk in chunk_text(text):
        vec = _embed_text(chunk)
        Embedding.objects.create(document=doc, chunk=chunk, vector=vec, dimensions=len(vec))
    log_audit_event(
        actor=actor,
        action="AI_DOCUMENT_INGESTED",
        entity="Document",
        entity_id=str(doc.id),
        metadata={"kind": kind, "chunks": doc.embeddings.count()},
    )
    return doc


def similarity_search(query: str, *, limit: int = 5, kind: str | None = None) -> list[dict[str, Any]]:
    qvec = _embed_text(query)
    qs = Embedding.objects.select_related("document").all()
    if kind:
        qs = qs.filter(document__kind=kind)
    scored: list[tuple[float, Embedding]] = []
    for emb in qs[:2000]:
        score = cosine(qvec, emb.vector or [])
        if score > 0.01:
            scored.append((score, emb))
    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        # fallback lexical
        from django.db.models import Q

        q = (query or "").strip()
        docs = Document.objects.filter(
            Q(title__icontains=q[:40]) | Q(content__icontains=q.split()[0] if q else "")
        )[:limit]
        return [
            {
                "score": 0.2,
                "chunk": d.content[:300],
                "document_id": str(d.id),
                "kind": d.kind,
                "title": d.title,
                "ref_type": d.ref_type,
                "ref_id": d.ref_id,
            }
            for d in docs
        ]
    results = []
    for score, emb in scored[:limit]:
        results.append(
            {
                "score": round(score, 4),
                "chunk": emb.chunk,
                "document_id": str(emb.document_id),
                "kind": emb.document.kind,
                "title": emb.document.title,
                "ref_type": emb.document.ref_type,
                "ref_id": emb.document.ref_id,
            }
        )
    return results
