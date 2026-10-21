"""Resolve very short utterances using active scheme conversation context."""

from __future__ import annotations

import re
from typing import Optional, Tuple

from app.services.human_language.intent_models import HumanLanguageIntent

# Single-token or minimal follow-ups (lowercase Latin + common KN/HI translit)
_SHORT_INTENT: Tuple[Tuple[str, HumanLanguageIntent], ...] = (
    (r"^documents?\??$", HumanLanguageIntent.DOCUMENTS_REQUIRED),
    (r"^papers?\??$", HumanLanguageIntent.DOCUMENTS_REQUIRED),
    (r"^dakhale?\??$", HumanLanguageIntent.DOCUMENTS_REQUIRED),
    (r"^documents\s+yenu\s+beku\??$", HumanLanguageIntent.DOCUMENTS_REQUIRED),
    (r"^yaava\s+documents?\??$", HumanLanguageIntent.DOCUMENTS_REQUIRED),
    (r"^yaava\s+paper(s)?\??$", HumanLanguageIntent.DOCUMENTS_REQUIRED),
    (r"^kagaz\??$", HumanLanguageIntent.DOCUMENTS_REQUIRED),
    (r"^money\??$", HumanLanguageIntent.BENEFITS_AMOUNT),
    (r"^amount\??$", HumanLanguageIntent.BENEFITS_AMOUNT),
    (r"^estu\??$", HumanLanguageIntent.BENEFITS_AMOUNT),
    (r"^how\s+much\??$", HumanLanguageIntent.BENEFITS_AMOUNT),
    (r"^kitna\??$", HumanLanguageIntent.BENEFITS_AMOUNT),
    (r"^apply\??$", HumanLanguageIntent.APPLICATION_PROCESS),
    (r"^application\??$", HumanLanguageIntent.APPLICATION_PROCESS),
    (r"^status\??$", HumanLanguageIntent.STATUS),
    (r"^eligibility\??$", HumanLanguageIntent.ELIGIBILITY),
    (r"^eligible\??$", HumanLanguageIntent.PERSONAL_ELIGIBILITY),
    (r"^for\s+me\??$", HumanLanguageIntent.PERSONAL_ELIGIBILITY),
    (r"^me\??$", HumanLanguageIntent.PERSONAL_ELIGIBILITY),
    (r"^my\s+case\??$", HumanLanguageIntent.PERSONAL_ELIGIBILITY),
    (r"^nan\s+case\s+alli\??$", HumanLanguageIntent.PERSONAL_ELIGIBILITY),
    (r"^nanage\s+eligible\s+aa\??$", HumanLanguageIntent.PERSONAL_ELIGIBILITY),
    (r"^where\??$", HumanLanguageIntent.APPLICATION_CHANNEL),
    (r"^yelli\??$", HumanLanguageIntent.APPLICATION_CHANNEL),
    (r"^yelli\s+hogbeku\??$", HumanLanguageIntent.APPLICATION_CHANNEL),
    (r"^kahan\??$", HumanLanguageIntent.APPLICATION_CHANNEL),
    (r"^how\??$", HumanLanguageIntent.APPLICATION_PROCESS),
    (r"^how\s+to\s+get\??$", HumanLanguageIntent.APPLICATION_PROCESS),
    (r"^how\s+can\s+i\s+get\s+it\??$", HumanLanguageIntent.APPLICATION_PROCESS),
    (r"^then\??$", HumanLanguageIntent.APPLICATION_PROCESS),
    (r"^next\??$", HumanLanguageIntent.APPLICATION_PROCESS),
    (r"^what\s+next\??$", HumanLanguageIntent.APPLICATION_PROCESS),
    (r"^when\??$", HumanLanguageIntent.GENERAL_INFORMATION),
    (r"^why\??$", HumanLanguageIntent.GENERAL_INFORMATION),
    (r"^what\s+about\s+documents\??$", HumanLanguageIntent.DOCUMENTS_REQUIRED),
    (r"^what\s+about\s+money\??$", HumanLanguageIntent.BENEFITS_AMOUNT),
    (r"^and\s+eligibility\??$", HumanLanguageIntent.ELIGIBILITY),
    (r"^benefits?\??$", HumanLanguageIntent.BENEFITS),
    (r"^nanage\s+idu\s+sigutta\??$", HumanLanguageIntent.PERSONAL_ELIGIBILITY),
    (r"^nanage\s+sigbeku\??$", HumanLanguageIntent.APPLICATION_PROCESS),
    (r"^idu\s+heg\s+sigutte\??$", HumanLanguageIntent.APPLICATION_PROCESS),
    (r"^idu\s+heg\s+mad\s*beku\??$", HumanLanguageIntent.APPLICATION_PROCESS),
    (r"^nan\s+en\s+madbeku\??$", HumanLanguageIntent.APPLICATION_PROCESS),
    (r"^enu\s+madbeku\??$", HumanLanguageIntent.APPLICATION_PROCESS),
    (r"^mujhe\s+milega\??$", HumanLanguageIntent.PERSONAL_ELIGIBILITY),
    (r"^mere\s+liye\??$", HumanLanguageIntent.PERSONAL_ELIGIBILITY),
    (r"^main\s+kya\s+karu\??$", HumanLanguageIntent.APPLICATION_PROCESS),
    (r"^ab\s+kya\s+karna\s+hai\??$", HumanLanguageIntent.APPLICATION_PROCESS),
)


def resolve_short_followup(
    text: str,
    *,
    active_scheme: Optional[str] = None,
) -> Tuple[Optional[HumanLanguageIntent], float]:
    """Map minimal follow-ups when a scheme/topic is already active."""
    raw = (text or "").strip()
    if not raw or not active_scheme:
        return None, 0.0
    lower = re.sub(r"\s+", " ", raw.lower()).strip()
    if len(lower.split()) > 8:
        return None, 0.0
    for pat, intent in _SHORT_INTENT:
        if re.search(pat, lower, re.I) or re.search(pat, raw, re.I):
            return intent, 0.75
    return None, 0.0
