"""Eligibility polarity extraction (benchmark v2)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from evaluation.metrics.v2.normalize import normalize_text_for_language

Polarity = str  # ELIGIBLE | INELIGIBLE | UNCERTAIN | NOT_APPLICABLE

# English patterns — order matters (stronger / more specific first).
_INELIGIBLE_PATTERNS: List[re.Pattern[str]] = [
    re.compile(p, re.I)
    for p in (
        r"\b(not eligible|ineligible)\b",
        r"\b(do not|does not|doesn't|don't)\s+(qualify|meet the criteria|meet eligibility)\b",
        r"\b(cannot|can't|can not)\s+(apply|enroll|avail|receive)\b",
        r"\b(does not|do not|doesn't|don't)\s+apply\b",
        r"\bthis benefit does not apply\b",
        r"\boutside the (?:commonly published )?age band\b",
        r"\bis not (?:an? )?(?:intended )?beneficiary\b",
        r"\bdoes not treat .{0,40} as (?:an? )?(?:intended )?beneficiary\b",
        r"\bnot (?:within|inside) the (?:age band|eligible age)\b",
        r"\bno[, ]+ .{0,20} (?:is|are) not eligible\b",
    )
]

_ELIGIBLE_PATTERNS: List[re.Pattern[str]] = [
    re.compile(p, re.I)
    for p in (
        r"\byou are eligible\b",
        r"\b(is|are) eligible\b",
        r"\b(you )?(can|may) apply\b",
        r"\b(you )?(can|may) avail\b",
        r"\b(you )?(can|may) enroll\b",
        r"\b(you )?qualify\b",
        r"\bmeet(s)? the (?:eligibility )?criteria\b",
        r"\bintended beneficiary\b",
        r"\beligible (?:woman|women|citizen|passenger|farmer|member)\b",
        r"\b(yes[, ]+)?(?:you|they) (?:can|may) (?:receive|get|obtain)\b",
        r"\bwithin the (?:commonly published )?age band\b",
        r"\binside the (?:commonly published )?age band\b",
    )
]

_UNCERTAIN_PATTERNS: List[re.Pattern[str]] = [
    re.compile(p, re.I)
    for p in (
        r"\bcannot (?:confirm|determine|verify|conclude)\b",
        r"\bcannot be confirmed\b",
        r"\bmay be eligible if\b",
        r"\beligibility depends\b",
        r"\bdepends on\b",
        r"\bif you meet\b",
        r"\binsufficient (?:evidence|information)\b",
        r"\bnot enough (?:evidence|information)\b",
        r"\bunclear\b",
        r"\bwithout (?:more|additional) (?:information|details)\b",
        r"\bcouldn't (?:identify|generate|find)\b",
        r"\bplease try again\b",
    )
]

# Hindi patterns (deterministic subset).
_HI_INELIGIBLE = [
    re.compile(p)
    for p in (
        r"पात्र नहीं",
        r"अपात्र",
        r"योग्य नहीं",
        r"पात्रता नहीं",
    )
]
_HI_ELIGIBLE = [
    re.compile(p)
    for p in (
        r"पात्र",
        r"योग्य",
        r"आवेदन कर",
        r"लाभार्थी",
    )
]

# Kannada patterns (deterministic subset).
_KN_INELIGIBLE = [
    re.compile(p)
    for p in (
        r"ಅರ್ಹರಲ್ಲ",
        r"ಅರ್ಹತೆ\s*ಇಲ್ಲ",
        r"ಪಾತ್ರ\s*ಇಲ್ಲ",
    )
]
_KN_ELIGIBLE = [
    re.compile(p)
    for p in (
        r"ಅರ್ಹ",
        r"ಲಾಭಾರ್ಥಿ",
        r"ಅರ್ಹತ",
    )
]


def _count_matches(patterns: List[re.Pattern[str]], text: str) -> int:
    return sum(1 for pat in patterns if pat.search(text))


def extract_eligibility_polarity(answer: str, language: str = "en") -> Dict[str, Any]:
    """Extract ELIGIBLE / INELIGIBLE / UNCERTAIN / NOT_APPLICABLE from answer text."""
    if not (answer or "").strip():
        return {"polarity": "UNCERTAIN", "confidence": "low", "method": "polarity_extractor_v2", "signals": []}

    norm = normalize_text_for_language(answer, language)
    signals: List[str] = []

    inel = _count_matches(_INELIGIBLE_PATTERNS, norm)
    elig = _count_matches(_ELIGIBLE_PATTERNS, norm)
    uncertain = _count_matches(_UNCERTAIN_PATTERNS, norm)

    if language == "hi":
        inel += _count_matches(_HI_INELIGIBLE, answer)
        elig += _count_matches(_HI_ELIGIBLE, answer)
        # "पात्र नहीं" counts as both — prioritize ineligible when negation present.
        if re.search(r"पात्र\s*नहीं", answer):
            inel += 1
            elig = max(0, elig - 1)
    elif language == "kn":
        inel += _count_matches(_KN_INELIGIBLE, answer)
        elig += _count_matches(_KN_ELIGIBLE, answer)

    if inel:
        signals.append("ineligible_patterns")
    if elig:
        signals.append("eligible_patterns")
    if uncertain:
        signals.append("uncertain_patterns")

    # Explicit negation of eligible wording.
    if re.search(r"\bnot eligible\b", norm) or re.search(r"पात्र नहीं", answer):
        inel = max(inel, 1)
        elig = 0

    if re.search(r"\bdoes not treat\b", norm):
        inel = max(inel, 1)
        if re.search(r"\bas (?:an? )?(?:intended )?beneficiary\b", norm):
            elig = 0

    if uncertain and inel == 0 and elig == 0:
        return {"polarity": "UNCERTAIN", "confidence": "medium", "method": "polarity_extractor_v2", "signals": signals}

    if inel > 0 and elig > 0:
        # Conflicting statements → uncertain unless ineligible is clearly dominant.
        if inel >= elig + 1:
            return {"polarity": "INELIGIBLE", "confidence": "medium", "method": "polarity_extractor_v2", "signals": signals}
        return {"polarity": "UNCERTAIN", "confidence": "low", "method": "polarity_extractor_v2", "signals": signals}

    if inel > 0:
        return {"polarity": "INELIGIBLE", "confidence": "high", "method": "polarity_extractor_v2", "signals": signals}
    if elig > 0:
        return {"polarity": "ELIGIBLE", "confidence": "high", "method": "polarity_extractor_v2", "signals": signals}

    return {"polarity": "UNCERTAIN", "confidence": "low", "method": "polarity_extractor_v2", "signals": signals}


def _polarity_to_bool(polarity: Polarity) -> Optional[bool]:
    if polarity == "ELIGIBLE":
        return True
    if polarity == "INELIGIBLE":
        return False
    return None


def score_eligibility_v2(
    expected: Optional[str],
    answer: str,
    *,
    language: str = "en",
    api_field: Optional[str] = None,
) -> Dict[str, Any]:
    if expected not in ("eligible", "ineligible"):
        return {
            "label": "n/a",
            "score": None,
            "expected": expected,
            "predicted_polarity": "NOT_APPLICABLE",
            "method": "polarity_extractor_v2",
        }

    api_pred = (api_field or "").strip().lower()
    if api_pred in ("eligible", "ineligible"):
        ok = api_pred == expected
        return {
            "label": "correct" if ok else "incorrect",
            "score": 1.0 if ok else 0.0,
            "expected": expected,
            "predicted_polarity": api_pred.upper(),
            "method": "eligibility_api_field",
        }

    extracted = extract_eligibility_polarity(answer, language)
    polarity = extracted["polarity"]
    predicted = _polarity_to_bool(polarity)
    expected_pos = expected == "eligible"

    if predicted is None:
        return {
            "label": "uncertain",
            "score": None,
            "expected": expected,
            "predicted_polarity": polarity,
            "confidence": extracted.get("confidence"),
            "signals": extracted.get("signals"),
            "method": "polarity_extractor_v2",
        }

    ok = predicted == expected_pos
    return {
        "label": "correct" if ok else "incorrect",
        "score": 1.0 if ok else 0.0,
        "expected": expected,
        "predicted_polarity": polarity,
        "confidence": extracted.get("confidence"),
        "signals": extracted.get("signals"),
        "method": "polarity_extractor_v2",
    }


def eligibility_confusion_matrix(
    rows: List[Tuple[str, str]],
) -> Dict[str, Any]:
    """rows: list of (expected eligible|ineligible, predicted ELIGIBLE|INELIGIBLE|UNCERTAIN)."""
    matrix = {
        "eligible_predicted_eligible": 0,
        "eligible_predicted_ineligible": 0,
        "eligible_predicted_uncertain": 0,
        "ineligible_predicted_eligible": 0,
        "ineligible_predicted_ineligible": 0,
        "ineligible_predicted_uncertain": 0,
    }
    for expected, predicted in rows:
        key = f"{expected}_predicted_{predicted.lower()}"
        if key in matrix:
            matrix[key] += 1
    return matrix


def eligibility_prf_from_matrix(matrix: Dict[str, int]) -> Dict[str, Any]:
    tp = matrix["eligible_predicted_eligible"]
    fp = matrix["ineligible_predicted_eligible"]
    fn = matrix["eligible_predicted_ineligible"] + matrix["eligible_predicted_uncertain"]
    tn = matrix["ineligible_predicted_ineligible"]
    uncertain = matrix["eligible_predicted_uncertain"] + matrix["ineligible_predicted_uncertain"]
    support = sum(matrix.values())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    accuracy = (tp + tn) / support if support else None
    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "support": support,
        "uncertain_count": uncertain,
        "uncertain_rate": uncertain / support if support else None,
        "confusion_matrix": matrix,
    }
