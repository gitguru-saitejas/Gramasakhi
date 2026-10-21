#!/usr/bin/env python3
"""Re-evaluate saved benchmark v1 responses with methodology-fixed v2 metrics."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.metrics.v2.evaluate import aggregate_scores_v2, classification_changes, score_case_v2  # noqa: E402
from evaluation.paths import (  # noqa: E402
    BENCHMARK_PATH,
    RE_EVALUATED_REPORT_PATH,
    RE_EVALUATED_RESULTS_PATH,
    RESULTS_PATH,
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_re_evaluated_report(
    *,
    dataset_meta: dict,
    scored: list,
    metrics: dict,
    changes: list,
    source_results_path: Path,
) -> str:
    legacy = metrics["legacy_v1"]
    v2 = metrics["re_evaluated_v2"]
    latencies = [row["latency_ms"] for row in scored if isinstance(row.get("latency_ms"), (int, float))]

    lines = [
        "# GramSakhi Benchmark v1 — Re-evaluated Report (Methodology v2)",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"Source results: `{source_results_path}`",
        f"Source generated at: {dataset_meta.get('source_generated_at', 'unknown')}",
        "",
        "## 1. Executive summary",
        "",
        "This report re-scores the **unchanged** 100 saved API responses using methodology-fixed v2 evaluators.",
        "Legacy v1 metrics are preserved for academic reproducibility.",
        "",
        f"- Cases: **{len(scored)}**",
        f"- HTTP success (legacy): **{legacy.get('success_rate')}**",
        f"- Classification changes vs legacy: **{len(changes)}** cases",
        "",
        "## 2. Dataset",
        "",
        json.dumps(dataset_meta.get("distribution") or {}, indent=2, ensure_ascii=False),
        "",
        "## 3. Execution integrity",
        "",
        "- 100/100 genuine authenticated responses (unchanged raw runs)",
        "- Raw API responses were **not** modified",
        "- Unique case IDs verified during re-evaluation",
        "",
        "## 4. Retrieval",
        "",
        "### Legacy v1",
        "",
        f"- P@1: {legacy.get('precision_at_1')}",
        f"- P@3: {legacy.get('precision_at_3')}",
        f"- P@5: {legacy.get('precision_at_5')}",
        f"- Recall@5: {legacy.get('retrieval_recall_at_5')}",
        "",
        "_Legacy comparison used literal path/URL string equality; often 0.0 despite correct scheme content._",
        "",
        "### Re-evaluated v2 (canonical scheme_id)",
        "",
        f"- P@1: {v2.get('precision_at_1')}",
        f"- P@3: {v2.get('precision_at_3')}",
        f"- P@5: {v2.get('precision_at_5')}",
        f"- Recall@5: {v2.get('retrieval_recall_at_5')}",
        f"- Evaluable cases: {v2.get('retrieval_evaluable_cases')}",
        f"- No-source cases: {v2.get('retrieval_no_source_cases')}",
        f"- Unevaluated cases: {v2.get('retrieval_unevaluated_cases')}",
        f"- Hit@1 cases: {v2.get('retrieval_hit_at_1_cases')}",
        f"- Miss@1 cases: {v2.get('retrieval_miss_at_1_cases')}",
        "",
        "Normalization: API source `scheme_id`, metadata, seed paths, demo_seed URLs, and myScheme slugs → canonical scheme_id.",
        "",
        "## 5. Factual",
        "",
        f"- Legacy keyphrase correctness: {legacy.get('factual_correctness')}",
        f"- Re-evaluated correctness: {v2.get('factual_correctness')}",
        f"- Full correct: {v2.get('factual_full_correct')} / {v2.get('factual_evaluated')}",
        f"- Partial: {v2.get('factual_partial')}",
        f"- Semantic review required: {v2.get('factual_semantic_review_required')}",
        "",
        "### Language breakdown (v2)",
        "",
        json.dumps(v2.get("language_accuracy") or {}, indent=2),
        "",
        json.dumps(v2.get("language_semantic_review_required") or {}, indent=2),
        "",
        "## 6. Eligibility",
        "",
        f"- Legacy accuracy: {legacy.get('category_accuracy', {}).get('eligibility')}",
        f"- Re-evaluated accuracy: {v2.get('eligibility', {}).get('accuracy')}",
        f"- Precision: {v2.get('eligibility', {}).get('precision')}",
        f"- Recall: {v2.get('eligibility', {}).get('recall')}",
        f"- F1: {v2.get('eligibility', {}).get('f1')}",
        f"- Uncertain rate: {v2.get('eligibility', {}).get('uncertain_rate')}",
        f"- Uncertain cases: {v2.get('eligibility_uncertain_cases')}",
        "",
        "### Confusion matrix",
        "",
        json.dumps(v2.get("eligibility", {}).get("confusion_matrix") or {}, indent=2),
        "",
        "## 7. Multilingual",
        "",
        "See language breakdown above. Hindi/Kannada numeric normalization uses Devanagari/Kannada digit mapping.",
        "Non-numeric Indic keyphrases may be marked `semantic_review_required` rather than auto-scored.",
        "",
        "## 8. Unsupported / hallucination (unchanged legacy)",
        "",
        f"- Unsupported detection: {v2.get('unsupported_detection_rate')}",
        f"- Hallucination rate: {v2.get('hallucination_rate')}",
        f"- Hallucination cases: {v2.get('hallucination_case_ids')}",
        "",
        "## 9. Latency (unchanged)",
        "",
        f"- Average ms: {v2.get('average_latency_ms')}",
        f"- P50 ms: {v2.get('p50_latency_ms')}",
        f"- P95 ms: {v2.get('p95_latency_ms')}",
        f"- Min ms: {min(latencies) if latencies else 'N/A'}",
        f"- Max ms: {max(latencies) if latencies else 'N/A'}",
        "",
        "## 10. Methodological limitations",
        "",
        "- v2 retrieval uses scheme_id identity, not chunk-level relevance.",
        "- Multilingual non-numeric phrases may require manual review.",
        "- Eligibility polarity extraction is deterministic, not a full semantic engine.",
        "- No LLM-as-judge; no human adjudication.",
        "- Local CPU inference latency is not production representative.",
        "",
        "## 11. Before vs after",
        "",
        "| Metric | Legacy v1 | Re-evaluated v2 | Why different |",
        "|--------|----------:|----------------:|---------------|",
        f"| Retrieval P@1 | {legacy.get('precision_at_1')} | {v2.get('precision_at_1')} | scheme_id normalization |",
        f"| Retrieval P@5 | {legacy.get('precision_at_5')} | {v2.get('precision_at_5')} | scheme_id normalization |",
        f"| Recall@5 | {legacy.get('retrieval_recall_at_5')} | {v2.get('retrieval_recall_at_5')} | scheme_id normalization |",
        f"| Factual correctness | {legacy.get('factual_correctness')} | {v2.get('factual_correctness')} | numeric + language normalization |",
        f"| Eligibility accuracy | {legacy.get('category_accuracy', {}).get('eligibility')} | {v2.get('eligibility', {}).get('accuracy')} | polarity extraction |",
        f"| Hindi factual | {legacy.get('language_accuracy', {}).get('hi')} | {v2.get('language_accuracy', {}).get('hi')} | Indic digit normalization |",
        f"| Kannada factual | {legacy.get('language_accuracy', {}).get('kn')} | {v2.get('language_accuracy', {}).get('kn')} | Indic digit normalization |",
        f"| Unsupported detection | {legacy.get('unsupported_detection_rate')} | {v2.get('unsupported_detection_rate')} | unchanged |",
        f"| Hallucination rate | {legacy.get('hallucination_rate')} | {v2.get('hallucination_rate')} | unchanged |",
        "",
        "## 12. Classification changes",
        "",
    ]
    if not changes:
        lines.append("No primary label changes detected.")
    else:
        for item in changes:
            lines.append(
                f"- `{item['id']}` ({item['category']}): {item['old']} → {item['new']} — {', '.join(item['reasons'])}"
            )
    lines.append("")
    text = "\n".join(lines)
    RE_EVALUATED_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RE_EVALUATED_REPORT_PATH.write_text(text, encoding="utf-8")
    return text


def re_evaluate(*, results_path: Path = RESULTS_PATH) -> dict:
    if not results_path.is_file():
        raise FileNotFoundError(f"Results not found: {results_path}")

    original = _load_json(results_path)
    benchmark = _load_json(BENCHMARK_PATH)
    cases = benchmark.get("cases") or []
    raw_runs = original.get("raw_runs") or []
    if len(cases) != 100:
        raise ValueError(f"Expected 100 benchmark cases, found {len(cases)}")
    if len(raw_runs) != 100:
        raise ValueError(f"Expected 100 raw runs, found {len(raw_runs)}")

    by_id = {row["id"]: row for row in raw_runs if row.get("id")}
    if len(by_id) != 100:
        raise ValueError(f"Expected 100 unique raw run IDs, found {len(by_id)}")

    ordered_runs = [by_id[case["id"]] for case in cases]
    scored = [score_case_v2(case, run) for case, run in zip(cases, ordered_runs)]
    metrics = aggregate_scores_v2(scored)
    changes = classification_changes(scored)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "methodology_version": "v2",
        "source_results_path": str(results_path),
        "source_generated_at": original.get("generated_at"),
        "api_status": original.get("api_status"),
        "dataset": {
            "path": str(BENCHMARK_PATH),
            "n_cases": len(cases),
            "distribution": benchmark.get("distribution"),
            "source_coverage": benchmark.get("source_coverage"),
            "validation": benchmark.get("validation_summary"),
            "source_generated_at": original.get("generated_at"),
        },
        "metrics": metrics,
        "classification_changes": changes,
        "cases": scored,
    }

    RE_EVALUATED_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RE_EVALUATED_RESULTS_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_re_evaluated_report(
        dataset_meta=payload["dataset"],
        scored=scored,
        metrics=metrics,
        changes=changes,
        source_results_path=results_path,
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-evaluate saved benchmark v1 results with v2 methodology")
    parser.add_argument(
        "--results",
        type=Path,
        default=RESULTS_PATH,
        help="Path to benchmark_results.json (raw responses unchanged)",
    )
    args = parser.parse_args()
    payload = re_evaluate(results_path=args.results)
    v2 = payload["metrics"]["re_evaluated_v2"]
    print(f"Wrote {RE_EVALUATED_RESULTS_PATH}")
    print(f"Wrote {RE_EVALUATED_REPORT_PATH}")
    print(json.dumps({"re_evaluated_v2": v2, "changes": len(payload['classification_changes'])}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
