"""Benchmark case schema and question-normalization helpers."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple

from evaluation.paths import CATEGORIES, DIFFICULTIES, EXPECTED_BEHAVIORS, LANGUAGES

_PUNCT = re.compile(r"[^\w\s\u0900-\u097F\u0C80-\u0CFF]", re.UNICODE)
_WS = re.compile(r"\s+")


def normalize_question(text: str) -> str:
    value = (text or "").strip().lower()
    value = _PUNCT.sub(" ", value)
    return _WS.sub(" ", value).strip()


def _require(condition: bool, errors: List[str], message: str) -> None:
    if not condition:
        errors.append(message)


def validate_evidence_item(item: Any, index: int) -> List[str]:
    errors: List[str] = []
    if not isinstance(item, dict):
        return [f"evidence[{index}] is not an object"]
    for key in ("document_id", "document_path", "excerpt"):
        _require(isinstance(item.get(key), str) and item[key].strip(), errors, f"evidence[{index}].{key} missing")
    excerpt = str(item.get("excerpt") or "").strip()
    _require(len(excerpt) >= 12, errors, f"evidence[{index}].excerpt too short")
    return errors


def validate_case_schema(case: Any) -> List[str]:
    errors: List[str] = []
    if not isinstance(case, dict):
        return ["case is not an object"]
    for key in ("id", "scheme", "category", "difficulty", "language", "question", "expected_behavior", "ground_truth"):
        _require(key in case, errors, f"missing field {key}")
    _require(isinstance(case.get("id"), str) and case.get("id", "").startswith("gsb1-"), errors, "id must be gsb1-*")
    _require(case.get("category") in CATEGORIES, errors, f"invalid category: {case.get('category')}")
    _require(case.get("difficulty") in DIFFICULTIES, errors, f"invalid difficulty: {case.get('difficulty')}")
    _require(case.get("language") in LANGUAGES, errors, f"invalid language: {case.get('language')}")
    _require(
        case.get("expected_behavior") in EXPECTED_BEHAVIORS,
        errors,
        f"invalid expected_behavior: {case.get('expected_behavior')}",
    )
    question = case.get("question")
    _require(isinstance(question, str) and len(question.strip()) >= 8, errors, "question too short")
    gt = case.get("ground_truth")
    _require(isinstance(gt, dict) and bool(gt), errors, "ground_truth empty")
    evidence = case.get("evidence")
    _require(isinstance(evidence, list), errors, "evidence must be a list")
    if isinstance(evidence, list):
        if case.get("category") != "unsupported" and not evidence:
            errors.append("evidence required for non-unsupported cases")
        for i, item in enumerate(evidence or []):
            errors.extend(validate_evidence_item(item, i))
    if isinstance(gt, dict) and case.get("category") == "eligibility":
        _require(gt.get("eligibility_status") in ("eligible", "ineligible"), errors, "eligibility_status required")
        _require(isinstance(gt.get("citizen_profile"), dict), errors, "citizen_profile required")
    if isinstance(gt, dict) and case.get("category") == "unsupported":
        _require(isinstance(gt.get("must_not_assert"), list) and gt.get("must_not_assert"), errors, "must_not_assert required")
    return errors


def find_duplicate_questions(cases: Iterable[Dict[str, Any]]) -> List[Tuple[str, str, str]]:
    seen: Dict[str, str] = {}
    dupes: List[Tuple[str, str, str]] = []
    for case in cases:
        key = (case.get("language") or "en", normalize_question(case.get("question") or ""))
        token = f"{key[0]}::{key[1]}"
        if not key[1]:
            continue
        if token in seen:
            dupes.append((seen[token], case.get("id") or "?", key[1]))
        else:
            seen[token] = case.get("id") or "?"
    return dupes
