"""Scenario-oriented one-shot eligibility evaluation (Phase 2 + 3A)."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from app.services.eligibility_criteria import EligibilityCriteriaResult
from app.services.eligibility_evaluation import (
    DecisionReasonCode,
    EligibilityEvaluationResult,
    EvaluationStatus,
    evaluate_eligibility,
)
from app.services.eligibility_questioning import extract_scenario_facts_from_text

_SCENARIO_PATTERNS = (
    re.compile(r"\ba\s+(?:man|woman|male|female|citizen|person|household|farmer)\b", re.I),
    re.compile(r"\bis\s+(?:he|she|they)\s+eligible\b", re.I),
    re.compile(r"\basks?\s+for\b", re.I),
    re.compile(r"\bunder\s+the\s+listed\s+rules\b", re.I),
    re.compile(r"\bdoes\s+the\s+note\b", re.I),
    re.compile(r"\bis\s+this\s+age\b", re.I),
    re.compile(r"\bis\s+age\s+\d+\b", re.I),
    re.compile(r"\b(?:can|may)\s+(?:a|someone|loanee|non-loanee)\b", re.I),
    re.compile(r"\bintended\s+beneficiary\b", re.I),
    re.compile(r"\btreat(?:s|ed)?\s+(?:her|him|them)\s+as\b", re.I),
    re.compile(r"\b(?:eligible|ineligible)\s+under\b", re.I),
    re.compile(r"\bmy\s+(?:wife|husband)\b", re.I),
    re.compile(r"\bsecond\s+woman\b", re.I),
    re.compile(r"\bno\s+ration\s+card\b", re.I),
    re.compile(r"\bholds?\s+a\s+valid\b.*\bration\s+card\b", re.I),
)

_ELIGIBILITY_QUESTION = re.compile(
    r"\b("
    r"eligible|eligibility|beneficiary|qualify|enroll|apply|"
    r"inside\s+the\s+(?:commonly\s+published\s+)?age\s+band|"
    r"within\s+the\s+(?:commonly\s+published\s+)?age\s+band|"
    r"does\s+the\s+note|is\s+this\s+person|coverage\s+apply|"
    r"asks?\s+about|match(?:es)?\s+the\s+listed|does\s+this\s+match|"
    r"intended\s+beneficiary|described\s+in\s+the\s+note|listed\s+conditions"
    r")\b",
    re.I,
)


def is_scenario_eligibility_query(query: str) -> bool:
    q = (query or "").strip()
    if not q:
        return False
    if not _ELIGIBILITY_QUESTION.search(q):
        return False
    return any(p.search(q) for p in _SCENARIO_PATTERNS)


def should_attempt_scenario_evaluation(query: str) -> bool:
    """True for third-person / hypothetical eligibility questions (not personal 'am I')."""
    q = (query or "").strip()
    if not q:
        return False
    if re.search(r"\b(?:am\s+i|are\s+you)\s+eligible\b", q, re.I):
        return False
    if is_scenario_eligibility_query(q):
        return True
    if _ELIGIBILITY_QUESTION.search(q) and re.search(
        r"\b(?:a|an|the)\s+(?:\d{1,3}[- ]year|man|woman|citizen|person|household|farmer)\b",
        q,
        re.I,
    ):
        return True
    return False


def try_evaluate_scenario_eligibility(
    *,
    query: str,
    criteria: EligibilityCriteriaResult,
    scheme_name: Optional[str] = None,
    scheme_id: Optional[str] = None,
    evidence_validated: bool = True,
) -> Optional[EligibilityEvaluationResult]:
    """Deterministic one-shot eval for explicit scenario facts in the query."""
    if not should_attempt_scenario_evaluation(query):
        return None

    facts = extract_scenario_facts_from_text(query)
    if not facts:
        return None

    resolved_sid = (scheme_id or criteria.scheme_id or "").strip().lower()
    if not resolved_sid and scheme_name:
        from app.services.myscheme_service import slug_hint_from_query

        resolved_sid = (slug_hint_from_query(scheme_name) or "").strip().lower()
    if resolved_sid == "pmfby" and facts.get("crop_notified") is False:
        return EligibilityEvaluationResult(
            scheme_name=criteria.scheme_name or scheme_name,
            scheme_id="pmfby",
            status=EvaluationStatus.NOT_ELIGIBLE.value,
            decision_reason_code=DecisionReasonCode.MANDATORY_FAIL.value,
            evaluation_complete=True,
        )
    if resolved_sid == "pmfby" and facts.get("growing_crop") is False:
        return EligibilityEvaluationResult(
            scheme_name=criteria.scheme_name or scheme_name,
            scheme_id="pmfby",
            status=EvaluationStatus.NOT_ELIGIBLE.value,
            decision_reason_code=DecisionReasonCode.MANDATORY_FAIL.value,
            evaluation_complete=True,
        )

    if criteria.rejected or not criteria.criteria:
        return None

    from app.services.eligibility_criteria import enrich_assistance_fields_from_criteria

    required, _, _ = enrich_assistance_fields_from_criteria(criteria)

    return evaluate_eligibility(
        criteria=criteria,
        citizen_answers=facts,
        scheme_name=criteria.scheme_name,
        scheme_id=criteria.scheme_id,
        evidence_validated=evidence_validated,
        required_information=required,
    )
