from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import unquote, urlparse

_POSITIVE = (
    ("guideline", 40),
    ("guidelines", 40),
    ("scheme", 25),
    ("eligibility", 22),
    ("application", 18),
    ("beneficiary", 16),
    ("brochure", 14),
    ("notification", 14),
    ("official", 10),
)
_NEGATIVE = (
    ("logo", -100),
    ("banner", -80),
    ("icon", -80),
    ("receipt", -60),
    ("certificate", -40),
    ("image", -50),
    ("report", -5),
)


def score_pdf_candidate(candidate: Dict[str, Any]) -> int:
    """Deterministic ranking — higher is better canonical PDF."""
    url = (candidate.get("url") or "").lower()
    title = (candidate.get("title") or "").lower()
    blob = f"{url} {title} {unquote(url)}"
    score = 0
    if url.endswith(".pdf") or ".pdf?" in url:
        score += 30
    for term, pts in _POSITIVE:
        if term in blob:
            score += pts
    for term, pts in _NEGATIVE:
        if term in blob:
            score += pts
    # Prefer myScheme / state department hosts over deep academic reports
    host = (urlparse(url).hostname or "").lower()
    if host.endswith(".gov.in"):
        score += 12
    if "myscheme" in host:
        score += 8
    origin = candidate.get("origin") or ""
    if origin == "myscheme_api_reference":
        score += 15
    if "guideline" in title:
        score += 20
    return score


def select_canonical_pdf(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None
    ranked = sorted(
        candidates,
        key=lambda c: (-score_pdf_candidate(c), c.get("url") or ""),
    )
    best = ranked[0]
    if score_pdf_candidate(best) < -50:
        return None
    return best
