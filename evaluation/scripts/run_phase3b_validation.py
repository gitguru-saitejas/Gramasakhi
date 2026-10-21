#!/usr/bin/env python3
"""Phase 3B targeted live validation — 19 benchmark cases (not full 100-case run)."""

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

PHASE3B_CASE_IDS = [
    # A — hallucination / grounding (4)
    "gsb1-0074",
    "gsb1-0076",
    "gsb1-0078",
    "gsb1-0075",
    # B — eligibility evidence (10)
    "gsb1-0041",
    "gsb1-0043",
    "gsb1-0046",
    "gsb1-0047",
    "gsb1-0048",
    "gsb1-0049",
    "gsb1-0050",
    "gsb1-0051",
    "gsb1-0057",
    "gsb1-0059",
    # C — retrieval / evidence (5): PMSBY, PMFBY, Gruha Lakshmi, cross-scheme, no-source
    "gsb1-0030",
    "gsb1-0001",
    "gsb1-0052",
    "gsb1-0077",
    "gsb1-0081",
]

ORDERED_IDS = PHASE3B_CASE_IDS


def _classify_failure(row: dict) -> str:
    resp = row.get("response") or {}
    validated = resp.get("validated")
    sources_n = len(resp.get("sources") or [])
    reason = str(resp.get("reason") or "")
    unsup = row.get("unsupported") or {}
    if unsup.get("hallucinated"):
        return "hallucination"
    if validated is False and sources_n == 0:
        if "query_too_short" in reason:
            return "query_too_short"
        return "no_evidence"
    if validated is False:
        return "validation_failure"
    elig = row.get("eligibility") or {}
    if elig.get("label") == "incorrect":
        return "eligibility_incorrect"
    return "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3B targeted validation (19 cases)")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument(
        "--ids",
        nargs="*",
        help="Optional subset of benchmark case ids (default: full Phase 3B set)",
    )
    parser.add_argument(
        "--baseline",
        default=str(ROOT / "evaluation" / "results" / "benchmark_v2_phase3a1.json"),
        help="Prior benchmark artifact for before/after comparison",
    )
    args = parser.parse_args()

    out_results = ROOT / "evaluation" / "results" / "phase3b_validation.json"
    out_report = ROOT / "evaluation" / "reports" / "phase3b_validation.md"

    all_cases = {c["id"]: c for c in load_benchmark(BENCHMARK_PATH)}
    id_list = args.ids if args.ids else ORDERED_IDS
    missing = [cid for cid in id_list if cid not in all_cases]
    if missing:
        print(f"error: missing benchmark ids: {missing}")
        return 1
    cases = [all_cases[cid] for cid in id_list]

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

    baseline_by_id: dict[str, dict] = {}
    baseline_path = Path(args.baseline)
    if baseline_path.is_file():
        try:
            baseline_data = json.loads(baseline_path.read_text(encoding="utf-8"))
            for row in baseline_data.get("cases") or []:
                baseline_by_id[row.get("id")] = row
        except Exception as exc:  # noqa: BLE001
            print(f"warning: could not load baseline: {exc}")

    case_reports = []
    for case, run, scored_row in zip(cases, runs, scored):
        resp = run.get("response") or {}
        sources = resp.get("sources") or []
        unsup = scored_row.get("unsupported") or unsupported_detection(
            str(resp.get("answer") or ""),
            (case.get("ground_truth") or {}).get("must_not_assert") or [],
            resp.get("validated"),
        )
        case_reports.append(
            {
                "id": case["id"],
                "category": case.get("category"),
                "scheme": case.get("scheme"),
                "question": case.get("question"),
                "sources_n": len(sources),
                "source_titles": [
                    s.get("title") or s.get("scheme_name") or s.get("source") for s in sources[:5]
                ],
                "validated": resp.get("validated"),
                "reason": resp.get("reason"),
                "eligibility_status": resp.get("eligibility_status"),
                "unsupported": unsup,
                "factual": scored_row.get("factual"),
                "eligibility": scored_row.get("eligibility"),
                "latency_ms": run.get("latency_ms"),
                "answer_preview": (str(resp.get("answer") or ""))[:400],
                "failure_classification": _classify_failure({**scored_row, "response": resp}),
                "baseline": {
                    "validated": (baseline_by_id.get(case["id"]) or {}).get("validated"),
                    "sources_n": (baseline_by_id.get(case["id"]) or {}).get("retrieval", {}).get("sources_n"),
                    "eligibility_status": (baseline_by_id.get(case["id"]) or {}).get("eligibility_status"),
                },
            }
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "label": "Phase 3B targeted validation (19 cases — not full benchmark)",
        "n_cases": len(cases),
        "case_ids": id_list,
        "cases": case_reports,
        "raw_runs": runs,
        "scored": scored,
    }
    out_results.parent.mkdir(parents=True, exist_ok=True)
    out_results.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Phase 3B — Targeted Validation (19 cases)",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "**Not a full 100-case benchmark.**",
        "",
        "## Per-case summary",
        "",
        "| ID | sources | validated | elig | halluc | latency | failure |",
        "|---|---:|---|---|---|---:|---|",
    ]
    for row in case_reports:
        uns = row["unsupported"]
        hall = "YES" if uns.get("hallucinated") else "no"
        lines.append(
            f"| {row['id']} | {row['sources_n']} | {row['validated']} | "
            f"{row.get('eligibility_status') or '—'} | {hall} | {row.get('latency_ms')} | "
            f"{row['failure_classification']} |"
        )
    lines.extend(["", f"Full results: `{out_results.relative_to(ROOT)}`"])
    out_report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_report)
    print(json.dumps({"n_cases": len(cases), "ids": ORDERED_IDS}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
