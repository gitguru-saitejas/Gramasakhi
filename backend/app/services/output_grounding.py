"""Post-generation deterministic grounding guard (Phase 2).

Runs after LLM generation; fails closed when unsupported claims leak through.
No additional LLM calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from app.services.claim_alignment import ClaimAnalysis, analyze_claim, check_answer_grounding
from app.services.evidence_validator import safe_fallback_answer


@dataclass
class GroundingGuardResult:
    ok: bool
    answer: str
    reason: str = "grounded"
    validated: bool = True
    signals: Dict[str, Any] = field(default_factory=dict)
    preserve_sources: bool = True


def apply_output_grounding_guard(
    query: str,
    answer: str,
    evidence: Sequence[Dict[str, Any]],
    *,
    response_language: Optional[str] = None,
    claim: Optional[ClaimAnalysis] = None,
) -> GroundingGuardResult:
    """Return grounded answer or safe refusal with validated=false."""
    text = (answer or "").strip()
    if not text:
        return GroundingGuardResult(ok=True, answer=text, validated=True)

    analysis = claim or analyze_claim(query)
    check = check_answer_grounding(query, text, evidence, claim=analysis)
    if check.ok:
        return GroundingGuardResult(
            ok=True,
            answer=text,
            validated=True,
            reason=check.reason,
            signals=check.signals,
        )

    fallback = safe_fallback_answer(response_language)
    signals = dict(check.signals)
    signals["grounding_failure"] = {
        "reason": check.reason,
        "detail": check.detail,
    }
    return GroundingGuardResult(
        ok=False,
        answer=fallback,
        validated=False,
        reason=check.reason,
        signals=signals,
        preserve_sources=True,
    )
