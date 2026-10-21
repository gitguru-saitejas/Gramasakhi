#!/usr/bin/env python3
"""Phase 3C targeted live validation — 18 benchmark cases."""

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

from evaluation.metrics.evaluate import unsupported_detection
from evaluation.metrics.v2.evaluate import score_case_v2
from evaluation.paths import BENCHMARK_PATH
from evaluation.runners.execute import load_benchmark, run_cases
from evaluation.scripts.run_benchmark_v2 import _bootstrap_citizen, preflight

CASE_IDS = [
    "gsb1-0066",
    "gsb1-0074",
    "gsb1-0075",
    "gsb1-0076",
    "gsb1-0078",
    "gsb1-0046",
    "gsb1-0047",
    "gsb1-0048",
    "gsb1-0049",
    "gsb1-0050",
    "gsb1-0051",
    "gsb1-0052",
    "gsb1-0055",
    "gsb1-0056",
    "gsb1-0059",
    "gsb1-0041",
    "gsb1-0043",
    "gsb1-0057",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3C targeted validation (18 cases)")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--skip-preflight", action="store_true")
    args = parser.parse_args()

    out_results = ROOT / "evaluation" / "results" / "phase3c_validation.json"
    out_report = ROOT / "evaluation" / "reports" / "phase3c_validation.md"

    all_cases = {c["id"]: c for c in load_benchmark(BENCHMARK_PATH)}
    cases = [all_cases[cid] for cid in CASE_IDS]

    if not args.skip_preflight:
        pf = preflight(timeout=min(args.timeout, 60.0))
        if not pf.get("api_healthy"):
            print(json.dumps(pf, indent=2))
            return 1
        if not pf.get("auth_ok"):
            base = os.environ.get("GRAMSAKHI_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
            _bootstrap_citizen(base)

    runs = run_cases(cases, timeout=args.timeout)
    scored = [score_case_v2(case, run) for case, run in zip(cases, runs)]

    rows = []
    for case, run, sc in zip(cases, runs, scored):
        resp = run.get("response") or {}
        uns = sc.get("unsupported") or unsupported_detection(
            str(resp.get("answer") or ""),
            (case.get("ground_truth") or {}).get("must_not_assert") or [],
            resp.get("validated"),
        )
        ev = resp.get("eligibility_evaluation") or {}
        rows.append(
            {
                "id": case["id"],
                "query": case.get("question"),
                "http_status": run.get("http_status"),
                "latency_ms": run.get("latency_ms"),
                "sources_n": len(resp.get("sources") or []),
                "validated": resp.get("validated"),
                "reason": resp.get("reason"),
                "grounding": resp.get("signals", {}).get("grounding_failure"),
                "eligibility_evaluation_status": ev.get("status"),
                "api_eligibility_status": resp.get("eligibility_status"),
                "hallucinated": uns.get("hallucinated"),
                "answer_preview": (str(resp.get("answer") or ""))[:500],
            }
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "label": "Phase 3C targeted validation (18 cases)",
        "cases": rows,
        "raw_runs": runs,
        "scored": scored,
    }
    out_results.parent.mkdir(parents=True, exist_ok=True)
    out_results.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Phase 3C — Targeted Validation (18 cases)",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "| ID | HTTP | src | validated | API elig | det status | halluc | latency |",
        "|---|---:|---:|---|---|---|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['id']} | {r['http_status']} | {r['sources_n']} | {r['validated']} | "
            f"{r.get('api_eligibility_status') or '—'} | {r.get('eligibility_evaluation_status') or '—'} | "
            f"{'YES' if r.get('hallucinated') else 'no'} | {r.get('latency_ms')} |"
        )
    lines.append(f"\nFull: `{out_results.relative_to(ROOT)}`")
    out_report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
