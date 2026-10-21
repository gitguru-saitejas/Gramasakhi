"""Score a system response against evidence-backed ground truth."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

from evaluation.metrics.compute import binary_prf, mean, percentile, precision_at_k, recall_at_k

_REFUSAL = re.compile(
    r"\b(do not have|don't have|insufficient|not (enough|sufficient) (evidence|information)|"
    r"cannot (confirm|verify|determine)|unsupported|not stated|not mentioned|"
    r"official (portal|notification)|verify (on|with) the official)\b",
    re.I,
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _claim_negated_in_answer(answer: str, claim: str) -> bool:
    """True when the answer explicitly negates the must_not_assert claim."""
    low = (answer or "").lower()
    claim_low = claim.lower()
    idx = low.find(claim_low)
    if idx < 0:
        return False
    window_start = max(0, idx - 90)
    window = low[window_start : idx + len(claim_low) + 30]
    neg_patterns = (
        r"\b(?:does not|do not|doesn't|don't|not|no|never|cannot|can't|isn't|aren't)\b",
        r"\b(?:exclude|excluding|excluded|outside scope|not covered|not eligible|not include)\b",
    )
    return any(re.search(p, window) for p in neg_patterns)


def keyphrase_correctness(answer: str, phrases: Sequence[str]) -> Dict[str, Any]:
    blob = _norm(answer)
    if not phrases:
        return {"label": "n/a", "score": None, "matched": [], "missing": [], "method": "deterministic_keyphrase"}
    matched = [p for p in phrases if _norm(p) in blob]
    missing = [p for p in phrases if p not in matched]
    if not matched:
        return {"label": "incorrect", "score": 0.0, "matched": matched, "missing": missing, "method": "deterministic_keyphrase"}
    if missing:
        return {
            "label": "partial",
            "score": len(matched) / float(len(phrases)),
            "matched": matched,
            "missing": missing,
            "method": "deterministic_keyphrase",
        }
    return {"label": "correct", "score": 1.0, "matched": matched, "missing": [], "method": "deterministic_keyphrase"}


def unsupported_detection(answer: str, must_not_assert: Sequence[str], validated: Optional[bool]) -> Dict[str, Any]:
    blob = _norm(answer)
    leaked = []
    for claim in must_not_assert:
        if len(claim) >= 4 and _norm(claim) in blob:
            if _claim_negated_in_answer(answer, claim):
                continue
            leaked.append(claim)
    refused = bool(_REFUSAL.search(answer or ""))
    evidence_rejected = validated is False
    hallucinated = bool(leaked) and not refused
    detected = (refused or evidence_rejected) and not leaked
    return {
        "unsupported_detected": detected,
        "hallucinated": hallucinated,
        "leaked_claims": leaked,
        "refusal_language": refused,
        "method": "unsupported_detector",
    }


def eligibility_match(expected: Optional[str], predicted: Optional[str], answer: str) -> Dict[str, Any]:
    if expected not in ("eligible", "ineligible"):
        return {"label": "n/a", "score": None, "method": "eligibility_field"}
    pred = (predicted or "").strip().lower()
    if pred in ("eligible", "ineligible"):
        ok = pred == expected
        return {"label": "correct" if ok else "incorrect", "score": 1.0 if ok else 0.0, "method": "eligibility_field"}
    blob = _norm(answer)
    if expected == "eligible" and re.search(r"\b(eligible|yes)\b", blob) and "not eligible" not in blob:
        return {"label": "correct", "score": 1.0, "method": "eligibility_answer_text"}
    if expected == "ineligible" and re.search(r"\b(not eligible|ineligible|no)\b", blob):
        return {"label": "correct", "score": 1.0, "method": "eligibility_answer_text"}
    return {"label": "incorrect", "score": 0.0, "method": "eligibility_answer_text"}


def retrieved_ids(payload: Dict[str, Any]) -> List[str]:
    ids: List[str] = []
    for key in ("sources", "official_sources"):
        for item in payload.get(key) or []:
            if not isinstance(item, dict):
                continue
            for field in ("url", "source_url", "title", "name", "document_id", "id"):
                value = item.get(field)
                if value:
                    ids.append(str(value))
                    break
    return ids


def relevant_ids(case: Dict[str, Any]) -> List[str]:
    ids: List[str] = []
    for item in case.get("evidence") or []:
        for field in ("document_path", "document_id", "source_url", "excerpt_id"):
            value = item.get(field)
            if value:
                ids.append(str(value))
    return ids


def score_case(case: Dict[str, Any], run: Dict[str, Any]) -> Dict[str, Any]:
    payload = run.get("response") or {}
    answer = str(payload.get("answer") or "")
    gt = case.get("ground_truth") or {}
    factual = keyphrase_correctness(answer, gt.get("required_keyphrases") or [])
    unsup = unsupported_detection(answer, gt.get("must_not_assert") or [], payload.get("validated"))
    elig = eligibility_match(gt.get("eligibility_status"), payload.get("eligibility_status"), answer)
    retrieved = retrieved_ids(payload)
    relevant = relevant_ids(case)
    retrieval_available = bool(retrieved)
    return {
        "id": case.get("id"),
        "category": case.get("category"),
        "language": case.get("language"),
        "difficulty": case.get("difficulty"),
        "scheme": case.get("scheme"),
        "ok": run.get("ok") is True,
        "http_status": run.get("http_status"),
        "latency_ms": run.get("latency_ms"),
        "error": run.get("error"),
        "factual": factual,
        "unsupported": unsup,
        "eligibility": elig,
        "precision_at_1": precision_at_k(relevant, retrieved, 1) if retrieval_available else None,
        "precision_at_3": precision_at_k(relevant, retrieved, 3) if retrieval_available else None,
        "precision_at_5": precision_at_k(relevant, retrieved, 5) if retrieval_available else None,
        "recall_at_5": recall_at_k(relevant, retrieved, 5) if retrieval_available else None,
        "retrieval_available": retrieval_available,
        "answer_preview": answer[:280],
        "validated": payload.get("validated"),
        "eligibility_status": payload.get("eligibility_status"),
    }


def aggregate_scores(scored: List[Dict[str, Any]]) -> Dict[str, Any]:
    latencies = [row["latency_ms"] for row in scored if isinstance(row.get("latency_ms"), (int, float))]
    successes = [row for row in scored if row.get("ok")]
    errors = [row for row in scored if not row.get("ok")]

    factual_rows = [
        row
        for row in successes
        if row.get("category") in ("factual", "multilingual", "difficult")
        and row["factual"]["score"] is not None
        and row.get("category") != "unsupported"
    ]
    correct = [row for row in factual_rows if row["factual"]["label"] == "correct"]
    partial = [row for row in factual_rows if row["factual"]["label"] == "partial"]

    unsup_rows = [row for row in successes if row.get("category") == "unsupported"]
    elig_pairs = []
    for row in successes:
        if row["eligibility"]["score"] is None:
            continue
        expected_pos = (row.get("eligibility_status") == "eligible") or (
            row["eligibility"]["label"] == "correct" and False
        )
        # Use ground-truth polarity from score method: correct+eligible question tracked via predicted field.
        predicted_eligible = str(row.get("eligibility_status") or "").lower() == "eligible"
        # Reconstruct expected from correctness + predicted when field present.
        if row["eligibility"]["method"] == "eligibility_field":
            expected_eligible = predicted_eligible if row["eligibility"]["label"] == "correct" else not predicted_eligible
            elig_pairs.append((expected_eligible, predicted_eligible))

    retrieval_p1 = [row["precision_at_1"] for row in successes if row.get("precision_at_1") is not None]
    retrieval_p3 = [row["precision_at_3"] for row in successes if row.get("precision_at_3") is not None]
    retrieval_p5 = [row["precision_at_5"] for row in successes if row.get("precision_at_5") is not None]
    retrieval_r5 = [row["recall_at_5"] for row in successes if row.get("recall_at_5") is not None]

    def _na(value: Optional[float]) -> Any:
        return value if value is not None else "N/A"

    language_acc = {}
    for lang in ("en", "hi", "kn"):
        subset = [row for row in factual_rows if row.get("language") == lang]
        if not subset:
            language_acc[lang] = "N/A"
        else:
            language_acc[lang] = mean([row["factual"]["score"] for row in subset])

    difficulty_acc = {}
    for diff in ("easy", "medium", "hard", "adversarial"):
        subset = [row for row in factual_rows if row.get("difficulty") == diff]
        difficulty_acc[diff] = mean([row["factual"]["score"] for row in subset]) if subset else "N/A"

    category_acc = {}
    for cat in ("factual", "eligibility", "unsupported", "multilingual", "difficult"):
        if cat == "unsupported":
            subset = unsup_rows
            category_acc[cat] = (
                mean([1.0 if row["unsupported"]["unsupported_detected"] else 0.0 for row in subset])
                if subset
                else "N/A"
            )
        elif cat == "eligibility":
            subset = [row for row in successes if row.get("category") == "eligibility" and row["eligibility"]["score"] is not None]
            category_acc[cat] = mean([row["eligibility"]["score"] for row in subset]) if subset else "N/A"
        else:
            subset = [row for row in factual_rows if row.get("category") == cat]
            category_acc[cat] = mean([row["factual"]["score"] for row in subset]) if subset else "N/A"

    return {
        "n_cases": len(scored),
        "success_rate": (len(successes) / len(scored)) if scored else "N/A",
        "error_rate": (len(errors) / len(scored)) if scored else "N/A",
        "n_errors": len(errors),
        "average_latency_ms": _na(mean(latencies)),
        "p95_latency_ms": _na(percentile(latencies, 95)),
        "precision_at_1": _na(mean(retrieval_p1)),
        "precision_at_3": _na(mean(retrieval_p3)),
        "precision_at_5": _na(mean(retrieval_p5)),
        "retrieval_recall_at_5": _na(mean(retrieval_r5)),
        "factual_correctness": _na(mean([row["factual"]["score"] for row in factual_rows])),
        "factual_full_correct": len(correct),
        "factual_partial": len(partial),
        "factual_evaluated": len(factual_rows),
        "unsupported_detection_rate": (
            mean([1.0 if row["unsupported"]["unsupported_detected"] else 0.0 for row in unsup_rows])
            if unsup_rows
            else "N/A"
        ),
        "hallucination_rate": (
            mean([1.0 if row["unsupported"]["hallucinated"] else 0.0 for row in unsup_rows])
            if unsup_rows
            else "N/A"
        ),
        "eligibility": binary_prf(elig_pairs) if elig_pairs else {"accuracy": "N/A", "precision": "N/A", "recall": "N/A", "f1": "N/A", "support": 0},
        "language_accuracy": language_acc,
        "difficulty_accuracy": difficulty_acc,
        "category_accuracy": category_acc,
        "failed_case_ids": [row["id"] for row in errors],
        "hallucination_case_ids": [row["id"] for row in unsup_rows if row["unsupported"]["hallucinated"]],
        "note": (
            "Factual scores are deterministic keyphrase overlap against seed excerpts, "
            "not LLM-as-judge unless labeled otherwise. Retrieval metrics are N/A when the API returns no sources."
        ),
    }
