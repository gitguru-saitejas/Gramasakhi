"""Contextual evidence expansion for eligibility-rich retrieval (Phase 3B).

Small, bounded helpers — no architectural redesign.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Set

logger = logging.getLogger("gramsakhi.evidence_expansion")

_ELIGIBILITY_QUERY = re.compile(
    r"\b("
    r"eligible|eligibility|who can apply|qualify|beneficiary|conditions|"
    r"head of family|head of the family|notified crop|notified area|"
    r"age band|savings account|ration card|resident of"
    r")\b",
    re.I,
)

_ELIGIBILITY_CHUNK_MARKERS: tuple[str, ...] = (
    "eligibility",
    "eligible",
    "who can apply",
    "beneficiary",
    "criteria",
    "conditions",
    "head of family",
    "head of the family",
    "notified crop",
    "notified area",
    "notified crops",
    "age band",
    "savings bank account",
    "savings account",
    "resident of",
    "section:\neligibility",
)

_SECTION_TAG_PATTERNS: tuple[tuple[str, str], ...] = (
    ("eligibility", r"\beligib|\bwho can apply|\bbeneficiary\b|\bcriteria\b"),
    ("benefits", r"\bbenefit|\bsubsidy|\bassistance\b"),
    ("application", r"\bapplication process|\bhow to apply\b"),
    ("documents", r"\bdocuments required|\brequired documents\b"),
    ("notified_crop", r"\bnotified crop|\bnotified area|\bgrowing notified\b"),
)


def is_eligibility_focused_query(query: str) -> bool:
    q = (query or "").strip()
    if not q:
        return False
    try:
        from app.services.citizen_assistance import classify_citizen_intent, CitizenIntent

        if classify_citizen_intent(q) in (CitizenIntent.ELIGIBILITY, CitizenIntent.PERSONAL_ELIGIBILITY):
            return True
    except Exception:  # noqa: BLE001
        pass
    if _ELIGIBILITY_QUERY.search(q):
        return True
    try:
        from app.services.myscheme_service import query_citizen_intent

        return query_citizen_intent(q) == "eligibility"
    except Exception:  # noqa: BLE001
        return False


def chunk_section_tags(content: str) -> List[str]:
    low = (content or "").lower()
    tags: List[str] = []
    for tag, pattern in _SECTION_TAG_PATTERNS:
        if re.search(pattern, low):
            tags.append(tag)
    return tags


def chunk_has_eligibility_signal(doc: Dict[str, Any]) -> bool:
    meta = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    tags = meta.get("section_tags") or meta.get("section_category") or []
    if isinstance(tags, str):
        tags = [tags]
    if "eligibility" in tags or "notified_crop" in tags:
        return True
    blob = f"{doc.get('content') or ''} {doc.get('scheme_name') or ''}".lower()
    return any(marker in blob for marker in _ELIGIBILITY_CHUNK_MARKERS)


def boost_eligibility_ranked_docs(
    query: str,
    docs: Sequence[Dict[str, Any]],
    *,
    boost_factor: float = 1.18,
) -> List[Dict[str, Any]]:
    """Re-rank hydrated docs to prefer eligibility-bearing chunks when appropriate."""
    items = [dict(d) for d in (docs or [])]
    if not items or not is_eligibility_focused_query(query):
        return items
    for row in items:
        if chunk_has_eligibility_signal(row):
            base = float(row.get("similarity_score") or row.get("hybrid_score") or row.get("ce_score") or 0.0)
            boosted = base * boost_factor
            row["similarity_score"] = boosted
            row["hybrid_score"] = float(row.get("hybrid_score") or base) * boost_factor
            row["eligibility_boost"] = True
    items.sort(
        key=lambda x: float(x.get("similarity_score") or x.get("hybrid_score") or 0.0),
        reverse=True,
    )
    return items


def _chunk_keys(doc: Dict[str, Any]) -> tuple[Optional[str], Optional[int]]:
    meta = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    doc_id = str(doc.get("document_id") or meta.get("document_id") or "").strip() or None
    idx = doc.get("chunk_index")
    if idx is None:
        idx = meta.get("chunk_index")
    try:
        idx_int = int(idx) if idx is not None else None
    except (TypeError, ValueError):
        idx_int = None
    return doc_id, idx_int


def expand_adjacent_chunks(
    db: Any,
    docs: Sequence[Dict[str, Any]],
    *,
    query: str = "",
    max_additions: int = 2,
) -> List[Dict[str, Any]]:
    """Add immediate neighbor chunks from the same document when eligibility context may be split."""
    items = [dict(d) for d in (docs or [])]
    if not items or max_additions <= 0:
        return items
    if not is_eligibility_focused_query(query) and not any(chunk_has_eligibility_signal(d) for d in items):
        return items

    from app.models.rag import DocumentChunk

    seen: Set[str] = {str(d.get("chunk_id") or "") for d in items if d.get("chunk_id")}
    additions: List[Dict[str, Any]] = []

    for doc in items:
        if len(additions) >= max_additions:
            break
        doc_id, idx = _chunk_keys(doc)
        if not doc_id or idx is None:
            continue
        for neighbor_idx in (idx - 1, idx + 1):
            if len(additions) >= max_additions:
                break
            row = (
                db.query(DocumentChunk)
                .filter(DocumentChunk.document_id == doc_id, DocumentChunk.chunk_index == neighbor_idx)
                .first()
            )
            if not row:
                continue
            cid = str(row.id)
            if cid in seen:
                continue
            meta = dict(row.metadata_dict or {})
            parent = row.document
            neighbor = {
                "chunk_id": cid,
                "content": row.content,
                "document_title": parent.title if parent else None,
                "scheme_name": getattr(parent, "scheme_name", None) if parent else meta.get("scheme_name"),
                "scheme_id": meta.get("scheme_id"),
                "source": getattr(parent, "source", None) if parent else meta.get("source"),
                "metadata": meta,
                "page": meta.get("page"),
                "document_id": doc_id,
                "chunk_index": neighbor_idx,
                "similarity_score": float(doc.get("similarity_score") or 0.0) * 0.92,
                "hybrid_score": float(doc.get("hybrid_score") or 0.0) * 0.92,
                "context_expansion": True,
                "expansion_parent_chunk_id": doc.get("chunk_id"),
            }
            seen.add(cid)
            additions.append(neighbor)

    if not additions:
        return items
    merged = items + additions
    merged.sort(
        key=lambda x: float(x.get("similarity_score") or x.get("hybrid_score") or 0.0),
        reverse=True,
    )
    logger.info("EVIDENCE_CONTEXT_EXPAND added=%s total=%s", len(additions), len(merged))
    return merged
