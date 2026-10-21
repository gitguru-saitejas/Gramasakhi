"""One-shot local bootstrap: obtain a citizen JWT via public API, then run benchmark_v1.

Never prints tokens, passwords, OTP codes, or .env values.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import dotenv_values

from evaluation.runners.api_client import GramSakhiClient, _request
from evaluation.runners.execute import run_benchmark


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
        payload={"credentials": {"phone_number": phone, "password": password}, "display_name": "Benchmark Citizen"},
        timeout=20,
    )
    if status >= 400:
        raise SystemExit(f"register_failed http={status}")
    os.environ["GRAMSAKHI_BENCH_PHONE"] = phone
    os.environ["GRAMSAKHI_BENCH_PASSWORD"] = password
    os.environ.pop("GRAMSAKHI_BENCH_TOKEN", None)
    client = GramSakhiClient(base_url=base, token=None)
    client.login(phone, password)
    token_state = client.probe_auth()
    print(f"auth_method=citizen_password_login token_status={token_state}")
    if token_state != "configured":
        raise SystemExit(f"probe_failed status={token_state}")
    os.environ["GRAMSAKHI_BENCH_TOKEN"] = client.token or ""


def main() -> int:
    os.environ.setdefault("GRAMSAKHI_API_BASE_URL", "http://127.0.0.1:8000")
    base = os.environ["GRAMSAKHI_API_BASE_URL"].rstrip("/")
    client = GramSakhiClient(base_url=base, token=None)
    healthy, detail = client.health()
    print(f"api_health={'ok' if healthy else 'down'}")
    if not healthy:
        print(detail)
        return 1
    if not (os.environ.get("GRAMSAKHI_BENCH_PHONE") and os.environ.get("GRAMSAKHI_BENCH_PASSWORD")):
        _bootstrap_citizen(base)
    result = run_benchmark(
        timeout=300.0,
        resume=True,
        start_after=os.environ.get("GRAMSAKHI_BENCH_START_AFTER") or "gsb1-0038",
        backfill_missing=True,
    )
    print(result.get("api_status"))
    metrics = result.get("metrics") or {}
    print(f"success={metrics.get('success_rate')} errors={metrics.get('n_errors')} n={metrics.get('n_cases')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
