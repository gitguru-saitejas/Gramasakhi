"""Multilingual intent patterns (regex + phrase cues, ordered by specificity)."""

from __future__ import annotations

import re
from typing import Iterable, Optional, Tuple

from app.services.human_language.intent_models import HumanLanguageIntent

# (intent, patterns) — first match wins
_RULES: Tuple[Tuple[HumanLanguageIntent, Tuple[str, ...]], ...] = (
    (
        HumanLanguageIntent.STATUS,
        (
            r"\bapplication status\b",
            r"\bstatus of my application\b",
            r"\bcheck my application\b",
            r"\bhas my application\b",
            r"\bapproved\b.*\bapplication\b",
            r"\bdid they approve\b",
            r"\bhas it come\b",
            r"\bwhere is my application\b",
            r"\bcan i check\b",
            r"\btrack(ing)?\b.*\bapplication\b",
            r"ಸ್ಥಿತಿ",
            r"अनुप्रयोग.*स्थिति",
            r"आवेदन.*स्थिति",
        ),
    ),
    (
        HumanLanguageIntent.APPLICATION_PROCESS,
        (
            r"\bhow (can|do|should) i apply\b",
            r"\bwhat should i do\b",
            r"\bi want (this|to apply|this benefit)\b",
            r"\bi need this\b",
            r"\bhow (can|do) i get (this|it|the scheme|the benefit)\b",
            r"\biske liye kya karna\b",
            r"\biske liye kya kar",
            r"\bab kya karna\b",
            r"\bmain kya karu\b",
            r"\bhow (can|do) i (avail|receive|take)\b",
            r"\bhow do i (register|enroll|avail)\b",
            r"\bapplication process\b",
            r"\bwhat is the process\b",
            r"\bwhere do i start\b",
            r"\bi want to apply\b",
            r"\bapply kaise\b",
            r"\bapply hege\b",
            r"\bapply hege mad",
            r"\bidu\s+heg\s+mad\s*beku\b",
            r"\benu\s+madbeku\b",
            r"\bnan\s+en\s+madbeku\b",
            r"\biske liye apply\b",
            r"\bidakke apply\b",
            r"\bಅರ್ಜಿ\b.*\b(ಹಾಕ|ಮಾಡ|ಸಲ್ಲಿಸ)\b",
            r"ಅರ್ಜಿ\s*ಹಾಕ",
            r"ಅರ್ಜಿ\s*ಹಾಕಬೇಕು",
            r"\bಇದನ್ನು\b.*\b(ಪಡೆ|ಸಿಗ)\b",
            r"ಇದನ್ನು\s*ಪಡೆಯ",
            r"ಪಡೆಯ.*ಹೇಗೆ",
            r"ಇದನ್ನು.*ಹೇಗೆ",
            r"\bआवेदन\b.*\b(कैसे|करूं|करें)\b",
            r"आवेदन\s*कैसे",
            r"इसके\s*लिए\s*आवेदन",
            r"इसके\s*लिए\s*क्या\s*कर",
            r"\bइसे\b.*\b(कैसे|मिल)\b",
            r"इसे\s*कैसे\s*मिल",
            "इसके लिए आवेदन कैसे करूं",
            r"कहाँ\s*जाना",
            "ಅರ್ಜಿ ಹೇಗೆ ಹಾಕಬೇಕು",
        ),
    ),
    (
        HumanLanguageIntent.APPLICATION_CHANNEL,
        (
            r"\bwhere (can|do|should) i (apply|go)\b",
            r"\bwhere should i go\b",
            r"\bwhere to apply\b",
            r"\bwhere can i get it\b",
            r"\bkahan jana\b",
            r"\bwhere hogbeku\b",
            r"\bwhich (office|website|portal)\b",
            r"\bapply online\b",
            r"\bcan i apply online\b",
            r"\bcan i do it online\b",
            r"\bwhich portal\b",
            r"\bofficial (website|portal|link)\b",
            r"\bwhich website\b",
            r"\bಕೋ office\b",
            r"\bಎಲ್ಲಿ\b.*\b(ಅರ್ಜಿ|apply)\b",
            r"\bकहाँ\b.*\b(आवेदन|apply)\b",
            r"\bkaha.*apply\b",
        ),
    ),
    (
        HumanLanguageIntent.PERSONAL_ELIGIBILITY,
        (
            r"\bam i eligible\b",
            r"\bcan i get (this|it|the scheme|the benefit)\b",
            r"\bwill i get (this|it)\b",
            r"\bis this for me\b",
            r"\bcan my (mother|father|wife|husband|daughter|son)\b",
            r"\bcan i apply for (this|it)\b",
            r"\bmujhe ye milega\b",
            r"\bmujhe milega\b",
            r"\bmere liye hai\b",
            r"\bdo i qualify\b",
            r"\bam i qualified\b",
            r"\beligible for me\b",
            r"\bavailable for me\b",
            r"\bcan i get this benefit\b",
            r"\bमैं.*पात्र\b",
            r"\bक्या मैं.*पात्र\b",
            r"\bमुझे.*मिल\b",
            r"\bमैं\b.*\bपात्र\b",
            r"\bपात्र\s*हूं\b",
            r"\bnanige.*sig",
            r"\bನಾನು.*ಅರ್ಹ",
            r"\bnanige idu sig",
            r"\bidakke.*nanu.*arh",
        ),
    ),
    (
        HumanLanguageIntent.BENEFITS_AMOUNT,
        (
            r"\bhow much\b",
            r"\bwhat is the amount\b",
            r"\bhow much money\b",
            r"\bhow much will i (get|receive)\b",
            r"\bkitne paise\b",
            r"\bkitna paisa\b",
            r"\bकितने पैसे\b",
            r"\bकितना\b.*\b(राशि|पैस|मिल)\b",
            r"\bಎಷ್ಟು\b",
            r"\bಎಷ್ಟು ಹಣ\b",
            r"\bhow much amount\b",
            r"\bsigutte\b.*\b(hana|amount|money)\b",
        ),
    ),
    (
        HumanLanguageIntent.DOCUMENTS_REQUIRED,
        (
            r"\bwhat (papers|documents)\b",
            r"\bwhich (papers|documents)\b",
            r"\bdocuments (required|needed)\b",
            r"\brequired documents\b",
            r"\bwhat proof\b",
            r"\bwhat should i (take|submit|bring)\b",
            r"\bwhat all should i submit\b",
            r"\bwhich papers should i submit\b",
            r"\bkaunse kagaz\b",
            r"\bdocuments yenu\b",
            r"\byenu beku\b.*\bdocument",
            r"\bದಾಖಲ",
            r"\bकागज\b",
            r"\bदस्तावेज\b",
            r"\bकौन से कागज\b",
        ),
    ),
    (
        HumanLanguageIntent.SCHEME_DISCOVERY,
        (
            r"\bwhich schemes\b",
            r"\blist (of )?schemes\b",
            r"\bwhat schemes\b",
            r"\bschemes available\b",
            r"\bfind a scheme\b",
            r"\bhelp me find\b.*\bscheme\b",
            r"\bಯಾವ ಯೋಜನೆ\b",
            r"\bकौन\s*सी\s*योजना\b",
        ),
    ),
    (
        HumanLanguageIntent.ELIGIBILITY,
        (
            r"\bwho is eligible\b",
            r"\bwho can apply\b",
            r"\bwho can get\b",
            r"\beligibility criteria\b",
            r"\beligibility rules\b",
            r"\bqualification\b",
            r"\bcan people apply\b",
            r"\bयारु\b.*\bअर्ह\b",
            r"\bयार\b.*\bअर्ह\b",
            r"\bयारु\b.*\barh\b",
            r"\bkaun eligible\b",
            r"\bkaun patra\b",
            r"\bकौन पात्र\b",
            r"\bपात्रता\b",
            r"\bಅರ್ಹ\b",
            r"\bಯಾರು\b.*\bಅರ್ಹ\b",
        ),
    ),
    (
        HumanLanguageIntent.BENEFITS,
        (
            r"\bwhat (do i get|will i receive|is the benefit)\b",
            r"\bwhat does this scheme give\b",
            r"\bwhat are the benefits\b",
            r"\bbenefits?\b",
            r"\bsubsidy\b",
            r"\bfinancial assistance\b",
            r"\bಲಾಭ\b",
            r"\bप्रयोजन\b|\bलाभ\b",
            r"\bscheme give\b",
        ),
    ),
    (
        HumanLanguageIntent.GENERAL_INFORMATION,
        (
            r"\btell me about\b",
            r"\bwhat is\b",
            r"\bwhat are\b",
            r"\binformation about\b",
            r"\bdetails about\b",
            r"\babout (this|the) scheme\b",
            r"\boverview\b",
            r"\bಯೋಜನೆ\b.*\b(ಬಗ್ಗೆ|ಹೇಳ)\b",
            r"\bयोजना\b.*\b(के बारे|बताओ)\b",
        ),
    ),
)

_SHORT_AMBIGUOUS = re.compile(
    r"^(yes|no|okay|ok|help|that one|tell me|need help)\.?$",
    re.I,
)


def _match_rules(text: str, lower: str) -> Optional[HumanLanguageIntent]:
    for intent, patterns in _RULES:
        for pat in patterns:
            use_regex = (
                pat.startswith(r"\b")
                or pat.startswith("(")
                or any(ord(c) > 127 for c in pat)
                or "\\" in pat
            )
            if use_regex:
                if re.search(pat, lower, re.I) or re.search(pat, text, re.I):
                    return intent
            elif pat.lower() in lower or pat in text:
                return intent
    return None


def classify_from_patterns(text: str) -> Tuple[HumanLanguageIntent, float]:
    raw = (text or "").strip()
    if not raw:
        return HumanLanguageIntent.UNKNOWN, 0.0
    lower = raw.lower()
    if _SHORT_AMBIGUOUS.match(lower):
        return HumanLanguageIntent.UNKNOWN, 0.0
    hit = _match_rules(raw, lower)
    if hit:
        return hit, 0.85
    return HumanLanguageIntent.UNKNOWN, 0.0


def followup_application_cues(text: str) -> bool:
    """Short follow-ups that imply application/process without explicit markers."""
    lower = (text or "").lower()
    cues: Iterable[str] = (
        "how can i get",
        "how do i get",
        "how to get",
        "apply",
        "register",
        "enroll",
        "avail",
        "process",
        "start",
        "next step",
    )
    return any(c in lower for c in cues) and len(lower.split()) <= 12
