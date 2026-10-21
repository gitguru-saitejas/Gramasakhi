"""Run benchmark_v1 against the existing GramSakhi API and write reports."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from evaluation.metrics.evaluate import aggregate_scores, score_case
from evaluation.paths import BENCHMARK_PATH, CHECKPOINT_PATH, RESULTS_PATH, RUN_REPORT_PATH
from evaluation.runners.api_client import GramSakhiApiError, GramSakhiClient


def load_benchmark(path=BENCHMARK_PATH) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload.get("cases") or [])


def _login_if_configured(client: GramSakhiClient) -> bool:
    phone = (os.environ.get("GRAMSAKHI_BENCH_PHONE") or "").strip()
    password = os.environ.get("GRAMSAKHI_BENCH_PASSWORD")
    if phone and password:
        client.login(phone, password)
        return True
    return False


def _auth_client(timeout: float) -> GramSakhiClient:
    client = GramSakhiClient(timeout=timeout)
    status = client.probe_auth() if client.token else "missing"
    if status == "configured":
        return client
    if status in ("expired", "invalid", "missing"):
        if _login_if_configured(client):
            refreshed = client.probe_auth()
            if refreshed != "configured":
                raise GramSakhiApiError(
                    f"login produced a {refreshed} citizen token; check phone/password and that the account is active"
                )
            return client
        if status == "expired":
            raise GramSakhiApiError(
                "expired: GRAMSAKHI_BENCH_TOKEN is expired. Log in as a citizen and set a fresh token, "
                "or set GRAMSAKHI_BENCH_PHONE and GRAMSAKHI_BENCH_PASSWORD."
            )
        if status == "invalid":
            raise GramSakhiApiError(
                "invalid: GRAMSAKHI_BENCH_TOKEN was rejected by the API. Set a fresh citizen JWT "
                "or GRAMSAKHI_BENCH_PHONE and GRAMSAKHI_BENCH_PASSWORD."
            )
    raise GramSakhiApiError(
        "missing: set GRAMSAKHI_BENCH_TOKEN or GRAMSAKHI_BENCH_PHONE + GRAMSAKHI_BENCH_PASSWORD"
    )


def load_checkpoint() -> Dict[str, Dict[str, Any]]:
    if not CHECKPOINT_PATH.is_file():
        return {}
    try:
        payload = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {row["id"]: row for row in payload.get("raw_runs") or [] if row.get("id")}


def save_checkpoint(runs: List[Dict[str, Any]], *, api_status: str = "") -> None:
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(
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


def pending_cases(
    cases: List[Dict[str, Any]],
    done_ids: Optional[set] = None,
    start_after: Optional[str] = None,
) -> List[Dict[str, Any]]:
    skip = set(done_ids or ())
    started = start_after is None
    pending: List[Dict[str, Any]] = []
    for case in cases:
        if not started:
            if case.get("id") == start_after:
                started = True
            continue
        if case.get("id") in skip:
            continue
        pending.append(case)
    return pending


def run_cases(
    cases: List[Dict[str, Any]],
    *,
    client: Optional[GramSakhiClient] = None,
    timeout: float = 180.0,
    prior_runs: Optional[List[Dict[str, Any]]] = None,
    api_status: str = "",
    checkpoint: bool = False,
) -> List[Dict[str, Any]]:
    active = client or _auth_client(timeout)
    runs: List[Dict[str, Any]] = list(prior_runs or [])
    for case in cases:
        record: Dict[str, Any] = {
            "id": case["id"],
            "question": case["question"],
            "language": case.get("language"),
            "category": case.get("category"),
        }
        try:
            body, latency_ms, status = active.chat(case["question"], language=case.get("language"))
            record.update(
                {
                    "ok": 200 <= status < 300,
                    "http_status": status,
                    "latency_ms": latency_ms,
                    "response": body,
                    "error": None if 200 <= status < 300 else body.get("detail") or body.get("error"),
                }
            )
            print(
                f"bench_case id={case['id']} http={status} ok={record['ok']} latency_ms={record['latency_ms']}",
                flush=True,
            )
        except GramSakhiApiError as exc:
            record.update(
                {
                    "ok": False,
                    "http_status": exc.status,
                    "latency_ms": None,
                    "response": {},
                    "error": str(exc),
                }
            )
            print(
                f"bench_case id={case['id']} http={record.get('http_status')} ok={record['ok']} error={record.get('error')}",
                flush=True,
            )
        runs.append(record)
        if checkpoint:
            save_checkpoint(runs, api_status=api_status)
    return runs


def write_report(
    *,
    dataset_meta: Dict[str, Any],
    scored: List[Dict[str, Any]],
    metrics: Dict[str, Any],
    api_status: str,
) -> str:
    lines = [
        "# GramSakhi Benchmark v1 report",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"API status: {api_status}",
        "",
        "## Dataset composition",
        "",
        json.dumps(dataset_meta.get("distribution") or {}, indent=2, ensure_ascii=False),
        "",
        "## Source coverage",
        "",
        json.dumps(dataset_meta.get("source_coverage") or {}, indent=2, ensure_ascii=False),
        "",
        "## Validation",
        "",
        json.dumps(dataset_meta.get("validation") or {}, indent=2, ensure_ascii=False),
        "",
        "## Overall metrics",
        "",
        json.dumps({k: v for k, v in metrics.items() if k not in ("failed_case_ids", "hallucination_case_ids")}, indent=2),
        "",
        "## Category metrics",
        "",
        json.dumps(metrics.get("category_accuracy") or {}, indent=2),
        "",
        "## Language metrics",
        "",
        json.dumps(metrics.get("language_accuracy") or {}, indent=2),
        "",
        "## Difficulty metrics",
        "",
        json.dumps(metrics.get("difficulty_accuracy") or {}, indent=2),
        "",
        "## Latency",
        "",
        f"- average_ms: {metrics.get('average_latency_ms')}",
        f"- p95_ms: {metrics.get('p95_latency_ms')}",
        "",
        "## Failed cases",
        "",
    ]
    failed = [row for row in scored if not row.get("ok")]
    if not failed:
        lines.append("None.")
    else:
        for row in failed:
            lines.append(f"- `{row['id']}` HTTP {row.get('http_status')} error={row.get('error')}")
    lines.extend(["", "## Unsupported / hallucination cases", ""])
    halluc = [row for row in scored if row.get("unsupported", {}).get("hallucinated")]
    if not halluc:
        lines.append("None detected among completed unsupported cases.")
    else:
        for row in halluc:
            lines.append(f"- `{row['id']}` leaked={row['unsupported'].get('leaked_claims')}")
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- Ground truth is limited to five seed/overview documents in this repository.",
            "- Catalog/registry URLs are not treated as scheme facts.",
            "- Factual correctness is deterministic keyphrase overlap, not human adjudication.",
            "- Retrieval Precision@k is N/A when the API returns no sources.",
            "- Live competitor systems were not tested.",
            "- If the API or model is unavailable, execution metrics reflect errors rather than answer quality.",
            "",
        ]
    )
    RUN_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    RUN_REPORT_PATH.write_text(text, encoding="utf-8")
    return text


def run_benchmark(
    limit: Optional[int] = None,
    timeout: float = 180.0,
    *,
    resume: bool = False,
    start_after: Optional[str] = None,
    backfill_missing: bool = False,
) -> Dict[str, Any]:
    dataset = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    cases = list(dataset.get("cases") or [])
    if limit is not None:
        cases = cases[:limit]
    prior = load_checkpoint() if resume else {}
    prior_runs = list(prior.values())
    api_status = "not_started"
    client = GramSakhiClient(timeout=timeout)
    healthy, detail = client.health()
    if not healthy:
        api_status = f"unreachable: {detail}"
        runs = prior_runs or [
            {
                "id": case["id"],
                "question": case["question"],
                "language": case.get("language"),
                "category": case.get("category"),
                "ok": False,
                "http_status": None,
                "latency_ms": None,
                "response": {},
                "error": api_status,
            }
            for case in cases
        ]
    else:
        try:
            client = _auth_client(timeout)
            auth_state = client.probe_auth()
            todo = pending_cases(cases, done_ids=set(prior), start_after=start_after)
            if start_after:
                print(f"resume_after={start_after} pending={len(todo)} checkpointed={len(prior)}", flush=True)
            if todo and not prior:
                preflight = run_cases(todo[:1], client=client, timeout=timeout, api_status="preflight", checkpoint=True)
                first = preflight[0]
                if not first.get("ok"):
                    api_status = (
                        f"healthy auth_{auth_state} preflight_failed "
                        f"http={first.get('http_status')} err={first.get('error')}"
                    )
                    raise GramSakhiApiError(api_status, status=first.get("http_status"))
                api_status = (
                    f"healthy auth_{auth_state} preflight_ok "
                    f"http={first.get('http_status')} base={client.base_url}"
                )
                rest = run_cases(
                    todo[1:],
                    client=client,
                    timeout=timeout,
                    prior_runs=preflight,
                    api_status=api_status,
                    checkpoint=True,
                )
                runs = rest
            else:
                api_status = f"healthy auth_{auth_state} resumed base={client.base_url}"
                if todo:
                    probe = run_cases(
                        todo[:1],
                        client=client,
                        timeout=timeout,
                        prior_runs=prior_runs,
                        api_status=api_status,
                        checkpoint=True,
                    )
                    if not probe[-1].get("ok"):
                        raise GramSakhiApiError(
                            f"resume_probe_failed http={probe[-1].get('http_status')} err={probe[-1].get('error')}",
                            status=probe[-1].get("http_status"),
                        )
                    runs = run_cases(
                        todo[1:],
                        client=client,
                        timeout=timeout,
                        prior_runs=probe,
                        api_status=api_status,
                        checkpoint=True,
                    )
                else:
                    runs = prior_runs
            if backfill_missing:
                missing = pending_cases(cases, done_ids={row["id"] for row in runs})
                if missing:
                    print(f"backfill_missing={len(missing)}", flush=True)
                    runs = run_cases(
                        missing,
                        client=client,
                        timeout=timeout,
                        prior_runs=runs,
                        api_status=api_status,
                        checkpoint=True,
                    )
        except GramSakhiApiError as exc:
            api_status = f"healthy_but_auth_failed: {exc}"
            runs = prior_runs or [
                {
                    "id": case["id"],
                    "question": case["question"],
                    "language": case.get("language"),
                    "category": case.get("category"),
                    "ok": False,
                    "http_status": getattr(exc, "status", None),
                    "latency_ms": None,
                    "response": {},
                    "error": api_status,
                }
                for case in cases
            ]

    by_id = {row["id"]: row for row in runs if row.get("id")}
    ordered_runs = [
        by_id.get(
            case["id"],
            {
                "id": case["id"],
                "question": case.get("question"),
                "language": case.get("language"),
                "category": case.get("category"),
                "ok": False,
                "http_status": None,
                "latency_ms": None,
                "response": {},
                "error": "not_run",
            },
        )
        for case in cases
    ]
    scored = [score_case(case, run) for case, run in zip(cases, ordered_runs)]
    runs = ordered_runs
    metrics = aggregate_scores(scored)
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_status": api_status,
        "dataset": {
            "path": str(BENCHMARK_PATH),
            "n_cases": len(cases),
            "distribution": dataset.get("distribution"),
            "source_coverage": dataset.get("source_coverage"),
            "validation": dataset.get("validation_summary"),
        },
        "metrics": metrics,
        "cases": scored,
        "raw_runs": runs,
    }
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_report(dataset_meta=result["dataset"], scored=scored, metrics=metrics, api_status=api_status)
    return result
