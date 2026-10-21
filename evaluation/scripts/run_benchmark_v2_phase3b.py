#!/usr/bin/env python3
"""Phase 3B/3B.1 measurement-only full 100-case benchmark (separate artifacts)."""

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

PHASE3B_RESULTS = ROOT / "evaluation" / "results" / "benchmark_v2_phase3b.json"
PHASE3B_CHECKPOINT = ROOT / "evaluation" / "results" / "benchmark_v2_phase3b_checkpoint.json"
PHASE3B_REPORT = ROOT / "evaluation" / "reports" / "benchmark_v2_phase3b.md"
PHASE3A1_RESULTS = ROOT / "evaluation" / "results" / "benchmark_v2_phase3a1.json"

import evaluation.paths as paths
import evaluation.scripts.run_benchmark_v2 as rb2

paths.BENCHMARK_V2_RESULTS_PATH = PHASE3B_RESULTS
paths.BENCHMARK_V2_CHECKPOINT_PATH = PHASE3B_CHECKPOINT
paths.BENCHMARK_V2_REPORT_PATH = PHASE3B_REPORT
rb2.BENCHMARK_V2_RESULTS_PATH = PHASE3B_RESULTS
rb2.BENCHMARK_V2_CHECKPOINT_PATH = PHASE3B_CHECKPOINT
rb2.BENCHMARK_V2_REPORT_PATH = PHASE3B_REPORT

REGRESSION_IDS = ("gsb1-0074", "gsb1-0075", "gsb1-0076", "gsb1-0078", "gsb1-0059")


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


def _delta(a, b):
    if a is None or b is None:
        return "n/a"
    try:
        return f"{float(a) - float(b):+.4f}"
    except (TypeError, ValueError):
        return "n/a"


def _rel_pct(a, b):
    if a is None or b is None:
        return "n/a"
    try:
        bf, af = float(b), float(a)
        if bf == 0:
            return "n/a"
        return f"{(af - bf) / bf * 100:+.1f}%"
    except (TypeError, ValueError):
        return "n/a"


def write_phase3b_report(payload: dict, *, preflight_info: dict) -> str:
    base_text = rb2.write_benchmark_v2_report(payload, preflight_info=preflight_info)
    v2 = (payload.get("metrics") or {}).get("re_evaluated_v2") or {}
    legacy = (payload.get("metrics") or {}).get("legacy_v1") or {}
    elig_stats = _eligibility_api_stats(payload)
    responses = rb2._raw_response_map(payload)
    scored = {r["id"]: r for r in payload.get("cases") or []}

    prior = {}
    if PHASE3A1_RESULTS.is_file():
        prior = json.loads(PHASE3A1_RESULTS.read_text(encoding="utf-8"))
    prior_v2 = (prior.get("metrics") or {}).get("re_evaluated_v2") or {}
    prior_legacy = (prior.get("metrics") or {}).get("legacy_v1") or {}
    prior_elig = prior_v2.get("eligibility") or {}
    elig_v2 = v2.get("eligibility") or {}

    reg_lines = ["", "### Phase 3B regression spot-checks", ""]
    for cid in REGRESSION_IDS:
        row = scored.get(cid, {})
        resp = responses.get(cid, {})
        uns = row.get("unsupported") or {}
        reg_lines.append(
            f"- `{cid}` validated={resp.get('validated')} reason={resp.get('reason')} "
            f"elig_api={resp.get('eligibility_status')} halluc={uns.get('hallucinated')} "
            f"sources={len(resp.get('sources') or [])}"
        )

    extra = [
        "",
        "---",
        "",
        "## Phase 3B/3B.1 post-run extensions",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "### Executive summary",
        "",
        "Measurement-only run after Phase 3B (RAG/evidence/grounding) and Phase 3B.1 (PMFBY eligibility).",
        "Baseline for comparison: Phase 3A.1 full benchmark (`benchmark_v2_phase3a1.json`).",
        "",
        "### Eligibility API / deterministic coverage",
        "",
        "```json",
        json.dumps(elig_stats, indent=2),
        "```",
        "",
        *reg_lines,
        "",
        "### Baseline comparison (Phase 3A.1 vs Phase 3B/3B.1)",
        "",
        "| Metric | Phase 3A.1 | Phase 3B/3B.1 | Abs Δ | Rel Δ |",
        "|--------|----------:|--------------:|------:|------:|",
        f"| HTTP success | {prior_legacy.get('success_rate')} | {legacy.get('success_rate')} | {_delta(legacy.get('success_rate'), prior_legacy.get('success_rate'))} | {_rel_pct(legacy.get('success_rate'), prior_legacy.get('success_rate'))} |",
        f"| Retrieval P@1 | {prior_v2.get('precision_at_1')} | {v2.get('precision_at_1')} | {_delta(v2.get('precision_at_1'), prior_v2.get('precision_at_1'))} | {_rel_pct(v2.get('precision_at_1'), prior_v2.get('precision_at_1'))} |",
        f"| Retrieval Recall@5 | {prior_v2.get('retrieval_recall_at_5')} | {v2.get('retrieval_recall_at_5')} | {_delta(v2.get('retrieval_recall_at_5'), prior_v2.get('retrieval_recall_at_5'))} | {_rel_pct(v2.get('retrieval_recall_at_5'), prior_v2.get('retrieval_recall_at_5'))} |",
        f"| Factual correctness | {prior_v2.get('factual_correctness')} | {v2.get('factual_correctness')} | {_delta(v2.get('factual_correctness'), prior_v2.get('factual_correctness'))} | {_rel_pct(v2.get('factual_correctness'), prior_v2.get('factual_correctness'))} |",
        f"| Eligibility accuracy | {prior_elig.get('accuracy')} | {elig_v2.get('accuracy')} | {_delta(elig_v2.get('accuracy'), prior_elig.get('accuracy'))} | {_rel_pct(elig_v2.get('accuracy'), prior_elig.get('accuracy'))} |",
        f"| Eligibility F1 | {prior_elig.get('f1')} | {elig_v2.get('f1')} | {_delta(elig_v2.get('f1'), prior_elig.get('f1'))} | {_rel_pct(elig_v2.get('f1'), prior_elig.get('f1'))} |",
        f"| Eligibility uncertain rate | {prior_elig.get('uncertain_rate')} | {elig_v2.get('uncertain_rate')} | {_delta(elig_v2.get('uncertain_rate'), prior_elig.get('uncertain_rate'))} | lower-is-better |",
        f"| Unsupported detection | {prior_v2.get('unsupported_detection_rate')} | {v2.get('unsupported_detection_rate')} | {_delta(v2.get('unsupported_detection_rate'), prior_v2.get('unsupported_detection_rate'))} | — |",
        f"| Hallucination rate | {prior_v2.get('hallucination_rate')} | {v2.get('hallucination_rate')} | {_delta(v2.get('hallucination_rate'), prior_v2.get('hallucination_rate'))} | lower-is-better |",
        f"| Avg latency ms | {prior_v2.get('average_latency_ms')} | {v2.get('average_latency_ms')} | {_delta(v2.get('average_latency_ms'), prior_v2.get('average_latency_ms'))} | — |",
        f"| P95 latency ms | {prior_v2.get('p95_latency_ms')} | {v2.get('p95_latency_ms')} | {_delta(v2.get('p95_latency_ms'), prior_v2.get('p95_latency_ms'))} | — |",
        "",
        f"Artifacts: `{PHASE3B_RESULTS}` and `{PHASE3B_REPORT}`.",
        "",
    ]
    PHASE3B_REPORT.write_text(base_text + "\n".join(extra), encoding="utf-8")
    return PHASE3B_REPORT.read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 3B/3B.1 full 100-case benchmark")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()

    os.environ.setdefault("GRAMSAKHI_API_BASE_URL", "http://127.0.0.1:8000")

    if args.report_only:
        if not PHASE3B_RESULTS.is_file():
            print(f"Missing {PHASE3B_RESULTS}", file=sys.stderr)
            return 1
        payload = json.loads(PHASE3B_RESULTS.read_text(encoding="utf-8"))
        write_phase3b_report(payload, preflight_info={"report_only": True})
        return 0

    pf = rb2.preflight(timeout=min(args.timeout, 60.0))
    print(json.dumps(pf, indent=2, default=str), flush=True)
    if not pf.get("api_healthy"):
        return 1
    if pf.get("dataset_cases") != 100:
        print("dataset_integrity_failed: expected 100 cases", file=sys.stderr)
        return 1
    if not pf.get("auth_ok"):
        rb2._bootstrap_citizen(os.environ.get("GRAMSAKHI_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/"))
        client = rb2._auth_client(min(args.timeout, 60.0))
        if client.probe_auth() != "configured":
            print("auth_failed after bootstrap", file=sys.stderr)
            return 1

    payload = rb2.run_live_benchmark(timeout=args.timeout, resume=args.resume)
    payload["phase"] = "phase_3b_3b1"
    payload["label"] = "Phase 3B/3B.1 post-hardening measurement run"
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    PHASE3B_RESULTS.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_phase3b_report(payload, preflight_info=pf)

    n = len(payload.get("raw_runs") or [])
    print(f"phase3b_complete cases={n} results={PHASE3B_RESULTS} report={PHASE3B_REPORT}")
    return 0 if n == 100 else 1


if __name__ == "__main__":
    raise SystemExit(main())
