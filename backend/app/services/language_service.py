"""Response-language resolution for GramSakhi (Phase 6.5 + Kannada quality).

Retrieval language and response language are separate concerns.
This module does NOT translate documents or redesign RAG.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from app.services.kannada_glossary import glossary_prompt_block

# ISO-like codes used in API / conversation storage
LANG_EN = "EN"
LANG_KN = "KN"
LANG_HI = "HI"

OP_NEW_INFORMATION = "NEW_INFORMATION_QUERY"
OP_ANSWER_IN_LANGUAGE = "ANSWER_IN_LANGUAGE_REQUEST"
OP_TRANSLATION = "TRANSLATION_REQUEST"

_CODE_TO_NAME = {
    LANG_EN: "English",
    LANG_KN: "Kannada",
    LANG_HI: "Hindi",
}

_NAME_TO_CODE = {
    "english": LANG_EN,
    "en": LANG_EN,
    "kannada": LANG_KN,
    "kn": LANG_KN,
    "kan": LANG_KN,
    "hindi": LANG_HI,
    "hi": LANG_HI,
    "hin": LANG_HI,
}


@dataclass
class LanguageDecision:
    detected_language: str
    response_language: str
    target_language: str
    is_translation_request: bool = False
    is_translation_only: bool = False
    strict_language_mode: bool = False
    operation: str = OP_NEW_INFORMATION
    reason: str = "default"


@dataclass
class PreviousAnswerTransform:
    """Transform prior assistant answer without a new RAG query."""

    apply: bool = False
    mode: str = "none"  # translate | rephrase
    target_language: Optional[str] = None


def language_name(code: Optional[str]) -> str:
    if not code:
        return "English"
    c = normalize_language_code(code) or LANG_EN
    return _CODE_TO_NAME.get(c, "English")


def normalize_language_code(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    upper = raw.upper()
    if upper in (LANG_EN, LANG_KN, LANG_HI):
        return upper
    return _NAME_TO_CODE.get(raw.lower())


def detect_script_language(text: str) -> Optional[str]:
    """Detect language from Unicode script of the original user message."""
    sample = text or ""
    kn = sum(1 for ch in sample if "\u0c80" <= ch <= "\u0cff")
    hi = sum(1 for ch in sample if "\u0900" <= ch <= "\u097f")
    if kn >= 2 and kn >= hi:
        return LANG_KN
    if hi >= 2 and hi > kn:
        return LANG_HI
    return None


# Latin tokens that are entities, not English-language evidence.
_ENTITY_LATIN = re.compile(
    r"\b("
    r"pm-?kisan|pmkisan|pmfby|pmay-?g?|pmsby|mgnrega|mgnregs|kcc|"
    r"aadhaar|aadhar|otp|ifsc|dbt|nsap|nrega|"
    r"gruha\s*lakshmi|gruhalakshmi|gruha\s*jyoti|guruha\s*jyoti|"
    r"anna\s*bhagya|ayushman|karnataka|india"
    r")\b",
    re.IGNORECASE,
)

_EN_QUESTION = re.compile(
    r"\b(what|who|when|where|how|which|why|whose|whom)\b",
    re.IGNORECASE,
)
_EN_LEXICAL = re.compile(
    r"\b("
    r"what|who|when|where|how|which|why|eligibility|eligible|benefit|benefits|"
    r"document|documents|apply|application|required|requirement|deadline|"
    r"amount|installment|criteria|please|explain|tell|about|scheme|schemes|"
    r"needed|need|can|does|is|are|the|for|of|and|with|from"
    r")\b",
    re.IGNORECASE,
)

# Citizen-style Kannada / Hindi Latin transliteration (not English).
# Strong tokens alone can decide; weak tokens need company.
_KN_LATIN_STRONG = re.compile(
    r"\b("
    r"hegidira|hegiddira|yojaneke|yojanage|yaaru|yaru|arharu|arhru|arharige|"
    r"ellaru|hege|eshtu|sigutte|siguttade|heli|helu|bagge|"
    r"arhate|arhathe|mahiti|maahiti|madtira|madtiira|"
    r"kannadadalli|kannadakke"
    r")\b",
    re.IGNORECASE,
)
_KN_LATIN_WEAK = re.compile(
    r"\b(yojane|enu|yenu|beku|hakki|kodi|yojana)\b",
    re.IGNORECASE,
)
_HI_LATIN_STRONG = re.compile(
    r"\b("
    r"kaun|koun|patra|patrata|kitna|kaise|milega|milta|chahiye|"
    r"batao|bataiye|bataye|ke\s*liye"
    r")\b",
    re.IGNORECASE,
)
_HI_LATIN_WEAK = re.compile(
    r"\b(yojana|kya|hai|kab|mein|me)\b",
    re.IGNORECASE,
)


def _latin_indic_transliteration(text: str) -> Optional[str]:
    """Detect KN/HI intent from Latin transliteration; None if ambiguous."""
    cleaned = text or ""
    kn_s = len(_KN_LATIN_STRONG.findall(cleaned))
    kn_w = len(_KN_LATIN_WEAK.findall(cleaned))
    hi_s = len(_HI_LATIN_STRONG.findall(cleaned))
    hi_w = len(_HI_LATIN_WEAK.findall(cleaned))
    kn_score = kn_s * 2 + kn_w
    hi_score = hi_s * 2 + hi_w
    if kn_s >= 1 or kn_score >= 2:
        if hi_score > kn_score and hi_s >= 1:
            return LANG_HI
        return LANG_KN
    if hi_s >= 1 or hi_score >= 2:
        return LANG_HI
    return None


def detect_lexical_language(text: str) -> Optional[str]:
    """
    Latin-script lexical cues for the CURRENT message.
    Scheme names alone must not force English.
    Transliterated Kannada/Hindi must not be treated as English.
    """
    script = detect_script_language(text)
    if script:
        return script
    raw = text or ""
    # Mixed script already handled above; for Latin+script leftover use script path.
    if any(ord(c) > 127 for c in raw):
        return None
    cleaned = _ENTITY_LATIN.sub(" ", raw)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return None

    indic = _latin_indic_transliteration(cleaned)
    en_q = bool(_EN_QUESTION.search(cleaned))
    en_hits = _EN_LEXICAL.findall(cleaned)

    # Clear English question structure wins over weak transliteration noise.
    if en_q and not indic:
        return LANG_EN
    if en_q and indic:
        # "who is eligible" style English beats a lone shared token like yojana;
        # strong KN/HI transliteration still wins (voice Latin Kannada).
        if indic == LANG_KN and _KN_LATIN_STRONG.search(cleaned):
            return LANG_KN
        if indic == LANG_HI and _HI_LATIN_STRONG.search(cleaned):
            return LANG_HI
        return LANG_EN
    if indic:
        return indic
    if len(en_hits) >= 2:
        return LANG_EN
    return None


def detect_strict_language_mode(text: str) -> bool:
    t = text or ""
    low = t.lower()
    if re.search(r"\b(only in|entirely in|strictly in)\s+kannada\b", low):
        return True
    if re.search(r"\banswer only in kannada\b", low):
        return True
    if "\u0c95\u0ca8\u0ccd\u0ca8\u0ca1\u0ca6\u0cb2\u0ccd\u0cb2\u0cbf \u0cae\u0cbe\u0ca4\u0ccd\u0cb0" in t:
        return True
    if "\u0c95\u0ca8\u0ccd\u0ca8\u0ca1\u0ca6\u0cb2\u0ccd\u0cb2\u0cbf \u0cae\u0cbe\u0ca4\u0ccd\u0cb0 \u0c89\u0ca4\u0ccd\u0ca4\u0cb0\u0cbf\u0cb8\u0cbf" in t:
        return True
    return False


def _has_explicit_language_request(text: str) -> Optional[str]:
    """Parse 'answer in Kannada' / Kannada script cues / transliteration."""
    t = (text or "").strip()
    low = t.lower()

    if re.search(r"\bkannada\s+please\b", low) or re.search(r"\bplease\s+kannada\b", low):
        return LANG_KN
    if re.search(r"\bhindi\s+please\b", low) or re.search(r"\bplease\s+hindi\b", low):
        return LANG_HI
    if re.search(r"\benglish\s+please\b", low) or re.search(r"\bplease\s+english\b", low):
        return LANG_EN
    if re.search(r"\b(in|into|to)\s+kannada\b", low) or re.search(
        r"\b(answer|reply|respond|tell|explain|give|translate|please).{0,40}\bkannada\b",
        low,
    ):
        return LANG_KN
    if re.search(r"\b(in|into|to)\s+hindi\b", low) or re.search(
        r"\b(answer|reply|respond|tell|explain|give|translate|please).{0,40}\bhindi\b",
        low,
    ):
        return LANG_HI
    if re.search(r"\b(in|into|to)\s+english\b", low) or re.search(
        r"\b(answer|reply|respond|tell|explain|give|translate|please).{0,40}\benglish\b",
        low,
    ):
        return LANG_EN

    # Transliteration variants
    if re.search(
        r"\b(kannadadalli|kannada\s*dalli|kannadakke|kannada\s*alli|"
        r"kannada\s*dalli\s*answer|kannadadalli\s*answer)\b",
        low,
    ) or re.search(
        r"\bkannada\s*(heli|helu|mad(i|u)|translate|answer\s*kodi|alli)\b", low
    ):
        return LANG_KN
    if re.search(r"\b(hindi\s*mein|hindimein|hindi\s*me)\b", low) or re.search(
        r"\bhindi\s*(batao|bataiye|mein\s+batao)\b", low
    ):
        return LANG_HI

    if "\u0c95\u0ca8\u0ccd\u0ca8\u0ca1" in t:
        return LANG_KN
    if "\u0939\u093f\u0902\u0926\u0940" in t or "\u0939\u093f\u0928\u094d\u0926\u0940" in t:
        if any(
            x in t
            for x in (
                "\u092e\u0947\u0902",
                "\u0905\u0928\u0941\u0935\u093e\u0926",
                "\u092c\u0924\u093e\u0913",
                "\u092c\u0924\u093e\u0907\u090f",
                "\u0939\u093f\u0902\u0926\u0940",
                "\u0939\u093f\u0928\u094d\u0926\u0940",
            )
        ):
            return LANG_HI

    return None


def detect_translation_intent(text: str) -> Tuple[bool, bool, Optional[str]]:
    """
    Returns (is_translation_request, is_translation_only, target_language).

    translation_only means: do not run RAG/live — translate previous answer.
    """
    t = (text or "").strip()
    if not t:
        return False, False, None
    low = t.lower()

    target = _has_explicit_language_request(t)
    if target and len(t.split()) <= 8:
        factual = re.search(
            r"\b(eligibility|benefit|benefits|document|documents|apply|application|"
            r"scheme|yojana|criteria|procedure|amount|deadline|money)\b",
            low,
        )
        if not factual and re.search(r"\b(please|dalli|heli|mein|batao|bataiye)\b", low + t):
            return True, True, target
    if target and len(t.split()) <= 12:
        factual = re.search(
            r"\b(eligibility|benefit|benefits|document|documents|apply|application|"
            r"scheme|yojana|criteria|procedure|amount|deadline|money)\b",
            low,
        )
        if not factual and re.search(
            r"\b(tell me|explain|say)\b.{0,30}\b(in|into|mein|dalli)\b", low
        ):
            return True, True, target
    same_lang = re.search(
        r"\bsame thing in (kannada|hindi|english)\b",
        low,
    )
    if same_lang:
        word = same_lang.group(1)
        mapping = {"kannada": LANG_KN, "hindi": LANG_HI, "english": LANG_EN}
        return True, True, mapping.get(word)

    translate_markers_en = (
        r"\btranslate\b",
        r"\btranslation\b",
        r"\bgive the above\b",
        r"\babove (answer|information|response)\b",
        r"\bprevious (answer|response)\b",
        r"\bthis answer\b",
        r"\bthe above\b",
    )
    translate_markers_kn = (
        "\u0c85\u0ca8\u0cc1\u0cb5\u0cbe\u0ca6",
        "\u0cae\u0cc7\u0cb2\u0cbf\u0ca8",
        "\u0c87\u0ca6\u0ca8\u0ccd\u0ca8\u0cc1",
        "\u0cae\u0cc7\u0cb2\u0cbf\u0ca8 \u0cae\u0cbe\u0cb9\u0cbf\u0ca4\u0cbf",
        "\u0cae\u0cc7\u0cb2\u0cbf\u0ca8 \u0c89\u0ca4\u0ccd\u0ca4\u0cb0",
    )
    translate_markers_hi = (
        "\u0905\u0928\u0941\u0935\u093e\u0926",
        "\u090a\u092a\u0930 \u0915\u0940",
        "\u0909\u092a\u0930\u094b\u0915\u094d\u0924",
        "\u092a\u093f\u091b\u0932\u093e \u0909\u0924\u094d\u0924\u0930",
        "\u0907\u0938 \u0909\u0924\u094d\u0924\u0930",
    )
    translit = (
        r"\bidannu\b",
        r"\bmeln(a|ina)\b",
        r"\btranslate\s*madi\b",
        r"\bkannadakke\s*translate\b",
    )

    looks_translate = any(re.search(p, low) for p in translate_markers_en)
    looks_translate = looks_translate or any(m in t for m in translate_markers_kn)
    looks_translate = looks_translate or any(m in t for m in translate_markers_hi)
    looks_translate = looks_translate or any(re.search(p, low) for p in translit)

    if not looks_translate and not (
        target
        and re.search(
            r"\b(above|previous|this answer|\u0cae\u0cc7\u0cb2\u0cbf\u0ca8|\u0c87\u0ca6\u0ca8\u0ccd\u0ca8\u0cc1|\u090a\u092a\u0930)\b",
            low + t,
        )
    ):
        return False, False, target

    if not target:
        target = None

    factual_en = re.search(
        r"\b(eligibility|benefit|benefits|document|documents|apply|application|"
        r"scheme|yojana|criteria|procedure|refund|grievance)\b",
        low,
    )
    factual_native = any(
        tok in t
        for tok in (
            "\u0c85\u0cb0\u0ccd\u0cb9\u0ca4\u0cc6",
            "\u0caa\u0ccd\u0cb0\u0caf\u0ccb\u0c9c\u0ca8",
            "\u0caf\u0ccb\u0c9c\u0ca8\u0cc6",
            "\u0ca6\u0cbe\u0c96\u0cb2\u0cc6",
            "\u092a\u093e\u0924\u094d\u0930\u0924\u093e",
            "\u0932\u093e\u092d",
            "\u092f\u094b\u091c\u0928\u093e",
            "\u0926\u0938\u094d\u0924\u093e\u0935\u0947\u091c",
        )
    )
    has_factual = bool(factual_en or factual_native)
    short = len(t) < 120
    only = looks_translate and short and not (
        has_factual
        and not re.search(
            r"\b(above|previous|this answer|\u0cae\u0cc7\u0cb2\u0cbf\u0ca8|\u0c87\u0ca6\u0ca8\u0ccd\u0ca8\u0cc1|\u090a\u092a\u0930)\b",
            low + t,
        )
    )
    if looks_translate and re.search(
        r"\b(above|previous|this answer|\u0cae\u0cc7\u0cb2\u0cbf\u0ca8|\u0c87\u0ca6\u0ca8\u0ccd\u0ca8\u0cc1|\u090a\u092a\u0930 \u0915\u0940|\u0905\u0928\u0941\u0935\u093e\u0926)\b",
        low + t,
    ):
        only = True

    return True, bool(only), target


_REPHRASE_PREVIOUS_ANSWER_RE = re.compile(
    r"(?:"
    r"\bexplain again\b"
    r"|\bsay that again\b"
    r"|\brepeat that\b"
    r"|\bshort answer\b"
    r"|\bmake it easier\b"
    r"|\bmake it simple\b"
    r"|\bi don't understand\b"
    r"|\bi do not understand\b"
    r"|\bsay that simply\b"
    r"|\btell me simply\b"
    r"|\bexplain\s+(?:that|it|this)\s+simply\b"
    r"|\bexplain\s+simply\b"
    r"|\bexplain\s+(?:that\s+)?in simple words\b"
    r"|\bi don't understand,?\s*explain\s+simply\b"
    r")"
)


def detect_previous_answer_transform(
    text: str,
    *,
    conversation_language: Optional[str] = None,
) -> PreviousAnswerTransform:
    """Conversation operations on the prior assistant answer (no new RAG)."""
    is_tr, only, target = detect_translation_intent(text)
    if is_tr and only:
        tgt = target or normalize_language_code(conversation_language) or LANG_EN
        return PreviousAnswerTransform(True, "translate", tgt)

    low = (text or "").strip().lower()
    if not low:
        return PreviousAnswerTransform()

    rephrase = _REPHRASE_PREVIOUS_ANSWER_RE.search(low)
    if rephrase and len(low) < 160:
        code = normalize_language_code(conversation_language) or LANG_EN
        return PreviousAnswerTransform(True, "rephrase", code)

    return PreviousAnswerTransform()


def resolve_response_language(
    original_query: str,
    *,
    request_language: Optional[str] = None,
    conversation_language: Optional[str] = None,
    stt_language: Optional[str] = None,
    previous_response_language: Optional[str] = None,
) -> LanguageDecision:
    """
    Canonical per-MESSAGE language resolution (text + voice).

    Priority:
      1. Explicit language / translation instruction in CURRENT message
      2. Clear translation instruction (via detect_translation_intent)
      3. Strong Unicode/script evidence in CURRENT message
      4. Strong CURRENT-message lexical / transliteration signal
      5. Reliable STT language (never overrides strong current lexical)
      6. Conversation last-language (preference/fallback only)
      7. Previous response language (fallback only)
      8. Weak UI/API preference
      9. Default EN

    Rewritten retrieval queries must NEVER be passed here.
    Conversation language must NEVER override strong current-message evidence.
    """
    text = original_query or ""
    is_tr, only_tr, tr_target = detect_translation_intent(text)
    explicit = tr_target or _has_explicit_language_request(text)
    script = detect_script_language(text)
    lexical = detect_lexical_language(text)
    stt = normalize_language_code(stt_language)
    req = normalize_language_code(request_language)
    conv = normalize_language_code(conversation_language)
    prev = normalize_language_code(previous_response_language)
    strict = detect_strict_language_mode(text)

    if only_tr:
        op = OP_TRANSLATION
    elif explicit and not only_tr:
        op = OP_ANSWER_IN_LANGUAGE
    else:
        op = OP_NEW_INFORMATION

    def _dec(code: str, reason: str, detected: Optional[str] = None) -> LanguageDecision:
        return LanguageDecision(
            detected_language=detected or script or lexical or stt or code,
            response_language=code,
            target_language=code,
            is_translation_request=is_tr,
            is_translation_only=only_tr,
            strict_language_mode=strict,
            operation=op,
            reason=reason,
        )

    if explicit:
        return _dec(explicit, "explicit_request", detected=script or stt or explicit)

    if script:
        return _dec(script, "detected_script", detected=script)

    # Current-message lexical/transliteration beats sticky conversation AND Whisper.
    if lexical == LANG_EN:
        return _dec(LANG_EN, "lexical_english", detected=LANG_EN)
    if lexical in (LANG_KN, LANG_HI):
        return _dec(lexical, "lexical_transliteration", detected=lexical)

    if stt:
        return _dec(stt, "stt_language", detected=stt)

    if conv:
        return _dec(conv, "conversation_language", detected=conv)

    if prev:
        return _dec(prev, "previous_response_language", detected=prev)

    if req:
        return _dec(req, "request_language", detected=req)

    return _dec(LANG_EN, "default_en", detected=LANG_EN)


def build_language_instruction(
    response_language: str,
    *,
    strict_language_mode: bool = False,
) -> str:
    name = language_name(response_language)
    code = normalize_language_code(response_language) or LANG_EN
    parts = [
        f"TARGET_RESPONSE_LANGUAGE: {code}",
        f"TARGET_LANGUAGE_NAME: {name}",
        f"LANGUAGE: {name}",
        f"Respond entirely in natural {name}.",
        "Use the provided evidence as the factual source.",
        "Do not add unsupported information.",
        "Do not change numbers, dates, amounts, eligibility criteria, "
        "scheme names, government department names, or URLs.",
        "Do not change negations (not eligible / cannot apply) or AND/OR conditions.",
        f"The source evidence may be in English or another language. "
        f"Translate the factual content into {name} while preserving the exact meaning.",
        f"Do not switch to English merely because the evidence is written in English."
        if code != LANG_EN
        else "Answer in clear English.",
        "English technical or official terms may be retained when necessary "
        f"(PM-KISAN, Aadhaar, OTP, URLs), but the surrounding explanation must be {name}."
        if code != LANG_EN
        else "Preserve official scheme names and URLs unchanged.",
        "Prefer simple citizen-friendly wording. Do not invent facts while simplifying.",
        "Preserve Source / Page / URL lines when present in evidence.",
    ]
    if code == LANG_KN:
        gloss = glossary_prompt_block(LANG_KN)
        if gloss:
            parts.append(gloss)
    if strict_language_mode:
        parts.append(
            f"STRICT LANGUAGE MODE: No explanatory sentences in any language other than {name}. "
            "Official names, abbreviations, numbers, and URLs may remain unchanged."
        )
    return "\n".join(parts)


def build_rephrase_prompt(
    previous_answer: str,
    *,
    response_language: str,
    regen_note: Optional[str] = None,
) -> str:
    name = language_name(response_language)
    code = normalize_language_code(response_language) or LANG_EN
    parts = [
        f"You are GramSakhi. Rephrase the previous answer in simpler, clearer {name}.",
        "",
        "Rules:",
        "1. Keep every fact, number, date, amount, eligibility rule, document name, and URL.",
        "2. Do not add or remove facts.",
        "3. Use shorter sentences where helpful.",
        f"4. Return only the rephrased answer in {name} ({code}).",
        "",
    ]
    if regen_note:
        parts.extend([regen_note, ""])
    parts.extend(
        [
            "PREVIOUS ANSWER:",
            (previous_answer or "").strip(),
            "",
            f"Provide the simplified {name} answer only.",
        ]
    )
    return "\n".join(parts)


def build_translation_prompt(
    previous_answer: str,
    *,
    target_language: str,
    regen_note: Optional[str] = None,
) -> str:
    name = language_name(target_language)
    code = normalize_language_code(target_language) or LANG_EN
    parts = [
        f"You are GramSakhi. Translate the provided answer into natural {name}.",
        "",
        "Rules:",
        "1. Do not add facts.",
        "2. Do not remove facts.",
        "3. Do not summarize.",
        "4. Do not reinterpret.",
        "5. Preserve numbers, dates, amounts, names, conditions, source information and URLs.",
        "6. Preserve negations and AND/OR meaning.",
        f"7. Return only the translated answer in {name} ({code}).",
        "",
    ]
    if regen_note:
        parts.extend([regen_note, ""])
    if code == LANG_KN:
        gloss = glossary_prompt_block(LANG_KN)
        if gloss:
            parts.extend([gloss, ""])
    parts.extend(
        [
            "ANSWER TO TRANSLATE:",
            (previous_answer or "").strip(),
            "",
            f"Provide the {name} translation only.",
        ]
    )
    return "\n".join(parts)


def controlled_language_failure_message(response_language: str, *, kind: str = "generation") -> str:
    code = normalize_language_code(response_language) or LANG_EN
    if kind == "translation":
        return {
            LANG_KN: (
                "\u0ca8\u0cbe\u0ca8\u0cc1 \u0c88\u0c97 \u0c85\u0ca8\u0cc1\u0cb5\u0cbe\u0ca6\u0cb5\u0ca8\u0ccd\u0ca8\u0cc1 "
                "\u0ca8\u0cbf\u0cb0\u0ccd\u0cad\u0cb0\u0cb5\u0cbe\u0c97\u0cbf \u0caa\u0cc2\u0cb0\u0cc8\u0cb8\u0cb2\u0cc1 "
                "\u0cb8\u0cbe\u0ca7\u0ccd\u0caf\u0cb5\u0cbe\u0c97\u0cb2\u0cbf\u0cb2\u0ccd\u0cb2. "
                "\u0ca6\u0caf\u0cb5\u0cbf\u0c9f\u0ccd\u0c9f\u0cc1 \u0cb8\u0ccd\u0cb5\u0cb2\u0ccd\u0caa \u0caa\u0ccd\u0cb0\u0caf\u0ca4\u0ccd\u0ca8\u0cbf\u0cb8\u0cbf."
            ),
            LANG_HI: (
                "\u092e\u0948\u0902 \u0905\u092d\u0940 \u0905\u0928\u0941\u0935\u093e\u0926 \u0935\u093f\u0936\u094d\u0935\u0938\u0928\u0940\u092f "
                "\u0938\u0947 \u092a\u0942\u0930\u093e \u0928\u0939\u0940\u0902 \u0915\u0930 \u0938\u0915\u093e/\u0938\u0915\u0940. "
                "\u0915\u0943\u092a\u092f\u093e \u0915\u0941\u091b \u0926\u0947\u0930 \u092c\u093e\u0926 \u092a\u0941\u0928\u0903 \u092a\u094d\u0930\u092f\u093e\u0938 \u0915\u0930\u0947\u0902."
            ),
            LANG_EN: (
                "I could not reliably complete the translation right now. "
                "Please try again shortly."
            ),
        }.get(code, "I could not reliably complete the translation right now.")
    return {
        LANG_KN: (
            "\u0c88 \u0cae\u0cbe\u0cb9\u0cbf\u0ca4\u0cbf\u0c97\u0cc6 \u0c88\u0c97 \u0cb5\u0cbf\u0cb6\u0ccd\u0cb5\u0cbe\u0cb8\u0cbe\u0cb0\u0ccd\u0cb9 "
            "\u0c89\u0ca4\u0ccd\u0ca4\u0cb0\u0cb5\u0ca8\u0ccd\u0ca8\u0cc1 \u0cb0\u0c9a\u0cbf\u0cb8\u0cb2\u0cc1 "
            "\u0cb8\u0cbe\u0ca7\u0ccd\u0caf\u0cb5\u0cbe\u0c97\u0cb2\u0cbf\u0cb2\u0ccd\u0cb2. "
            "\u0ca6\u0caf\u0cb5\u0cbf\u0c9f\u0ccd\u0c9f\u0cc1 \u0cae\u0ca4\u0ccd\u0ca4\u0cc6 \u0caa\u0ccd\u0cb0\u0caf\u0ca4\u0ccd\u0ca8\u0cbf\u0cb8\u0cbf."
        ),
        LANG_HI: (
            "\u0907\u0938 \u091c\u093e\u0928\u0915\u093e\u0930\u0940 \u0915\u0947 \u0932\u093f\u090f \u0905\u092d\u0940 "
            "\u0935\u093f\u0936\u094d\u0935\u0938\u0928\u0940\u092f \u0909\u0924\u094d\u0924\u0930 \u0924\u0948\u092f\u093e\u0930 "
            "\u0928\u0939\u0940\u0902 \u0915\u093f\u092f\u093e \u091c\u093e \u0938\u0915\u093e. "
            "\u0915\u0943\u092a\u092f\u093e \u092b\u093f\u0930 \u0938\u0947 \u092a\u094d\u0930\u092f\u093e\u0938 \u0915\u0930\u0947\u0902\u0964"
        ),
        LANG_EN: (
            "I couldn't generate a verified answer right now. "
            "Please try again."
        ),
    }.get(code, "I couldn't generate a verified answer right now. Please try again.")


def language_metadata(decision: LanguageDecision) -> Dict[str, Any]:
    return {
        "detected_language": decision.detected_language,
        "response_language": decision.response_language,
        "target_language": decision.target_language,
        "is_translation_request": decision.is_translation_request,
        "is_translation_only": decision.is_translation_only,
        "strict_language_mode": decision.strict_language_mode,
        "language_operation": decision.operation,
        "language_reason": decision.reason,
    }
