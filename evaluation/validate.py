"""Validation gate for benchmark_v1 cases."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set

from evaluation.eligibility import derive_eligibility
from evaluation.schema import find_duplicate_questions, validate_case_schema

_DEVANAGARI = range(0x0900, 0x097F)
_KANNADA = range(0x0C80, 0x0CFF)


def _has_script(text: str, codepoints: range) -> bool:
    return any(ord(ch) in codepoints for ch in text)


def _excerpt_blob(case: Dict[str, Any]) -> str:
    return "\n".join(str(item.get("excerpt") or "") for item in case.get("evidence") or [])


def _keyphrases_traceable(case: Dict[str, Any]) -> Optional[str]:
    if case.get("expected_behavior") in ("unsupported",):
        return None
    phrases = (case.get("ground_truth") or {}).get("required_keyphrases") or []
    blob = _excerpt_blob(case).lower()
    missing = [p for p in phrases if p.lower() not in blob]
    if missing:
        return f"keyphrases not in evidence: {missing}"
    return None


def _unsupported_is_unsupported(case: Dict[str, Any]) -> Optional[str]:
    if case.get("category") != "unsupported":
        return None
    if case.get("expected_behavior") != "unsupported":
        return "unsupported case must expect unsupported"
    blob = _excerpt_blob(case).lower()
    hits = []
    for claim in (case.get("ground_truth") or {}).get("must_not_assert") or []:
        token = claim.lower().strip()
        if len(token) >= 6 and token in blob:
            hits.append(claim)
    if hits:
        return f"claimed-unsupported assertion appears in evidence: {hits}"
    return None


def _language_ok(case: Dict[str, Any]) -> Optional[str]:
    lang = case.get("language")
    question = case.get("question") or ""
    if lang == "hi" and not _has_script(question, _DEVANAGARI):
        return "Hindi case lacks Devanagari"
    if lang == "kn" and not _has_script(question, _KANNADA):
        return "Kannada case lacks Kannada script"
    if lang in ("hi", "kn"):
        translation = case.get("translation") or {}
        if translation.get("validated") is not True:
            return "multilingual case is not translation-validated"
    return None


def _eligibility_ok(case: Dict[str, Any]) -> Optional[str]:
    gt = case.get("ground_truth") or {}
    profile = gt.get("citizen_profile")
    expected = gt.get("eligibility_status")
    if case.get("category") != "eligibility" and expected not in ("eligible", "ineligible"):
        return None
    if not profile:
        if case.get("category") == "eligibility":
            return "eligibility case missing citizen_profile"
        return None
    derived = derive_eligibility(case.get("scheme") or "", profile)
    if derived is None:
        return "eligibility cannot be derived from profile and seed rules"
    if expected and derived != expected:
        return f"derived eligibility {derived} != expected {expected}"
    return None


def _source_ok(case: Dict[str, Any], allowed_urls: Set[str], allowed_paths: Set[str]) -> Optional[str]:
    for item in case.get("evidence") or []:
        path = (item.get("document_path") or "").replace("\\", "/")
        if path not in allowed_paths:
            return f"fabricated or unknown document_path: {path}"
        url = item.get("source_url")
        if url and url not in allowed_urls:
            return f"fabricated source_url: {url}"
    return None


def validate_case(
    case: Dict[str, Any],
    *,
    allowed_urls: Set[str],
    allowed_paths: Set[str],
) -> List[str]:
    errors = validate_case_schema(case)
    for check in (
        _keyphrases_traceable(case),
        _unsupported_is_unsupported(case),
        _language_ok(case),
        _eligibility_ok(case),
        _source_ok(case, allowed_urls, allowed_paths),
    ):
        if check:
            errors.append(check)
    return errors


def validate_benchmark(
    cases: Iterable[Dict[str, Any]],
    *,
    allowed_urls: Set[str],
    allowed_paths: Set[str],
) -> Dict[str, Any]:
    accepted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    for case in cases:
        errors = validate_case(case, allowed_urls=allowed_urls, allowed_paths=allowed_paths)
        if errors:
            rejected.append({"id": case.get("id"), "question": case.get("question"), "errors": errors})
        else:
            accepted.append(case)
    dupes = find_duplicate_questions(accepted)
    if dupes:
        drop = {b for _, b, _ in dupes}
        kept = []
        for case in accepted:
            if case["id"] in drop:
                rejected.append(
                    {
                        "id": case["id"],
                        "question": case.get("question"),
                        "errors": [f"duplicate of {a}" for a, b, _ in dupes if b == case["id"]],
                    }
                )
            else:
                kept.append(case)
        accepted = kept
    return {
        "accepted": accepted,
        "rejected": rejected,
        "duplicate_pairs": [{"kept": a, "rejected": b, "normalized": n} for a, b, n in dupes],
    }


def assign_stable_ids(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for i, case in enumerate(cases, start=1):
        cloned = dict(case)
        cloned["id"] = f"gsb1-{i:04d}"
        out.append(cloned)
    return out
