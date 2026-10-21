"""Language-aware factual keyphrase evaluation (benchmark v2)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence

from evaluation.metrics.v2.normalize import (
    is_primarily_numeric_phrase,
    normalize_numeric_expression,
    normalize_text_for_language,
)

# Spelled-out number words derivable from ground-truth facts (English prose only).
_NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
    "thousand": 1000,
    "lakh": 100000,
    "crore": 10000000,
}


def _word_number_variants(facts: Sequence[str]) -> List[float]:
    values: set[float] = set()
    for fact in facts or []:
        blob = normalize_text_for_language(str(fact), "en")
        values.update(normalize_numeric_expression(blob))
        tokens = re.findall(r"[a-z]+", blob)
        for idx, token in enumerate(tokens):
            if token in _NUMBER_WORDS and token in ("two", "twenty", "thousand"):
                # Handle simple compounds like "two thousand".
                if token == "two" and idx + 1 < len(tokens) and tokens[idx + 1] == "thousand":
                    values.add(2000.0)
                if token == "twenty" and idx + 1 < len(tokens) and tokens[idx + 1] == "thousand":
                    values.add(20000.0)
    return sorted(values)


def _numeric_match(phrase: str, answer: str, language: str, facts: Sequence[str]) -> bool:
    phrase_values = normalize_numeric_expression(phrase)
    if not phrase_values:
        return False
    answer_values = set(normalize_numeric_expression(answer))
    answer_values.update(_word_number_variants(facts))
    return any(pv in answer_values for pv in phrase_values)


def _exact_match(phrase: str, answer: str, language: str) -> bool:
    return normalize_text_for_language(phrase, language) in normalize_text_for_language(answer, language)


def _normalized_match(phrase: str, answer: str, language: str) -> bool:
    # Punctuation-insensitive substring for non-numeric phrases.
    p = re.sub(r"[^\w\s]", " ", normalize_text_for_language(phrase, language))
    a = re.sub(r"[^\w\s]", " ", normalize_text_for_language(answer, language))
    p = re.sub(r"\s+", " ", p).strip()
    return bool(p) and p in a


def match_keyphrase_multilingual(
    answer: str,
    phrases: Sequence[str],
    *,
    language: str = "en",
    facts: Sequence[str] = (),
) -> Dict[str, Any]:
    """Deterministic multilingual keyphrase evaluation hierarchy."""
    if not phrases:
        return {
            "label": "n/a",
            "score": None,
            "matched": [],
            "missing": [],
            "match_details": [],
            "method": "v2_multilingual_keyphrase",
        }

    matched: List[str] = []
    missing: List[str] = []
    details: List[Dict[str, Any]] = []

    for phrase in phrases:
        detail: Dict[str, Any] = {"phrase": phrase, "match_type": "no_match"}
        if _exact_match(phrase, answer, language):
            detail["match_type"] = "exact_match"
            matched.append(phrase)
        elif is_primarily_numeric_phrase(phrase) and _numeric_match(phrase, answer, language, facts):
            detail["match_type"] = "normalized_match" if language == "en" else "multilingual_variant_match"
            matched.append(phrase)
        elif _normalized_match(phrase, answer, language):
            detail["match_type"] = "normalized_match"
            matched.append(phrase)
        elif language in ("hi", "kn") and is_primarily_numeric_phrase(phrase):
            # Indic digit normalization attempted; still no numeric hit.
            detail["match_type"] = "no_match"
            missing.append(phrase)
        elif language in ("hi", "kn") and not is_primarily_numeric_phrase(phrase):
            # Non-numeric phrase in Indic answer without deterministic variant → review required.
            detail["match_type"] = "semantic_review_required"
            missing.append(phrase)
        else:
            missing.append(phrase)
        details.append(detail)

    review_required = any(d["match_type"] == "semantic_review_required" for d in details)
    if not matched:
        label = "semantic_review_required" if review_required else "incorrect"
        return {
            "label": label,
            "score": 0.0,
            "matched": matched,
            "missing": missing,
            "match_details": details,
            "method": "v2_multilingual_keyphrase",
        }
    if missing:
        score = len(matched) / float(len(phrases))
        label = "partial"
        if review_required and score == 0:
            label = "semantic_review_required"
        return {
            "label": label,
            "score": score,
            "matched": matched,
            "missing": missing,
            "match_details": details,
            "method": "v2_multilingual_keyphrase",
        }
    return {
        "label": "correct",
        "score": 1.0,
        "matched": matched,
        "missing": [],
        "match_details": details,
        "method": "v2_multilingual_keyphrase",
    }


def keyphrase_correctness_v2(
    answer: str,
    phrases: Sequence[str],
    *,
    language: str = "en",
    facts: Sequence[str] = (),
) -> Dict[str, Any]:
    return match_keyphrase_multilingual(answer, phrases, language=language, facts=facts)
