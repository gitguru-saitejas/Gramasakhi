"""Retrieval-oriented normalized queries (no invented scheme facts)."""

from __future__ import annotations

from typing import Optional

from app.services.human_language.intent_models import HumanLanguageIntent

_TEMPLATES = {
    HumanLanguageIntent.APPLICATION_PROCESS: "What is the application process for {scheme}?",
    HumanLanguageIntent.APPLICATION_CHANNEL: "Where can I apply for {scheme}? Official portal or office.",
    HumanLanguageIntent.DOCUMENTS_REQUIRED: "What documents are required to apply for {scheme}?",
    HumanLanguageIntent.ELIGIBILITY: "What are the eligibility criteria for {scheme}?",
    HumanLanguageIntent.PERSONAL_ELIGIBILITY: "Am I eligible for {scheme}? What criteria apply?",
    HumanLanguageIntent.BENEFITS: "What benefits does {scheme} provide?",
    HumanLanguageIntent.BENEFITS_AMOUNT: "What is the benefit amount for {scheme}?",
    HumanLanguageIntent.GENERAL_INFORMATION: "What is {scheme}? Overview and key details.",
    HumanLanguageIntent.SCHEME_DISCOVERY: "Which government schemes are available?",
    HumanLanguageIntent.STATUS: "How can I check application status for {scheme}?",
}


def build_normalized_query(
    intent: HumanLanguageIntent,
    *,
    original_query: str,
    scheme_name: Optional[str] = None,
) -> str:
    scheme = (scheme_name or "this scheme").strip()
    tpl = _TEMPLATES.get(intent)
    if tpl:
        return tpl.format(scheme=scheme)
    q = (original_query or "").strip()
    return q if q else "Government scheme information"
