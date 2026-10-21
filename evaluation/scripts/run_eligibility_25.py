#!/usr/bin/env python3
"""Run the 25 eligibility benchmark cases against the live API (Phase 3A.1 diagnostic)."""

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

from evaluation.metrics.v2.evaluate import aggregate_scores_v2, score_case_v2
from evaluation.paths import BENCHMARK_PATH
from evaluation.runners.execute import load_benchmark, run_cases
from evaluation.scripts.run_benchmark_v2 import _bootstrap_citizen, preflight


def main() -> int:
    parser = argparse.ArgumentParser(description="Run 25 eligibility cases only")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--skip-preflight", action="store_true")
    args = parser.parse_args()

    out_results = ROOT / "evaluation" / "results" / "eligibility_25_3a1.json"
    out_report = ROOT / "evaluation" / "reports" / "eligibility_25_3a1.md"

    cases = [c for c in load_benchmark(BENCHMARK_PATH) if c.get("category") == "eligibility"]
    if len(cases) != 25:
        print(f"warning: expected 25 eligibility cases, found {len(cases)}")

    if not args.skip_preflight:
        pf = preflight(timeout=args.timeout)
        if pf.get("status") != "ok":
            print(json.dumps(pf, indent=2))
            return 1
        if pf.get("auth") == "missing":
            _bootstrap_citizen(pf.get("base_url", "http://127.0.0.1:8000"))

    runs = run_cases(cases, timeout=args.timeout)
    api_status = "ok"

    scored = [score_case_v2(case, run) for case, run in zip(cases, runs)]
    agg = aggregate_scores_v2(scored)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "label": "Phase 3A.1 targeted eligibility validation (25 cases, not full benchmark)",
        "api_status": api_status,
        "n_cases": len(cases),
        "aggregate": agg,
        "cases": scored,
        "raw_runs": runs,
    }
    out_results.parent.mkdir(parents=True, exist_ok=True)
    out_results.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    elig = agg.get("re_evaluated_v2", {}).get("eligibility") or agg.get("legacy_v1", {}).get("eligibility") or {}
    legacy = agg.get("legacy_v1") or {}
    http_ok = legacy.get("success_rate", 0)
    lines = [
        "# Phase 3A.1 — Targeted Eligibility Validation (25 cases)",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "**Diagnostic only — not a full 100-case benchmark.**",
        "",
        "## Summary",
        "",
        f"- HTTP success: {http_ok:.1%}",
        f"- Eligibility accuracy (v2): {elig.get('accuracy', 0):.1%}",
        f"- Precision: {elig.get('precision', 0):.1%}",
        f"- Recall: {elig.get('recall', 0):.1%}",
        f"- F1: {elig.get('f1', 0):.1%}",
        f"- Uncertain count: {elig.get('uncertain_count', 0)}",
        f"- Uncertain rate: {elig.get('uncertain_rate', 0):.1%}",
        f"- Eligibility scored (non-uncertain v2): {agg.get('re_evaluated_v2', {}).get('eligibility_scored_cases', 'N/A')}",
        "",
        "## Confusion matrix",
        "",
        "```json",
        json.dumps(elig.get("confusion_matrix") or {}, indent=2),
        "```",
        "",
        f"Results: `{out_results.relative_to(ROOT)}`",
    ]
    out_report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_report)
    print(json.dumps({"eligibility": elig, "n_cases": len(cases)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
