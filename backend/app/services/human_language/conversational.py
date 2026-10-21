"""Language commands, multi-intent hints, and clarification helpers."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from app.services.human_language.intent_models import HumanLanguageIntent

ConversationalTag = str  # LANGUAGE_CHANGE | MULTI_INTENT | CLARIFICATION


def detect_language_change(text: str) -> Tuple[bool, Optional[str]]:
    """Return (is_language_only_command, KN|HI|EN)."""
    from app.services.language_service import _has_explicit_language_request

    t = (text or "").strip()
    if not t:
        return False, None
    low = t.lower()
    for word, code in (("kannada", "KN"), ("hindi", "HI"), ("english", "EN")):
        if re.search(rf"\b{word}\s+please\b", low) or re.search(rf"\bplease\s+{word}\b", low):
            return True, code
    if re.search(r"\bkannada\s+dalli\s+heli\b", low) or "ಕನ್ನಡದಲ್ಲಿ" in t:
        return True, "KN"
    if re.search(r"\bhindi\s+mein\s+bata", low) or "हिंदी में" in t:
        return True, "HI"
    explicit = _has_explicit_language_request(t)
    if explicit and len(t.split()) <= 8:
        factual = re.search(
            r"\b(eligibility|benefit|document|apply|scheme|yojana|amount|deadline)\b", low
        )
        if not factual:
            return True, explicit
    return False, None


def detect_multi_intents(text: str) -> List[HumanLanguageIntent]:
    """Lightweight multi-intent detection for compound questions."""
    low = (text or "").lower()
    found: List[HumanLanguageIntent] = []
    checks = (
        (HumanLanguageIntent.GENERAL_INFORMATION, r"\b(what is|tell me about|about this scheme)\b"),
        (HumanLanguageIntent.ELIGIBILITY, r"\b(who (is|can)|eligible|eligibility)\b"),
        (HumanLanguageIntent.PERSONAL_ELIGIBILITY, r"\b(can i|am i|for me|mere liye)\b"),
        (HumanLanguageIntent.APPLICATION_PROCESS, r"\b(how (do|can|to) i apply|how to apply|how do i get)\b"),
        (HumanLanguageIntent.DOCUMENTS_REQUIRED, r"\b(document|documents|papers|dakhale|kagaz)\b"),
        (HumanLanguageIntent.BENEFITS_AMOUNT, r"\b(how much|amount|money|kitna|estu)\b"),
        (HumanLanguageIntent.STATUS, r"\b(status|track|approved)\b"),
    )
    for intent, pat in checks:
        if re.search(pat, low):
            if intent not in found:
                found.append(intent)
    if len(found) <= 1:
        return []
    return found


def _is_citizen_eligibility_fact_statement(text: str) -> bool:
    """Personal facts during eligibility Q&A — not scheme retrieval queries."""
    raw = (text or "").strip()
    if not raw or "?" in raw:
        return False
    low = raw.lower()
    if re.search(
        r"\b(eligible|eligibility|apply|scheme|yojana|benefit|documents?|pm[- ]?\w+)\b",
        low,
    ):
        return False
    if re.search(
        r"\b(my income|i am \d|i'm \d|i live in|i'm living in|meri aamdani)\b",
        low,
    ):
        return True
    if re.search(r"\bincome is\b", low) and re.search(r"\d", low):
        return True
    return False


def query_has_retrieval_structure(text: str) -> bool:
    """True when the utterance is complete enough to route to RAG (not a menu prompt)."""
    raw = (text or "").strip()
    if not raw:
        return False
    low = raw.lower()
    words = low.split()
    if len(words) == 1 and re.match(
        r"^(how|what|where|when|why|who|documents?|money|apply|status|eligibility)\??$",
        low,
    ):
        return False
    if _is_citizen_eligibility_fact_statement(raw):
        return False
    if len(words) >= 5:
        return True
    if re.search(
        r"\b(who|what|which|how|does|do|can|are|is|will|where|when|through|according|"
        r"mention|describe|include|list|administer|enroll|insure|require|provide|"
        r"typically|commonly|according)\b",
        low,
    ):
        return True
    if "?" in raw and len(words) >= 3:
        return True
    return False


def _is_incomplete_with_known_scheme(text: str) -> bool:
    """Short or keyword-only follow-ups when scheme context is already known."""
    raw = (text or "").strip()
    if not raw:
        return True
    lower = re.sub(r"\s+", " ", raw.lower()).strip()
    words = lower.split()
    if query_has_retrieval_structure(raw):
        return False
    if len(words) <= 2:
        return True
    if re.match(
        r"^(documents?|papers?|money|apply|application|status|eligibility|"
        r"amount|benefits?|where|how|when|why|what about)\??$",
        lower,
    ):
        return True
    return len(words) <= 3


def clarification_for_unknown(
    text: str,
    *,
    active_scheme: Optional[str] = None,
) -> Tuple[bool, str]:
    raw = (text or "").strip()
    if not raw:
        return True, "What would you like to know about government schemes?"
    if query_has_retrieval_structure(raw):
        return False, ""
    if active_scheme and _is_incomplete_with_known_scheme(raw):
        return (
            True,
            "Do you want to know how to apply, what documents are needed, "
            "whether you are eligible, or the benefit amount?",
        )
    if re.search(r"^(documents?|money|apply|status|eligibility|how|where)\??$", raw, re.I):
        return True, "Sure — which scheme are you asking about?"
    return False, ""
