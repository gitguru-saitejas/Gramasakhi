#!/usr/bin/env python3
"""Execute Benchmark v2: fresh 100-case live API run + v2 evaluation + report."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import dotenv_values

from evaluation.metrics.v2.evaluate import aggregate_scores_v2, classification_changes, score_case_v2
from evaluation.paths import (
    BENCHMARK_PATH,
    BENCHMARK_V2_CHECKPOINT_PATH,
    BENCHMARK_V2_REPORT_PATH,
    BENCHMARK_V2_RESULTS_PATH,
    RE_EVALUATED_RESULTS_PATH,
)
from evaluation.runners.api_client import GramSakhiClient, _request
from evaluation.runners.execute import _auth_client, load_benchmark, run_cases, save_checkpoint


def _load_dev_otp_key() -> str:
    vals = dotenv_values(ROOT / "backend" / ".env")
    enabled = str(vals.get("OTP_DEV_RETRIEVAL_ENABLED") or "").strip().lower()
    key = (vals.get("OTP_DEV_RETRIEVAL_KEY") or "").strip()
    if enabled not in {"1", "true", "yes"} or not key:
        raise SystemExit("otp_dev_retrieval_unavailable")
    return key


def _bootstrap_citizen(base: str) -> None:
    phone = f"98{int(time.time()) % 10_000_000:08d}"[:10]
    password = f"Bench{int(time.time())}Aa1!"
    key = _load_dev_otp_key()
    status, body, _ = _request("POST", f"{base}/api/auth/otp/send", payload={"phone_number": phone}, timeout=20)
    if status >= 400:
        raise SystemExit(f"otp_send_failed http={status}")
    status, body, _ = _request(
        "GET",
        f"{base}/api/auth/otp/dev?phone_number={phone}",
        headers={"X-Dev-OTP-Key": key},
        timeout=20,
    )
    code = (body or {}).get("otp")
    if status >= 400 or not code:
        raise SystemExit(f"otp_dev_failed http={status}")
    status, body, _ = _request(
        "POST",
        f"{base}/api/auth/otp/verify",
        payload={"phone_number": phone, "code": code},
        timeout=20,
    )
    if status >= 400:
        raise SystemExit(f"otp_verify_failed http={status}")
    status, body, _ = _request(
        "POST",
        f"{base}/api/auth/register",
        payload={"credentials": {"phone_number": phone, "password": password}, "display_name": "Benchmark V2 Citizen"},
        timeout=20,
    )
    if status >= 400:
        raise SystemExit(f"register_failed http={status}")
    from evaluation.runners.api_client import extract_access_token

    token = extract_access_token(body if isinstance(body, dict) else {})
    if not token:
        raise SystemExit("register_missing_access_token")
    os.environ["GRAMSAKHI_BENCH_PHONE"] = phone
    os.environ["GRAMSAKHI_BENCH_PASSWORD"] = password
    os.environ["GRAMSAKHI_BENCH_TOKEN"] = token
    client = GramSakhiClient(base_url=base, token=token)
    if client.probe_auth() != "configured":
        raise SystemExit("probe_failed after bootstrap")


def _load_v2_checkpoint() -> Dict[str, Dict[str, Any]]:
    if not BENCHMARK_V2_CHECKPOINT_PATH.is_file():
        return {}
    try:
        payload = json.loads(BENCHMARK_V2_CHECKPOINT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {row["id"]: row for row in payload.get("raw_runs") or [] if row.get("id")}


def _save_v2_checkpoint(runs: List[Dict[str, Any]], *, api_status: str = "") -> None:
    BENCHMARK_V2_CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    BENCHMARK_V2_CHECKPOINT_PATH.write_text(
        json.dumps(
            {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "api_status": api_status,
                "n_runs": len(runs),
                "raw_runs": runs,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _run_v2_checkpoint(runs: List[Dict[str, Any]], *, api_status: str = "") -> None:
    _save_v2_checkpoint(runs, api_status=api_status)


def preflight(*, timeout: float = 30.0) -> Dict[str, Any]:
    base = os.environ.get("GRAMSAKHI_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    client = GramSakhiClient(base_url=base, timeout=timeout)
    healthy, detail = client.health()
    ollama_ok = False
    ollama_detail = ""
    try:
        status, body, _ = _request("GET", "http://127.0.0.1:11434/api/tags", timeout=10.0)
        ollama_ok = status == 200
        ollama_detail = str(body)[:200]
    except Exception as exc:  # noqa: BLE001
        ollama_detail = str(exc)

    dataset = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    cases = dataset.get("cases") or []
    auth_ok = False
    auth_detail = "not_attempted"
    if healthy:
        if not (os.environ.get("GRAMSAKHI_BENCH_PHONE") and os.environ.get("GRAMSAKHI_BENCH_PASSWORD")):
            if not os.environ.get("GRAMSAKHI_BENCH_TOKEN"):
                _bootstrap_citizen(base)
        try:
            client = _auth_client(timeout)
            auth_detail = client.probe_auth()
            auth_ok = auth_detail == "configured"
        except Exception as exc:  # noqa: BLE001
            auth_detail = str(exc)

    return {
        "api_healthy": healthy,
        "api_detail": detail,
        "ollama_healthy": ollama_ok,
        "ollama_detail": ollama_detail,
        "auth_ok": auth_ok,
        "auth_detail": auth_detail,
        "dataset_path": str(BENCHMARK_PATH),
        "dataset_cases": len(cases),
        "dataset_distribution": dataset.get("distribution"),
    }


def run_live_benchmark(*, timeout: float = 300.0, resume: bool = False) -> Dict[str, Any]:
    dataset = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    cases = list(dataset.get("cases") or [])
    if len(cases) != 100:
        raise ValueError(f"Expected 100 benchmark cases, found {len(cases)}")

    prior = _load_v2_checkpoint() if resume else {}
    prior_runs = list(prior.values())
    done_ids = set(prior.keys())
    todo = [c for c in cases if c["id"] not in done_ids]

    base = os.environ.get("GRAMSAKHI_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    client = GramSakhiClient(base_url=base, timeout=timeout)
    healthy, detail = client.health()
    if not healthy:
        raise SystemExit(f"API unreachable: {detail}")

    if not (os.environ.get("GRAMSAKHI_BENCH_PHONE") and os.environ.get("GRAMSAKHI_BENCH_PASSWORD")):
        if not os.environ.get("GRAMSAKHI_BENCH_TOKEN"):
            _bootstrap_citizen(base)

    client = _auth_client(timeout)
    auth_state = client.probe_auth()
    api_status = f"healthy auth_{auth_state} base={base} phase=2"

    runs = list(prior_runs)
    if todo:
        print(f"benchmark_v2 pending={len(todo)} completed={len(prior_runs)} total=100", flush=True)

        def _checkpoint_wrapper(current: List[Dict[str, Any]], *, api_status: str = "") -> None:
            _run_v2_checkpoint(current, api_status=api_status)

        # Monkey-patch save_checkpoint for v2 path during this run
        import evaluation.runners.execute as execute_mod

        original_save = execute_mod.save_checkpoint
        execute_mod.save_checkpoint = lambda runs, api_status="": _run_v2_checkpoint(runs, api_status=api_status)
        try:
            if not prior_runs:
                preflight_run = run_cases(todo[:1], client=client, timeout=timeout, api_status=api_status, checkpoint=True)
                if not preflight_run[0].get("ok"):
                    raise SystemExit(
                        f"preflight_failed http={preflight_run[0].get('http_status')} err={preflight_run[0].get('error')}"
                    )
                runs = run_cases(
                    todo[1:],
                    client=client,
                    timeout=timeout,
                    prior_runs=preflight_run,
                    api_status=api_status,
                    checkpoint=True,
                )
            else:
                runs = run_cases(
                    todo,
                    client=client,
                    timeout=timeout,
                    prior_runs=prior_runs,
                    api_status=api_status,
                    checkpoint=True,
                )
        finally:
            execute_mod.save_checkpoint = original_save

    by_id = {row["id"]: row for row in runs if row.get("id")}
    ordered_runs = [by_id.get(c["id"], {"id": c["id"], "ok": False, "error": "not_run"}) for c in cases]

    scored = [score_case_v2(case, run) for case, run in zip(cases, ordered_runs)]
    metrics = aggregate_scores_v2(scored)
    changes = classification_changes(scored)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_version": "v2",
        "phase": "phase_2_production",
        "methodology_version": "v2",
        "api_status": api_status,
        "dataset": {
            "path": str(BENCHMARK_PATH),
            "n_cases": len(cases),
            "distribution": dataset.get("distribution"),
            "source_coverage": dataset.get("source_coverage"),
            "validation": dataset.get("validation_summary"),
        },
        "metrics": metrics,
        "classification_changes": changes,
        "cases": scored,
        "raw_runs": ordered_runs,
    }
    BENCHMARK_V2_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    BENCHMARK_V2_RESULTS_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def _baseline_metrics() -> Dict[str, Any]:
    if not RE_EVALUATED_RESULTS_PATH.is_file():
        return {}
    data = json.loads(RE_EVALUATED_RESULTS_PATH.read_text(encoding="utf-8"))
    return data.get("metrics") or {}


def _find_case(scored: List[Dict[str, Any]], case_id: str) -> Optional[Dict[str, Any]]:
    for row in scored:
        if row.get("id") == case_id:
            return row
    return None


def _raw_response_map(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for row in payload.get("raw_runs") or []:
        cid = row.get("id")
        if cid:
            out[cid] = row.get("response") or {}
    return out


def _grounding_blocked_cases(scored: List[Dict[str, Any]], responses: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    blocked = []
    grounding_reasons = {
        "domain_mismatch",
        "unsupported_numeric_fact",
        "unsupported_scope_claim",
        "unsupported_claim",
        "answer_domain_mismatch",
        "answer_unsupported_amount",
        "answer_unsupported_scope",
    }
    for row in scored:
        cid = row.get("id")
        resp = responses.get(cid or "", {})
        reason = str(resp.get("reason") or "")
        validated = resp.get("validated")
        signals = resp.get("signals") or {}
        claim_support = (signals.get("claim_support") or {}) if isinstance(signals, dict) else {}
        grounding = (signals.get("grounding_failure") or {}) if isinstance(signals, dict) else {}
        if validated is False and (
            reason in grounding_reasons
            or claim_support.get("reason") in grounding_reasons
            or grounding.get("reason") in grounding_reasons
        ):
            blocked.append(
                {
                    "id": cid,
                    "reason": reason or claim_support.get("reason") or grounding.get("reason"),
                    "category": row.get("category"),
                    "answer_preview": str(resp.get("answer") or "")[:200],
                }
            )
    return blocked


def write_benchmark_v2_report(payload: Dict[str, Any], *, preflight_info: Dict[str, Any]) -> str:
    scored = payload.get("cases") or []
    responses = _raw_response_map(payload)
    metrics = payload.get("metrics") or {}
    v2 = metrics.get("re_evaluated_v2") or {}
    legacy = metrics.get("legacy_v1") or {}
    baseline = _baseline_metrics()
    base_v2 = (baseline.get("re_evaluated_v2") or {}) if baseline else {}

    latencies = [row["latency_ms"] for row in scored if isinstance(row.get("latency_ms"), (int, float))]
    blocked = _grounding_blocked_cases(scored, responses)

    hist_ids = ["gsb1-0074", "gsb1-0076", "gsb1-0078"]
    hist_sections = []
    for cid in hist_ids:
        row = _find_case(scored, cid)
        if not row:
            hist_sections.append(f"### `{cid}`\n\nNot found in results.\n")
            continue
        resp = responses.get(cid, {})
        signals = resp.get("signals") or {}
        hist_sections.append(
            "\n".join(
                [
                    f"### `{cid}`",
                    "",
                    f"- Question: {row.get('question', 'N/A')[:200]}",
                    f"- HTTP ok: {row.get('ok')}",
                    f"- validated: {resp.get('validated')}",
                    f"- reason: {resp.get('reason')}",
                    f"- eligibility_status: {resp.get('eligibility_status')}",
                    f"- sources count: {len(resp.get('sources') or [])}",
                    f"- claim_support: {json.dumps(signals.get('claim_support') or {}, default=str)[:300]}",
                    f"- grounding_failure: {json.dumps(signals.get('grounding_failure') or {}, default=str)[:300]}",
                    f"- answer preview: {str(resp.get('answer') or '')[:400]}",
                    f"- hallucinated (legacy): {row.get('unsupported', {}).get('hallucinated')}",
                    "",
                ]
            )
        )

    elig_rows = [r for r in scored if r.get("category") == "eligibility"]
    elig_third_person = [
        r
        for r in elig_rows
        if r.get("question")
        and any(
            p in str(r.get("question")).lower()
            for p in ("a man", "a woman", "is he", "is she", "head of family", "asks for")
        )
    ]

    over_block = blocked

    def _delta(new: Any, old: Any) -> str:
        if old in (None, "N/A", ""):
            return "no baseline"
        if new == old:
            return "unchanged"
        try:
            if float(new) > float(old):
                return "improved"
            if float(new) < float(old):
                return "regression"
        except (TypeError, ValueError):
            pass
        return "changed"

    recommendation = "READY FOR NEXT PHASE"
    regressions: List[str] = []
    if v2.get("hallucination_rate", 0) and v2.get("hallucination_rate", 0) > 0.05:
        if len(v2.get("hallucination_case_ids") or []) > 0:
            regressions.append("residual_hallucinations")
    if legacy.get("success_rate", 1) < 0.95:
        regressions.append("http_failures")
    if len(over_block) > 15:
        regressions.append("possible_over_blocking")
    if regressions:
        recommendation = "NEEDS TARGETED FIXES" if len(regressions) < 3 else "MAJOR REGRESSION — STOP"

    lines = [
        "# GramSakhi Benchmark v2 Report (Phase 2 Live API)",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"Results artifact: `{BENCHMARK_V2_RESULTS_PATH}`",
        f"API status: {payload.get('api_status')}",
        "",
        "## 1. Executive summary",
        "",
        f"- Cases executed: **{len(scored)}**",
        f"- HTTP success rate: **{legacy.get('success_rate')}**",
        f"- Phase 2 production API with v2 evaluation methodology",
        f"- Grounding-blocked responses: **{len(blocked)}**",
        f"- Hallucination cases: **{v2.get('hallucination_case_ids')}**",
        f"- Recommendation: **{recommendation}**",
        "",
        "## 2. Environment / pre-flight",
        "",
        json.dumps(preflight_info, indent=2, default=str),
        "",
        "## 3. Dataset integrity",
        "",
        f"- Path: `{BENCHMARK_PATH}`",
        f"- Cases: {payload.get('dataset', {}).get('n_cases')}",
        "- Dataset file was not modified for this run.",
        "",
        json.dumps(payload.get("dataset", {}).get("distribution") or {}, indent=2),
        "",
        "## 4. Overall benchmark results",
        "",
        json.dumps({k: v for k, v in legacy.items() if k not in ("failed_case_ids",)}, indent=2, default=str),
        "",
        "## 5. Retrieval (v2 methodology)",
        "",
        f"- Evaluable: {v2.get('retrieval_evaluable_cases')}",
        f"- No-source: {v2.get('retrieval_no_source_cases')}",
        f"- Unevaluated: {v2.get('retrieval_unevaluated_cases')}",
        f"- P@1: {v2.get('precision_at_1')}",
        f"- P@3: {v2.get('precision_at_3')}",
        f"- P@5: {v2.get('precision_at_5')}",
        f"- Recall@5: {v2.get('retrieval_recall_at_5')}",
        "",
        "_Unevaluated cases occur when ground truth lacks expected scheme_id._",
        "",
        "## 6. Factual (v2)",
        "",
        f"- Overall correctness: {v2.get('factual_correctness')}",
        f"- Full correct: {v2.get('factual_full_correct')} / {v2.get('factual_evaluated')}",
        f"- Partial: {v2.get('factual_partial')}",
        f"- Semantic review required: {v2.get('factual_semantic_review_required')}",
        "",
        "## 7. Multilingual (v2)",
        "",
        json.dumps(v2.get("language_accuracy") or {}, indent=2),
        "",
        json.dumps(v2.get("language_semantic_review_required") or {}, indent=2),
        "",
        "## 8. Eligibility (v2)",
        "",
        json.dumps(v2.get("eligibility") or {}, indent=2),
        "",
        f"- Scored cases: {v2.get('eligibility_scored_cases')}",
        f"- Uncertain cases: {v2.get('eligibility_uncertain_cases')}",
        "",
        "### Third-person scenario cases",
        "",
    ]
    for r in elig_third_person[:15]:
        ev2 = r.get("eligibility_v2") or {}
        resp = responses.get(r.get("id") or "", {})
        lines.append(
            f"- `{r.get('id')}` expected={ev2.get('expected')} predicted={ev2.get('predicted_polarity')} "
            f"api_status={resp.get('eligibility_status')} score={ev2.get('score')}"
        )
    lines.extend(
        [
            "",
            "## 9. Unsupported-query results",
            "",
            f"- Detection rate: {v2.get('unsupported_detection_rate')}",
            "",
            "## 10. Hallucination results",
            "",
            f"- Rate: {v2.get('hallucination_rate')}",
            f"- Cases: {v2.get('hallucination_case_ids')}",
            f"- Grounding-blocked (Phase 2 gates): {len(blocked)}",
            "",
            "### Grounding-blocked responses",
            "",
        ]
    )
    if not blocked:
        lines.append("None detected via reason/signal inspection.")
    else:
        for item in blocked:
            lines.append(f"- `{item['id']}` reason={item['reason']} cat={item['category']}")
    lines.extend(
        [
            "",
            "## 11. Latency",
            "",
            f"- Average ms: {v2.get('average_latency_ms')}",
            f"- P50 ms: {v2.get('p50_latency_ms')}",
            f"- P95 ms: {v2.get('p95_latency_ms')}",
            f"- Max ms: {max(latencies) if latencies else 'N/A'}",
            "",
            "## 12. Historical hallucination regression",
            "",
            *hist_sections,
            "",
            "## 13. Eligibility regression analysis",
            "",
            f"- Total eligibility cases: {len(elig_rows)}",
            f"- Third-person scenarios inspected: {len(elig_third_person)}",
            "",
            "## 14. Over-blocking / false-positive analysis",
            "",
        ]
    )
    if not over_block:
        lines.append("No Phase 2 grounding refusals detected by reason-code scan.")
    else:
        for item in over_block[:30]:
            lines.append(
                f"- `{item['id']}` ({item['category']}) reason={item['reason']} — {item['answer_preview'][:120]}"
            )
    lines.extend(
        [
            "",
            "## 15. v1 baseline vs Benchmark v2 comparison",
            "",
            "| Metric | v1 baseline (pre-Phase-2 API, v2 eval) | Benchmark v2 (Phase-2 API, v2 eval) | Delta type |",
            "|--------|---------------------------------------:|------------------------------------:|------------|",
            f"| HTTP success | {base_v2.get('success_rate', legacy.get('success_rate'))} | {legacy.get('success_rate')} | execution |",
            f"| Retrieval P@1 | {base_v2.get('precision_at_1')} | {v2.get('precision_at_1')} | {_delta(v2.get('precision_at_1'), base_v2.get('precision_at_1'))} |",
            f"| Factual correctness | {base_v2.get('factual_correctness')} | {v2.get('factual_correctness')} | {_delta(v2.get('factual_correctness'), base_v2.get('factual_correctness'))} |",
            f"| Eligibility accuracy | {(base_v2.get('eligibility') or {}).get('accuracy')} | {(v2.get('eligibility') or {}).get('accuracy')} | {_delta((v2.get('eligibility') or {}).get('accuracy'), (base_v2.get('eligibility') or {}).get('accuracy'))} |",
            f"| Unsupported detection | {base_v2.get('unsupported_detection_rate')} | {v2.get('unsupported_detection_rate')} | {_delta(v2.get('unsupported_detection_rate'), base_v2.get('unsupported_detection_rate'))} |",
            f"| Hallucination rate | {base_v2.get('hallucination_rate')} | {v2.get('hallucination_rate')} | {_delta(v2.get('hallucination_rate'), base_v2.get('hallucination_rate'))} |",
            f"| Avg latency ms | {base_v2.get('average_latency_ms')} | {v2.get('average_latency_ms')} | execution |",
            "",
            "**Legend:** metric correction = evaluator fix only; improved/regression = Phase 2 API behavior change.",
            "",
            "## 16. Remaining limitations",
            "",
            "- v2 retrieval uses scheme_id identity, not chunk relevance.",
            "- Eligibility polarity extraction is deterministic.",
            "- Unsupported/hallucination metrics use legacy v1 detector.",
            "- Local Ollama latency not production representative.",
            "",
            "## 17. Final recommendation",
            "",
            f"**{recommendation}**",
            "",
            f"Evidence: HTTP success={legacy.get('success_rate')}, hallucinations={v2.get('hallucination_case_ids')}, "
            f"grounding_blocked={len(blocked)}, eligibility_accuracy={(v2.get('eligibility') or {}).get('accuracy')}.",
            "",
        ]
    )
    text = "\n".join(lines) + "\n"
    BENCHMARK_V2_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    BENCHMARK_V2_REPORT_PATH.write_text(text, encoding="utf-8")
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Benchmark v2 (Phase 2 live API)")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--resume", action="store_true", help="Resume from benchmark_v2_checkpoint.json")
    parser.add_argument("--report-only", action="store_true", help="Regenerate report from existing benchmark_v2.json")
    args = parser.parse_args()

    os.environ.setdefault("GRAMSAKHI_API_BASE_URL", "http://127.0.0.1:8000")

    if args.report_only:
        if not BENCHMARK_V2_RESULTS_PATH.is_file():
            print(f"Missing {BENCHMARK_V2_RESULTS_PATH}", file=sys.stderr)
            return 1
        payload = json.loads(BENCHMARK_V2_RESULTS_PATH.read_text(encoding="utf-8"))
        write_benchmark_v2_report(payload, preflight_info={"report_only": True})
        print(f"Wrote {BENCHMARK_V2_REPORT_PATH}")
        return 0

    pf = preflight(timeout=min(args.timeout, 30.0))
    print(json.dumps(pf, indent=2, default=str), flush=True)
    if not pf["api_healthy"]:
        return 1
    if not pf["auth_ok"]:
        print(f"Auth failed: {pf['auth_detail']}", file=sys.stderr)
        return 1
    if pf["dataset_cases"] != 100:
        print(f"Dataset case count mismatch: {pf['dataset_cases']}", file=sys.stderr)
        return 1

    payload = run_live_benchmark(timeout=args.timeout, resume=args.resume)
    write_benchmark_v2_report(payload, preflight_info=pf)
    v2 = payload["metrics"]["re_evaluated_v2"]
    print(f"Wrote {BENCHMARK_V2_RESULTS_PATH}")
    print(f"Wrote {BENCHMARK_V2_REPORT_PATH}")
    print(
        json.dumps(
            {
                "success_rate": payload["metrics"]["legacy_v1"].get("success_rate"),
                "hallucination_case_ids": v2.get("hallucination_case_ids"),
                "eligibility_accuracy": (v2.get("eligibility") or {}).get("accuracy"),
                "precision_at_1": v2.get("precision_at_1"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
