"""Stage 6A — citizen intent classification and assistance context.

Sits above retrieval/generation. Does not replace RAG, providers, or EV.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

from app.services.query_rewriter import (
    extract_scheme_mentions,
    history_active_scheme,
    is_standalone_query,
)


class CitizenIntent(str, Enum):
    OVERVIEW = "OVERVIEW"
    ELIGIBILITY = "ELIGIBILITY"
    BENEFITS = "BENEFITS"
    DOCUMENTS = "DOCUMENTS"
    APPLICATION = "APPLICATION"
    DEADLINE = "DEADLINE"
    APPLICATION_PORTAL = "APPLICATION_PORTAL"
    NEXT_ACTION = "NEXT_ACTION"
    PERSONAL_ELIGIBILITY = "PERSONAL_ELIGIBILITY"
    COMPARISON = "COMPARISON"
    GENERAL_FOLLOWUP = "GENERAL_FOLLOWUP"
    CLARIFICATION = "CLARIFICATION"
    UNKNOWN = "UNKNOWN"


class AssistanceMode(str, Enum):
    OVERVIEW = "overview"
    ELIGIBILITY = "eligibility"
    BENEFITS = "benefits"
    DOCUMENTS = "documents"
    APPLICATION = "application"
    DEADLINE = "deadline"
    APPLICATION_PORTAL = "application_portal"
    NEXT_ACTION = "next_action"
    COLLECT_INFORMATION = "collect_information"
    COMPARISON = "comparison"
    FOLLOW_UP = "follow_up"
    CLARIFICATION = "clarification"
    GENERAL = "general"


# Ordered — first match wins (more specific before broad).
_INTENT_RULES: tuple[tuple[CitizenIntent, tuple[str, ...]], ...] = (
    (
        CitizenIntent.COMPARISON,
        (
            "compare",
            "comparison",
            " versus ",
            " vs ",
            "difference between",
            "differences between",
            "तुलना",
            "ಹೋಲಿಸ",
        ),
    ),
    (
        CitizenIntent.PERSONAL_ELIGIBILITY,
        (
            "am i eligible",
            "can i get this scheme",
            "can i get the scheme",
            "do i qualify",
            "am i qualified",
            "eligible for me",
            "ನನಗೆ ಸಿಗುತ್ತದೆಯ",
            "ನಾನು ಅರ್ಹ",
            "मुझे मिल",
            "क्या मैं पात्र",
            "main eligible",
        ),
    ),
    (
        CitizenIntent.APPLICATION_PORTAL,
        (
            "where can i apply",
            "where to apply",
            "application portal",
            "official portal",
            "official website",
            "apply online",
            "register online",
            "ಎಲ್ಲಿ ಅರ್ಜಿ",
            "कहाँ आवेदन",
            "portal link",
            "application link",
            "official application link",
            "official pdf",
        ),
    ),
    (
        CitizenIntent.NEXT_ACTION,
        (
            "what should i do next",
            "what do i do next",
            "what should i do",
            "next step",
            "next steps",
            "what next",
            "can i apply now",
            "what do i need before applying",
            "do i need anything else",
            "what documents should i keep",
            "okay, what next",
            "ಮುಂದೆ ಏನು",
            "ಮುಂದಿನ ಹಂತ",
            "आगे क्या",
            "अगला कदम",
        ),
    ),
    (
        CitizenIntent.DEADLINE,
        (
            "deadline",
            "last date",
            "closing date",
            "last day",
            "ಅಂತಿಮ ದಿನಾಂಕ",
            "ಕೊನೆಯ ದಿನ",
            "अंतिम तिथि",
            "आखिरी तारीख",
        ),
    ),
    (
        CitizenIntent.DOCUMENTS,
        (
            "document",
            "documents required",
            "required documents",
            "papers required",
            "certificates required",
            "what papers",
            "ದಾಖಲೆ",
            "ದಾಖಲಾತಿ",
            "दस्तावेज",
            "कागज",
        ),
    ),
    (
        CitizenIntent.APPLICATION,
        (
            "how to apply",
            "how do i apply",
            "application process",
            "application procedure",
            "apply for",
            "registration process",
            "ಅರ್ಜಿ ಹಾಕ",
            "ಅರ್ಜಿ ಸಲ್ಲಿಸ",
            "आवेदन कैसे",
            "आवेदन प्रक्रिया",
        ),
    ),
    (
        CitizenIntent.ELIGIBILITY,
        (
            "eligibility",
            "eligible",
            "who is eligible",
            "who can apply",
            "who can get",
            "criteria",
            "qualification",
            "ಅರ್ಹ",
            "ಯಾರು ಅರ್ಹ",
            "arharu",
            "arhru",
            "yaru arhru",
            "yojaneke yaaru arhru",
            "पात्र",
            "पात्रता",
            "कौन पात्र",
            "kaun eligible",
            "kaun eligible hai",
            "kaun patra",
        ),
    ),
    (
        CitizenIntent.BENEFITS,
        (
            "benefit",
            "benefits",
            "subsidy",
            "assistance amount",
            "how much",
            "what do i get",
            "financial help",
            "ಪ್ರಯೋಜನ",
            "ಲಾಭ",
            "लाभ",
            "सहायता",
            "राशि",
        ),
    ),
    (
        CitizenIntent.CLARIFICATION,
        (
            "what do you mean",
            "clarify",
            "explain that",
            "i don't understand",
            "not clear",
            "ಸ್ಪಷ್ಟ",
            "स्पष्ट",
        ),
    ),
    (
        CitizenIntent.GENERAL_FOLLOWUP,
        (
            "tell me more",
            "more details",
            "more information",
            "explain more",
            "go on",
            "continue",
            "ಇನ್ನಷ್ಟು",
            "ಹೆಚ್ಚು ಹೇಳ",
            "और बताओ",
            "और जानकारी",
        ),
    ),
    (
        CitizenIntent.OVERVIEW,
        (
            "what is",
            "what are",
            "tell me about",
            "information about",
            "details about",
            "about the scheme",
            "scheme about",
            "ಯೋಜನೆ ಬಗ್ಗೆ",
            "yojana ke bare",
            "योजना के बारे",
            "overview",
        ),
    ),
)


def _normalize(text: str) -> str:
    t = (text or "").replace("\u00a0", " ")
    t = re.sub(r"\s+", " ", t).strip()
    try:
        from app.services.multilingual_retrieval_service import normalize_stt_artifacts

        t = normalize_stt_artifacts(t)
    except Exception:
        pass
    return t


def classify_citizen_intent(
    query: str,
    *,
    conversation_history: Optional[Sequence[Dict[str, Any]]] = None,
    active_scheme: Optional[str] = None,
) -> CitizenIntent:
    """Multilingual intent from citizen question (+ light follow-up context)."""
    raw = _normalize(query)
    if not raw:
        return CitizenIntent.UNKNOWN

    lower = raw.lower()

    # Legacy high-specificity rules (comparison, deadline, next action, clarification).
    for intent, markers in _INTENT_RULES:
        if intent in (
            CitizenIntent.COMPARISON,
            CitizenIntent.DEADLINE,
            CitizenIntent.NEXT_ACTION,
            CitizenIntent.CLARIFICATION,
            CitizenIntent.GENERAL_FOLLOWUP,
        ):
            for marker in markers:
                if marker.lower() in lower or marker in raw:
                    return intent

    try:
        from app.services.human_language import interpret_human_language, map_to_citizen_intent

        nlu = interpret_human_language(
            raw,
            conversation_history=conversation_history,
            conversation_active_scheme=active_scheme,
            use_llm=False,
        )
        mapped = map_to_citizen_intent(nlu.intent)
        if mapped != CitizenIntent.UNKNOWN:
            return mapped
    except Exception:
        pass

    for intent, markers in _INTENT_RULES:
        for marker in markers:
            if marker.lower() in lower or marker in raw:
                return intent

    if conversation_history and active_scheme:
        try:
            from app.services.query_rewriter import _looks_like_followup

            if _looks_like_followup(raw):
                return CitizenIntent.GENERAL_FOLLOWUP
        except Exception:
            pass

    return CitizenIntent.UNKNOWN


def extract_comparison_schemes(query: str) -> List[str]:
    """Return distinct schemes named in a comparison question."""
    mentions = extract_scheme_mentions(query)
    if len(mentions) >= 2:
        return mentions
    lower = (query or "").lower()
    if not any(k in lower for k in ("compare", " vs ", " versus ", "difference")):
        return mentions
    # "compare PM-KISAN and PMFBY" — split on conjunctions and re-scan.
    parts = re.split(r"\band\b|\bwith\b|\bvs\.?\b|\bversus\b|,", query or "", flags=re.I)
    found: List[str] = []
    for part in parts:
        for name in extract_scheme_mentions(part):
            if name not in found:
                found.append(name)
    return found or mentions


def resolve_detected_scheme(
    original_query: str,
    *,
    rewrite_active_scheme: Optional[str] = None,
    conversation_active_scheme: Optional[str] = None,
    conversation_history: Optional[Sequence[Dict[str, Any]]] = None,
) -> Optional[str]:
    """Explicit scheme in query overrides prior context."""
    mentions = extract_scheme_mentions(original_query)
    if mentions:
        return mentions[0]
    if is_standalone_query(original_query):
        try:
            from app.services.myscheme_service import requested_scheme_identity

            ident = requested_scheme_identity(original_query)
            name = (ident or {}).get("scheme_name") or ""
            if name:
                return name.strip()[:120]
        except Exception:
            pass
    try:
        from app.services.query_rewriter import (
            _NEW_TOPIC_OPENER,
            _PRONOUN_SCHEME,
            _looks_like_followup,
        )

        if (
            _NEW_TOPIC_OPENER.search(original_query)
            and not _PRONOUN_SCHEME.search(original_query)
            and not _looks_like_followup(original_query)
            and not mentions
        ):
            return None
    except Exception:
        pass
    if rewrite_active_scheme:
        return rewrite_active_scheme
    if conversation_active_scheme:
        return conversation_active_scheme
    if conversation_history:
        return history_active_scheme(conversation_history)
    return None


def assistance_mode_for_intent(intent: CitizenIntent) -> AssistanceMode:
    return {
        CitizenIntent.OVERVIEW: AssistanceMode.OVERVIEW,
        CitizenIntent.ELIGIBILITY: AssistanceMode.ELIGIBILITY,
        CitizenIntent.BENEFITS: AssistanceMode.BENEFITS,
        CitizenIntent.DOCUMENTS: AssistanceMode.DOCUMENTS,
        CitizenIntent.APPLICATION: AssistanceMode.APPLICATION,
        CitizenIntent.DEADLINE: AssistanceMode.DEADLINE,
        CitizenIntent.APPLICATION_PORTAL: AssistanceMode.APPLICATION_PORTAL,
        CitizenIntent.NEXT_ACTION: AssistanceMode.NEXT_ACTION,
        CitizenIntent.PERSONAL_ELIGIBILITY: AssistanceMode.COLLECT_INFORMATION,
        CitizenIntent.COMPARISON: AssistanceMode.COMPARISON,
        CitizenIntent.GENERAL_FOLLOWUP: AssistanceMode.FOLLOW_UP,
        CitizenIntent.CLARIFICATION: AssistanceMode.CLARIFICATION,
        CitizenIntent.UNKNOWN: AssistanceMode.GENERAL,
    }.get(intent, AssistanceMode.GENERAL)


def build_personal_eligibility_framework(
    *,
    intent: CitizenIntent,
) -> tuple[List[str], List[str], List[str]]:
    """Framework only — required fields come from scheme evidence in later stages."""
    if intent != CitizenIntent.PERSONAL_ELIGIBILITY:
        return [], [], []
    # Placeholder interface; do not invent scheme-specific fields in Stage 6A.
    return [], [], []


@dataclass
class AssistanceContext:
    intent: CitizenIntent = CitizenIntent.UNKNOWN
    detected_scheme: Optional[str] = None
    comparison_schemes: List[str] = field(default_factory=list)
    conversation_id: Optional[str] = None
    response_language: Optional[str] = None
    assistance_mode: AssistanceMode = AssistanceMode.GENERAL
    required_information: List[str] = field(default_factory=list)
    known_information: List[str] = field(default_factory=list)
    missing_information: List[str] = field(default_factory=list)
    is_follow_up: bool = False
    is_comparison: bool = False
    original_query: str = ""
    nlu_intent: Optional[str] = None
    normalized_query: Optional[str] = None
    scheme_id: Optional[str] = None
    nlu_entities: Dict[str, Any] = field(default_factory=dict)
    nlu_secondary_intents: List[str] = field(default_factory=list)
    nlu_conversational_tags: List[str] = field(default_factory=list)
    nlu_needs_clarification: bool = False
    nlu_clarification_prompt: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["intent"] = self.intent.value
        d["assistance_mode"] = self.assistance_mode.value
        return d


def build_assistance_context(
    *,
    original_query: str,
    conversation_id: Optional[str] = None,
    response_language: Optional[str] = None,
    conversation_history: Optional[Sequence[Dict[str, Any]]] = None,
    rewrite_active_scheme: Optional[str] = None,
    conversation_active_scheme: Optional[str] = None,
) -> AssistanceContext:
    """Request-level assistance state (not persisted beyond conversation scheme field)."""
    raw = _normalize(original_query)
    comparison_schemes = extract_comparison_schemes(raw)
    is_comparison = len(comparison_schemes) >= 2 or (
        len(comparison_schemes) >= 1
        and bool(re.search(r"\b(compare|versus| vs |difference between)\b", raw, re.I))
    )

    from app.services.human_language import interpret_human_language, map_to_citizen_intent

    nlu = interpret_human_language(
        raw,
        conversation_history=conversation_history,
        rewrite_active_scheme=rewrite_active_scheme,
        conversation_active_scheme=conversation_active_scheme,
    )
    detected_scheme = nlu.scheme_name or resolve_detected_scheme(
        raw,
        rewrite_active_scheme=rewrite_active_scheme,
        conversation_active_scheme=conversation_active_scheme,
        conversation_history=conversation_history,
    )
    if is_comparison and comparison_schemes:
        detected_scheme = comparison_schemes[0]

    intent = map_to_citizen_intent(nlu.intent)
    if is_comparison:
        intent = CitizenIntent.COMPARISON
    elif intent == CitizenIntent.UNKNOWN and not nlu.needs_clarification:
        intent = classify_citizen_intent(
            raw,
            conversation_history=conversation_history,
            active_scheme=detected_scheme,
        )

    is_follow_up = False
    if conversation_history and detected_scheme:
        try:
            from app.services.query_rewriter import _looks_like_followup

            is_follow_up = _looks_like_followup(raw) and not is_standalone_query(raw)
        except Exception:
            is_follow_up = False

    if intent == CitizenIntent.UNKNOWN and is_follow_up:
        intent = CitizenIntent.GENERAL_FOLLOWUP

    if (
        nlu.needs_clarification
        and nlu.clarification_prompt
        and intent == CitizenIntent.UNKNOWN
        and "LANGUAGE_CHANGE" not in (nlu.conversational_tags or [])
    ):
        intent = CitizenIntent.CLARIFICATION

    mode = assistance_mode_for_intent(intent)
    required, known, missing = build_personal_eligibility_framework(intent=intent)

    return AssistanceContext(
        intent=intent,
        detected_scheme=detected_scheme,
        comparison_schemes=comparison_schemes,
        conversation_id=conversation_id,
        response_language=response_language,
        assistance_mode=mode,
        required_information=required,
        known_information=known,
        missing_information=missing,
        is_follow_up=is_follow_up,
        is_comparison=is_comparison,
        original_query=raw,
        nlu_intent=nlu.intent.value,
        normalized_query=nlu.normalized_query,
        scheme_id=nlu.scheme_id,
        nlu_entities=dict(nlu.entities),
        nlu_secondary_intents=[i.value for i in nlu.secondary_intents],
        nlu_conversational_tags=list(nlu.conversational_tags),
        nlu_needs_clarification=bool(nlu.needs_clarification),
        nlu_clarification_prompt=nlu.clarification_prompt,
    )


def intent_generation_rule(intent: CitizenIntent) -> str:
    """Prompt fragment for Ollama — not a separate LLM pipeline."""
    rules = {
        CitizenIntent.OVERVIEW: "Give a concise scheme overview using available evidence.",
        CitizenIntent.ELIGIBILITY: "Focus on eligibility criteria only.",
        CitizenIntent.BENEFITS: "Focus on benefits/assistance only.",
        CitizenIntent.DOCUMENTS: "Focus on required documents only.",
        CitizenIntent.APPLICATION: "Focus on application procedure only.",
        CitizenIntent.DEADLINE: "Focus on deadline/date information only if present in evidence.",
        CitizenIntent.APPLICATION_PORTAL: "Focus on official application route/portal only.",
        CitizenIntent.NEXT_ACTION: (
            "Focus on the next actionable step supported by evidence "
            "(documents, application route, or portal) without inventing a workflow."
        ),
        CitizenIntent.PERSONAL_ELIGIBILITY: (
            "Do NOT claim the citizen is eligible or ineligible. "
            "If personal details are needed, say you can help check eligibility and "
            "may need a few details first."
        ),
        CitizenIntent.COMPARISON: (
            "Compare schemes separately. Never mix facts from one scheme into another."
        ),
        CitizenIntent.GENERAL_FOLLOWUP: "Answer the follow-up using conversation context.",
        CitizenIntent.CLARIFICATION: "Clarify using only the supplied evidence.",
        CitizenIntent.UNKNOWN: "Answer only what the question asks using available evidence.",
    }
    return rules.get(intent, rules[CitizenIntent.UNKNOWN])
