#!/usr/bin/env python3
"""Phase 3A.1 measurement-only full 100-case benchmark (separate artifacts)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PHASE3A1_RESULTS = ROOT / "evaluation" / "results" / "benchmark_v2_phase3a1.json"
PHASE3A1_CHECKPOINT = ROOT / "evaluation" / "results" / "benchmark_v2_phase3a1_checkpoint.json"
PHASE3A1_REPORT = ROOT / "evaluation" / "reports" / "benchmark_v2_phase3a1.md"
PRIOR_V2_RESULTS = ROOT / "evaluation" / "results" / "benchmark_v2.json"

import evaluation.paths as paths
import evaluation.scripts.run_benchmark_v2 as rb2

paths.BENCHMARK_V2_RESULTS_PATH = PHASE3A1_RESULTS
paths.BENCHMARK_V2_CHECKPOINT_PATH = PHASE3A1_CHECKPOINT
paths.BENCHMARK_V2_REPORT_PATH = PHASE3A1_REPORT
rb2.BENCHMARK_V2_RESULTS_PATH = PHASE3A1_RESULTS
rb2.BENCHMARK_V2_CHECKPOINT_PATH = PHASE3A1_CHECKPOINT
rb2.BENCHMARK_V2_REPORT_PATH = PHASE3A1_REPORT


def _eligibility_api_stats(payload: dict) -> dict:
    responses = rb2._raw_response_map(payload)
    elig_ids = [c["id"] for c in payload.get("cases", []) if c.get("category") == "eligibility"]
    api_populated = det_populated = null_status = 0
    for cid in elig_ids:
        resp = responses.get(cid, {})
        if resp.get("eligibility_status") is not None:
            api_populated += 1
        ev = resp.get("eligibility_evaluation") or {}
        if ev.get("status"):
            det_populated += 1
        if resp.get("eligibility_status") is None:
            null_status += 1
    return {
        "eligibility_cases": len(elig_ids),
        "api_status_populated": api_populated,
        "deterministic_eval_populated": det_populated,
        "null_eligibility_status": null_status,
    }


def write_phase3a1_report(payload: dict, *, preflight_info: dict) -> str:
    base_text = rb2.write_benchmark_v2_report(payload, preflight_info=preflight_info)
    v2 = (payload.get("metrics") or {}).get("re_evaluated_v2") or {}
    legacy = (payload.get("metrics") or {}).get("legacy_v1") or {}
    elig_stats = _eligibility_api_stats(payload)

    prior = {}
    if PRIOR_V2_RESULTS.is_file():
        prior = json.loads(PRIOR_V2_RESULTS.read_text(encoding="utf-8"))
    prior_v2 = (prior.get("metrics") or {}).get("re_evaluated_v2") or {}
    prior_legacy = (prior.get("metrics") or {}).get("legacy_v1") or {}

    extra = [
        "",
        "---",
        "",
        "## Phase 3A.1 post-run extensions",
        "",
        "### Eligibility API / deterministic coverage",
        "",
        json.dumps(elig_stats, indent=2),
        "",
        "### Baseline comparison (pre-Phase-3A.1 benchmark v2 vs this run)",
        "",
        "| Metric | Pre-3A.1 v2 | Phase 3A.1 full run | Notes |",
        "|--------|------------:|--------------------:|-------|",
        f"| HTTP success | {prior_legacy.get('success_rate', 'N/A')} | {legacy.get('success_rate')} | execution |",
        f"| Retrieval P@1 | {prior_v2.get('precision_at_1', 'N/A')} | {v2.get('precision_at_1')} | pipeline/retrieval |",
        f"| Retrieval Recall@5 | {prior_v2.get('retrieval_recall_at_5', 'N/A')} | {v2.get('retrieval_recall_at_5')} | pipeline/retrieval |",
        f"| Factual correctness | {prior_v2.get('factual_correctness', 'N/A')} | {v2.get('factual_correctness')} | mixed |",
        f"| Eligibility accuracy | {(prior_v2.get('eligibility') or {}).get('accuracy', 'N/A')} | {(v2.get('eligibility') or {}).get('accuracy')} | pipeline |",
        f"| Hallucination rate | {prior_v2.get('hallucination_rate', 'N/A')} | {v2.get('hallucination_rate')} | grounding |",
        f"| Avg latency ms | {prior_v2.get('average_latency_ms', 'N/A')} | {v2.get('average_latency_ms')} | execution |",
        "",
        "### Model vs pipeline preliminary diagnosis",
        "",
        "- **A. Retrieval/evidence**: inspect no-source cases and P@1/Recall@5 delta.",
        "- **B. Eligibility pipeline**: inspect eligibility API status coverage and deterministic eval counts.",
        "- **C. Grounding/validation**: inspect grounding-blocked count and hallucination case IDs.",
        "- **D. LLM generation**: inspect cases where validated=true but factual/eligibility labels fail.",
        "",
        f"Generated Phase 3A.1 artifacts at `{PHASE3A1_RESULTS}` and `{PHASE3A1_REPORT}`.",
        "",
    ]
    PHASE3A1_REPORT.write_text(base_text + "\n".join(extra), encoding="utf-8")
    return PHASE3A1_REPORT.read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 3A.1 full 100-case benchmark")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()

    os.environ.setdefault("GRAMSAKHI_API_BASE_URL", "http://127.0.0.1:8000")

    if args.report_only:
        if not PHASE3A1_RESULTS.is_file():
            print(f"Missing {PHASE3A1_RESULTS}", file=sys.stderr)
            return 1
        payload = json.loads(PHASE3A1_RESULTS.read_text(encoding="utf-8"))
        write_phase3a1_report(payload, preflight_info={"report_only": True})
        return 0

    pf = rb2.preflight(timeout=min(args.timeout, 60.0))
    if not pf.get("api_healthy"):
        print(json.dumps(pf, indent=2), file=sys.stderr)
        return 1
    if pf.get("dataset_cases") != 100:
        print("dataset_integrity_failed: expected 100 cases", file=sys.stderr)
        return 1
    if not pf.get("auth_ok"):
        print(json.dumps(pf, indent=2), file=sys.stderr)
        return 1

    payload = rb2.run_live_benchmark(timeout=args.timeout, resume=args.resume)
    payload["phase"] = "phase_3a1"
    payload["label"] = "Phase 3A.1 post-hardening measurement run"
    PHASE3A1_RESULTS.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_phase3a1_report(payload, preflight_info=pf)

    n = len(payload.get("raw_runs") or [])
    print(f"phase3a1_complete cases={n} results={PHASE3A1_RESULTS} report={PHASE3A1_REPORT}")
    return 0 if n == 100 else 1


if __name__ == "__main__":
    raise SystemExit(main())
