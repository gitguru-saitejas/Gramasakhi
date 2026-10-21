"""Shared human-language interpretation entry point."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional, Sequence

from app.services.human_language.context_resolver import resolve_scheme_context
from app.services.human_language.conversational import (
    clarification_for_unknown,
    detect_language_change,
    detect_multi_intents,
    query_has_retrieval_structure,
)
from app.services.human_language.entity_extractor import extract_entities
from app.services.human_language.intent_models import (
    ConversationalTag,
    HumanLanguageIntent,
    NLUResult,
)
from app.services.human_language.llm_classifier import classify_with_llm
from app.services.human_language.patterns import classify_from_patterns, followup_application_cues
from app.services.human_language.query_normalizer import build_normalized_query
from app.services.human_language.short_followup import resolve_short_followup

logger = logging.getLogger("gramsakhi.human_language")


def _normalize_text(text: str) -> str:
    try:
        from app.services.citizen_assistance import _normalize

        return _normalize(text)
    except Exception:
        from app.services.multilingual_retrieval_service import normalize_stt_artifacts

        return normalize_stt_artifacts(text or "")


def interpret_human_language(
    query: str,
    *,
    conversation_history: Optional[Sequence[Dict[str, Any]]] = None,
    rewrite_active_scheme: Optional[str] = None,
    conversation_active_scheme: Optional[str] = None,
    use_llm: bool = True,
) -> NLUResult:
    original = _normalize_text(query)
    scheme_ctx = resolve_scheme_context(
        original,
        conversation_history=conversation_history,
        rewrite_active_scheme=rewrite_active_scheme,
        conversation_active_scheme=conversation_active_scheme,
    )
    scheme_name = scheme_ctx.get("scheme_name")
    scheme_id = scheme_ctx.get("scheme_id")

    tags: list[str] = []
    output_language: Optional[str] = None
    is_lang_cmd, lang_code = detect_language_change(original)
    if is_lang_cmd and lang_code:
        tags.append(ConversationalTag.LANGUAGE_CHANGE.value)
        output_language = lang_code

    secondary = detect_multi_intents(original)
    if secondary:
        tags.append(ConversationalTag.MULTI_INTENT.value)

    intent, conf = classify_from_patterns(original)
    classifier = "deterministic"

    lower = original.lower()
    if not scheme_name and len(lower.split()) <= 3:
        if re.match(
            r"^(documents?|papers?|money|apply|application|status|eligibility|"
            r"amount|benefits?|where|how|when|why)\??$",
            lower,
        ):
            intent = HumanLanguageIntent.UNKNOWN
            conf = 0.0

    if intent == HumanLanguageIntent.UNKNOWN and scheme_name:
        short_intent, short_conf = resolve_short_followup(
            original, active_scheme=scheme_name
        )
        if short_intent:
            intent = short_intent
            conf = short_conf
            classifier = "short_followup"

    if intent == HumanLanguageIntent.UNKNOWN and scheme_name:
        try:
            from app.services.query_rewriter import _looks_like_followup

            if _looks_like_followup(original) and followup_application_cues(original):
                intent = HumanLanguageIntent.APPLICATION_PROCESS
                conf = 0.7
        except Exception:
            pass

    if intent == HumanLanguageIntent.UNKNOWN and use_llm and not is_lang_cmd:
        llm_intent, llm_conf = classify_with_llm(
            original, active_scheme=scheme_name, timeout_seconds=3.0
        )
        if llm_intent is not None:
            intent = llm_intent
            conf = llm_conf
            classifier = "llm"

    bare_contextual = (
        not scheme_name
        and len(lower.split()) <= 3
        and re.match(
            r"^(documents?|papers?|money|apply|application|status|eligibility|"
            r"amount|benefits?|where|how|when|why)\??$",
            lower,
        )
    )
    if intent == HumanLanguageIntent.UNKNOWN and not is_lang_cmd and not bare_contextual:
        try:
            from app.services.multilingual_retrieval_service import detect_intent

            bridged = detect_intent(original)
            bridge_map = {
                "eligibility": HumanLanguageIntent.ELIGIBILITY,
                "benefits": HumanLanguageIntent.BENEFITS,
                "amount": HumanLanguageIntent.BENEFITS_AMOUNT,
                "documents": HumanLanguageIntent.DOCUMENTS_REQUIRED,
                "application": HumanLanguageIntent.APPLICATION_PROCESS,
                "status": HumanLanguageIntent.STATUS,
                "overview": HumanLanguageIntent.GENERAL_INFORMATION,
            }
            if bridged in bridge_map:
                intent = bridge_map[bridged]
                conf = 0.6
                classifier = "retrieval_bridge"
        except Exception:
            pass

    if bare_contextual:
        intent = HumanLanguageIntent.UNKNOWN
        conf = 0.0

    if secondary and intent == HumanLanguageIntent.UNKNOWN and secondary:
        intent = secondary[0]
        conf = 0.65
        classifier = "multi_intent"

    if (
        intent == HumanLanguageIntent.UNKNOWN
        and not is_lang_cmd
        and query_has_retrieval_structure(original)
    ):
        intent = HumanLanguageIntent.GENERAL_INFORMATION
        conf = max(conf, 0.55)
        if classifier == "deterministic":
            classifier = "complete_query_routing"

    needs_clarification = False
    clarification_prompt: Optional[str] = None
    if intent == HumanLanguageIntent.UNKNOWN and not is_lang_cmd:
        needs_clarification, clarification_prompt = clarification_for_unknown(
            original, active_scheme=scheme_name
        )
        if needs_clarification:
            tags.append(ConversationalTag.CLARIFICATION.value)

    primary_intent = intent
    if is_lang_cmd:
        primary_intent = HumanLanguageIntent.GENERAL_INFORMATION

    entities = extract_entities(original)
    if scheme_name and "scheme" not in entities:
        entities["scheme"] = scheme_name

    normalized = build_normalized_query(
        primary_intent if not is_lang_cmd else HumanLanguageIntent.GENERAL_INFORMATION,
        original_query=original,
        scheme_name=scheme_name,
    )
    if is_lang_cmd:
        normalized = original

    references: Dict[str, Any] = {}
    if scheme_name:
        references["scheme"] = "current_conversation_scheme"

    result = NLUResult(
        intent=primary_intent,
        secondary_intents=secondary[1:] if len(secondary) > 1 else [],
        scheme_id=scheme_id,
        scheme_name=scheme_name,
        entities=entities,
        original_query=original,
        normalized_query=normalized,
        classifier=classifier,
        confidence=conf,
        output_language=output_language,
        conversational_tags=tags,
        needs_clarification=needs_clarification and not is_lang_cmd,
        clarification_prompt=clarification_prompt,
        references=references,
    )
    logger.info(
        "NLU original=%r intent=%s secondary=%s scheme=%s tags=%s clarify=%s normalized=%r",
        original[:120],
        result.intent.value,
        [i.value for i in result.secondary_intents],
        result.scheme_name,
        result.conversational_tags,
        result.needs_clarification,
        result.normalized_query[:160],
    )
    return result
