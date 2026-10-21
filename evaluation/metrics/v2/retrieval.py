"""Scheme-id based retrieval evaluation (benchmark v2)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from evaluation.metrics.compute import precision_at_k, recall_at_k
from evaluation.metrics.v2.normalize import (
    canonicalize_scheme_id,
    canonicalize_source_identity,
    extract_scheme_id_from_document_id,
    extract_scheme_id_from_seed_path,
)


def relevant_scheme_ids(case: Dict[str, Any]) -> Set[str]:
    """Canonical scheme identities expected for retrieval on this case."""
    ids: Set[str] = set()
    scheme = case.get("scheme")
    if scheme and str(scheme).lower() not in ("unspecified", "none", ""):
        found = canonicalize_scheme_id(scheme)
        if found:
            ids.add(found)

    for item in case.get("evidence") or []:
        if not isinstance(item, dict):
            continue
        for field in ("document_id", "document_path", "source_url"):
            value = item.get(field)
            if not value:
                continue
            found = (
                extract_scheme_id_from_document_id(str(value))
                or extract_scheme_id_from_seed_path(str(value))
                or canonicalize_scheme_id(str(value))
            )
            if found:
                ids.add(found)
    return ids


def retrieved_scheme_ids(payload: Dict[str, Any]) -> List[str]:
    """Ordered canonical scheme_ids from API sources (deduped, order preserved)."""
    ordered: List[str] = []
    seen: Set[str] = set()
    for key in ("sources", "official_sources"):
        for item in payload.get(key) or []:
            sid = canonicalize_source_identity(item)
            if sid and sid not in seen:
                seen.add(sid)
                ordered.append(sid)
    return ordered


def score_retrieval(case: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate retrieval using canonical scheme_id identity."""
    relevant = relevant_scheme_ids(case)
    retrieved = retrieved_scheme_ids(payload)
    has_sources = bool((payload.get("sources") or payload.get("official_sources")))

    if not relevant:
        return {
            "status": "unevaluated",
            "reason": "no_relevant_scheme_id",
            "relevant_scheme_ids": [],
            "retrieved_scheme_ids": retrieved,
            "has_sources": has_sources,
            "precision_at_1": None,
            "precision_at_3": None,
            "precision_at_5": None,
            "recall_at_5": None,
            "hit_at_1": None,
            "method": "scheme_id_v2",
        }

    if not has_sources:
        return {
            "status": "no_source",
            "reason": "api_returned_no_sources",
            "relevant_scheme_ids": sorted(relevant),
            "retrieved_scheme_ids": [],
            "has_sources": False,
            "precision_at_1": None,
            "precision_at_3": None,
            "precision_at_5": None,
            "recall_at_5": None,
            "hit_at_1": None,
            "method": "scheme_id_v2",
        }

    rel_list = sorted(relevant)
    hit_at_1 = bool(retrieved[:1] and retrieved[0] in relevant)
    return {
        "status": "evaluated",
        "reason": None,
        "relevant_scheme_ids": rel_list,
        "retrieved_scheme_ids": retrieved,
        "has_sources": True,
        "precision_at_1": precision_at_k(rel_list, retrieved, 1),
        "precision_at_3": precision_at_k(rel_list, retrieved, 3),
        "precision_at_5": precision_at_k(rel_list, retrieved, 5),
        "recall_at_5": recall_at_k(rel_list, retrieved, 5),
        "hit_at_1": hit_at_1,
        "method": "scheme_id_v2",
    }
