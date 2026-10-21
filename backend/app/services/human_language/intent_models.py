"""Shared human-language intent model (backend-only NLU)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.services.citizen_assistance import CitizenIntent


class ConversationalTag(str, Enum):
    LANGUAGE_CHANGE = "LANGUAGE_CHANGE"
    MULTI_INTENT = "MULTI_INTENT"
    CLARIFICATION = "CLARIFICATION"
    CORRECTION = "CORRECTION"


class HumanLanguageIntent(str, Enum):
    SCHEME_DISCOVERY = "SCHEME_DISCOVERY"
    GENERAL_INFORMATION = "GENERAL_INFORMATION"
    ELIGIBILITY = "ELIGIBILITY"
    PERSONAL_ELIGIBILITY = "PERSONAL_ELIGIBILITY"
    BENEFITS = "BENEFITS"
    BENEFITS_AMOUNT = "BENEFITS_AMOUNT"
    APPLICATION_PROCESS = "APPLICATION_PROCESS"
    APPLICATION_CHANNEL = "APPLICATION_CHANNEL"
    DOCUMENTS_REQUIRED = "DOCUMENTS_REQUIRED"
    STATUS = "STATUS"
    UNKNOWN = "UNKNOWN"


def map_to_citizen_intent(intent: HumanLanguageIntent) -> CitizenIntent:
    """Preserve existing CitizenIntent API while exposing richer NLU intents."""
    return {
        HumanLanguageIntent.SCHEME_DISCOVERY: CitizenIntent.OVERVIEW,
        HumanLanguageIntent.GENERAL_INFORMATION: CitizenIntent.OVERVIEW,
        HumanLanguageIntent.ELIGIBILITY: CitizenIntent.ELIGIBILITY,
        HumanLanguageIntent.PERSONAL_ELIGIBILITY: CitizenIntent.PERSONAL_ELIGIBILITY,
        HumanLanguageIntent.BENEFITS: CitizenIntent.BENEFITS,
        HumanLanguageIntent.BENEFITS_AMOUNT: CitizenIntent.BENEFITS,
        HumanLanguageIntent.APPLICATION_PROCESS: CitizenIntent.APPLICATION,
        HumanLanguageIntent.APPLICATION_CHANNEL: CitizenIntent.APPLICATION_PORTAL,
        HumanLanguageIntent.DOCUMENTS_REQUIRED: CitizenIntent.DOCUMENTS,
        HumanLanguageIntent.STATUS: CitizenIntent.GENERAL_FOLLOWUP,
        HumanLanguageIntent.UNKNOWN: CitizenIntent.UNKNOWN,
    }.get(intent, CitizenIntent.UNKNOWN)


def retrieval_intent_hint(intent: HumanLanguageIntent) -> Optional[str]:
    """Bridge NLU intent → multilingual_retrieval_service string intent."""
    return {
        HumanLanguageIntent.SCHEME_DISCOVERY: "overview",
        HumanLanguageIntent.GENERAL_INFORMATION: "overview",
        HumanLanguageIntent.ELIGIBILITY: "eligibility",
        HumanLanguageIntent.PERSONAL_ELIGIBILITY: "eligibility",
        HumanLanguageIntent.BENEFITS: "benefits",
        HumanLanguageIntent.BENEFITS_AMOUNT: "amount",
        HumanLanguageIntent.APPLICATION_PROCESS: "application",
        HumanLanguageIntent.APPLICATION_CHANNEL: "application",
        HumanLanguageIntent.DOCUMENTS_REQUIRED: "documents",
        HumanLanguageIntent.STATUS: "status",
    }.get(intent)


@dataclass
class NLUResult:
    intent: HumanLanguageIntent = HumanLanguageIntent.UNKNOWN
    secondary_intents: List[HumanLanguageIntent] = field(default_factory=list)
    scheme_id: Optional[str] = None
    scheme_name: Optional[str] = None
    entities: Dict[str, Any] = field(default_factory=dict)
    original_query: str = ""
    normalized_query: str = ""
    classifier: str = "deterministic"
    confidence: float = 0.0
    output_language: Optional[str] = None
    conversational_tags: List[str] = field(default_factory=list)
    needs_clarification: bool = False
    clarification_prompt: Optional[str] = None
    references: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent.value,
            "secondary_intents": [i.value for i in self.secondary_intents],
            "scheme_id": self.scheme_id,
            "scheme_name": self.scheme_name,
            "entities": dict(self.entities),
            "original_query": self.original_query,
            "normalized_query": self.normalized_query,
            "classifier": self.classifier,
            "confidence": self.confidence,
            "output_language": self.output_language,
            "conversational_tags": list(self.conversational_tags),
            "needs_clarification": self.needs_clarification,
            "clarification_prompt": self.clarification_prompt,
            "references": dict(self.references),
        }
