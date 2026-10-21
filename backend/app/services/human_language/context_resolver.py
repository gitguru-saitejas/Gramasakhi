"""Scheme reference resolution for NLU (explicit query → conversation context)."""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from app.services.citizen_assistance import resolve_detected_scheme


def resolve_scheme_context(
    query: str,
    *,
    conversation_history: Optional[Sequence[Dict[str, Any]]] = None,
    rewrite_active_scheme: Optional[str] = None,
    conversation_active_scheme: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """Return scheme_name (display/canonical) and scheme_id (slug when known)."""
    scheme_name = resolve_detected_scheme(
        query,
        rewrite_active_scheme=rewrite_active_scheme,
        conversation_active_scheme=conversation_active_scheme,
        conversation_history=conversation_history,
    )
    scheme_id: Optional[str] = None
    try:
        from app.services.myscheme_service import requested_scheme_identity

        ident = requested_scheme_identity(query)
        if ident and ident.get("scheme_id"):
            scheme_id = (ident.get("scheme_id") or "").strip() or None
        if not scheme_id and scheme_name:
            ident2 = requested_scheme_identity(scheme_name)
            if ident2 and ident2.get("scheme_id"):
                scheme_id = (ident2.get("scheme_id") or "").strip() or None
    except Exception:
        pass
    return {"scheme_name": scheme_name, "scheme_id": scheme_id}
