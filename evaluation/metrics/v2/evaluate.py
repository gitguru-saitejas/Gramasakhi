"""Benchmark v2 scoring and aggregation (methodology-fixed, legacy preserved)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from evaluation.metrics.compute import mean, percentile
from evaluation.metrics.evaluate import (
    aggregate_scores as aggregate_scores_legacy,
    eligibility_match,
    keyphrase_correctness,
    score_case as score_case_legacy,
    unsupported_detection,
)
from evaluation.metrics.v2.eligibility import eligibility_confusion_matrix, eligibility_prf_from_matrix, score_eligibility_v2
from evaluation.metrics.v2.multilingual import keyphrase_correctness_v2
from evaluation.metrics.v2.retrieval import score_retrieval


def score_case_v2(case: Dict[str, Any], run: Dict[str, Any]) -> Dict[str, Any]:
    """Score one case with legacy v1 fields plus v2 methodology-fixed fields."""
    legacy = score_case_legacy(case, run)
    payload = run.get("response") or {}
    answer = str(payload.get("answer") or "")
    gt = case.get("ground_truth") or {}
    language = str(case.get("language") or "en")

    factual_v2 = keyphrase_correctness_v2(
        answer,
        gt.get("required_keyphrases") or [],
        language=language,
        facts=gt.get("facts") or [],
    )
    retrieval_v2 = score_retrieval(case, payload)
    elig_v2 = score_eligibility_v2(
        gt.get("eligibility_status"),
        answer,
        language=language,
        api_field=payload.get("eligibility_status"),
    )

    legacy_factual = keyphrase_correctness(answer, gt.get("required_keyphrases") or [])
    legacy_elig = eligibility_match(gt.get("eligibility_status"), payload.get("eligibility_status"), answer)

    return {
        **legacy,
        "legacy": {
            "factual": legacy_factual,
            "eligibility": legacy_elig,
            "precision_at_1": legacy.get("precision_at_1"),
            "precision_at_3": legacy.get("precision_at_3"),
            "precision_at_5": legacy.get("precision_at_5"),
            "recall_at_5": legacy.get("recall_at_5"),
            "retrieval_available": legacy.get("retrieval_available"),
        },
        "factual_v2": factual_v2,
        "retrieval_v2": retrieval_v2,
        "eligibility_v2": elig_v2,
    }


def aggregate_scores_v2(scored: List[Dict[str, Any]]) -> Dict[str, Any]:
    legacy_metrics = aggregate_scores_legacy(scored)
    successes = [row for row in scored if row.get("ok")]

    factual_rows = [
        row
        for row in successes
        if row.get("category") in ("factual", "multilingual", "difficult")
        and row["factual_v2"]["score"] is not None
        and row.get("category") != "unsupported"
    ]
    factual_confident = [row for row in factual_rows if row["factual_v2"]["label"] != "semantic_review_required"]

    retrieval_evaluated = [row for row in successes if row["retrieval_v2"].get("status") == "evaluated"]
    retrieval_no_source = [row for row in successes if row["retrieval_v2"].get("status") == "no_source"]
    retrieval_unevaluated = [row for row in successes if row["retrieval_v2"].get("status") == "unevaluated"]
    retrieval_hits = [row for row in retrieval_evaluated if row["retrieval_v2"].get("hit_at_1")]

    elig_rows = [row for row in successes if row.get("category") == "eligibility"]
    elig_scored = [row for row in elig_rows if row["eligibility_v2"].get("score") is not None]
    elig_uncertain = [row for row in elig_rows if row["eligibility_v2"].get("label") == "uncertain"]

    confusion_inputs = []
    for row in elig_rows:
        expected = row["eligibility_v2"].get("expected")
        if expected not in ("eligible", "ineligible"):
            continue
        predicted = row["eligibility_v2"].get("predicted_polarity", "UNCERTAIN")
        if predicted not in ("ELIGIBLE", "INELIGIBLE", "UNCERTAIN"):
            predicted = "UNCERTAIN"
        confusion_inputs.append((expected, predicted))
    elig_stats = eligibility_prf_from_matrix(eligibility_confusion_matrix(confusion_inputs))

    def _na(value: Optional[float]) -> Any:
        return value if value is not None else "N/A"

    language_acc_v2: Dict[str, Any] = {}
    language_review: Dict[str, int] = {}
    for lang in ("en", "hi", "kn"):
        subset = [row for row in factual_confident if row.get("language") == lang]
        review_subset = [row for row in factual_rows if row.get("language") == lang and row["factual_v2"]["label"] == "semantic_review_required"]
        language_review[lang] = len(review_subset)
        if not subset:
            language_acc_v2[lang] = "N/A"
        else:
            language_acc_v2[lang] = mean([row["factual_v2"]["score"] for row in subset])

    category_acc_v2: Dict[str, Any] = {}
    for cat in ("factual", "eligibility", "unsupported", "multilingual", "difficult"):
        if cat == "unsupported":
            subset = [row for row in successes if row.get("category") == "unsupported"]
            category_acc_v2[cat] = (
                mean([1.0 if row["unsupported"]["unsupported_detected"] else 0.0 for row in subset])
                if subset
                else "N/A"
            )
        elif cat == "eligibility":
            subset = elig_scored
            category_acc_v2[cat] = mean([row["eligibility_v2"]["score"] for row in subset]) if subset else "N/A"
        else:
            subset = [row for row in factual_confident if row.get("category") == cat]
            category_acc_v2[cat] = mean([row["factual_v2"]["score"] for row in subset]) if subset else "N/A"

    latencies = [row["latency_ms"] for row in scored if isinstance(row.get("latency_ms"), (int, float))]

    re_evaluated = {
        "precision_at_1": _na(mean([row["retrieval_v2"]["precision_at_1"] for row in retrieval_evaluated])),
        "precision_at_3": _na(mean([row["retrieval_v2"]["precision_at_3"] for row in retrieval_evaluated])),
        "precision_at_5": _na(mean([row["retrieval_v2"]["precision_at_5"] for row in retrieval_evaluated])),
        "retrieval_recall_at_5": _na(mean([row["retrieval_v2"]["recall_at_5"] for row in retrieval_evaluated])),
        "retrieval_evaluable_cases": len(retrieval_evaluated),
        "retrieval_no_source_cases": len(retrieval_no_source),
        "retrieval_unevaluated_cases": len(retrieval_unevaluated),
        "retrieval_hit_at_1_cases": len(retrieval_hits),
        "retrieval_miss_at_1_cases": len(retrieval_evaluated) - len(retrieval_hits),
        "factual_correctness": _na(mean([row["factual_v2"]["score"] for row in factual_confident])),
        "factual_full_correct": len([row for row in factual_confident if row["factual_v2"]["label"] == "correct"]),
        "factual_partial": len([row for row in factual_confident if row["factual_v2"]["label"] == "partial"]),
        "factual_evaluated": len(factual_confident),
        "factual_semantic_review_required": len(
            [row for row in factual_rows if row["factual_v2"]["label"] == "semantic_review_required"]
        ),
        "eligibility": elig_stats,
        "eligibility_scored_cases": len(elig_scored),
        "eligibility_uncertain_cases": len(elig_uncertain),
        "language_accuracy": language_acc_v2,
        "language_semantic_review_required": language_review,
        "category_accuracy": category_acc_v2,
        "unsupported_detection_rate": legacy_metrics.get("unsupported_detection_rate"),
        "hallucination_rate": legacy_metrics.get("hallucination_rate"),
        "hallucination_case_ids": legacy_metrics.get("hallucination_case_ids"),
        "average_latency_ms": _na(mean(latencies)),
        "p95_latency_ms": _na(percentile(latencies, 95)),
        "p50_latency_ms": _na(percentile(latencies, 50)),
        "note": (
            "Re-evaluated metrics use scheme_id retrieval matching, multilingual-aware keyphrase "
            "normalization, and eligibility polarity extraction. Unsupported/hallucination metrics "
            "are unchanged from legacy v1."
        ),
    }

    return {
        "legacy_v1": legacy_metrics,
        "re_evaluated_v2": re_evaluated,
        "comparison_note": "legacy_v1 preserves original benchmark v1 methodology for reproducibility",
    }


def classification_changes(scored: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Cases whose primary label changed between legacy and v2 evaluators."""
    changes: List[Dict[str, Any]] = []
    for row in scored:
        case_id = row.get("id")
        cat = row.get("category")
        reasons: List[str] = []
        old_label = None
        new_label = None

        if cat in ("factual", "multilingual", "difficult"):
            old_label = row["legacy"]["factual"]["label"]
            new_label = row["factual_v2"]["label"]
            if old_label != new_label:
                reasons.append("factual_keyphrase_method")
        elif cat == "eligibility":
            old_label = row["legacy"]["eligibility"]["label"]
            new_label = row["eligibility_v2"]["label"]
            if old_label != new_label:
                reasons.append("eligibility_polarity_method")
        elif cat == "unsupported":
            continue

        retrieval_old = row["legacy"].get("precision_at_1")
        retrieval_new = row["retrieval_v2"].get("precision_at_1")
        if retrieval_old != retrieval_new and (retrieval_old or retrieval_new is not None):
            reasons.append("retrieval_scheme_id_method")
            if not old_label:
                old_label = str(retrieval_old)
                new_label = str(retrieval_new)

        if reasons:
            changes.append(
                {
                    "id": case_id,
                    "category": cat,
                    "old": old_label,
                    "new": new_label,
                    "reasons": reasons,
                }
            )
    return changes
