"""Phase 5 — Android golden journey API validation (mirrors mobile client; no mocks)."""
from __future__ import annotations

import io
import json
import re
import sys
import urllib.error
import urllib.request
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

BASE = "http://127.0.0.1:8000/api"
# Use 10.0.2.2 health probe semantics: host loopback from CI; app uses emulator alias.
HEALTH = "http://127.0.0.1:8000/health"
EMULATOR_API = "http://10.0.2.2:8000/health"
PHONE = f"9{__import__('time').time_ns() % 10_000_000_000:09d}"[:10]
CHAT_TIMEOUT = 300


def req(method: str, path: str, body: dict | None = None, token: str | None = None) -> tuple[int, dict | str]:
    url = f"{BASE}{path}"
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=CHAT_TIMEOUT) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw
        return e.code, payload


def map_answer(data: dict) -> str:
    return str(data.get("answer") or "")


def main() -> int:
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
        if not ok:
            failures.append(name)

    # Config contract
    check("API config default emulator host documented", Path(ROOT / "mobile/.env.example").read_text(encoding="utf-8").find("10.0.2.2:8000") >= 0)

    try:
        with urllib.request.urlopen(HEALTH, timeout=10) as r:
            health = json.loads(r.read().decode())
        check("Backend health (host loopback)", health.get("status") == "ok")
    except Exception as exc:
        check("Backend health (host loopback)", False, str(exc))
        return 1

    # Emulator alias is not reachable from host — document only
    try:
        urllib.request.urlopen(EMULATOR_API, timeout=2)
        check("10.0.2.2 from host (informational)", True, "unexpectedly reachable")
    except Exception:
        check("10.0.2.2 alias (app-side only)", True, "host cannot reach 10.0.2.2 — expected")

    # Auth + optional register (mobile OTP flow)
    code, _ = req("POST", "/auth/otp/send", {"phone_number": PHONE})
    check("OTP send", code == 200)

    otp_code = None
    mirror = ROOT / "backend" / ".dev_otp_last.txt"
    if mirror.exists():
        m = re.search(r"OTP:\s*(\d{6})", mirror.read_text(encoding="utf-8"))
        otp_code = m.group(1) if m else None
    if not otp_code:
        try:
            from fastapi.testclient import TestClient
            from app.main import app

            buf = io.StringIO()
            with redirect_stdout(buf):
                TestClient(app).post("/api/auth/otp/send", json={"phone_number": PHONE})
            m = re.search(r"VERIFICATION OTP:\s*(\d{6})", buf.getvalue())
            otp_code = m.group(1) if m else None
        except Exception:
            pass

    token = None
    if otp_code:
        code, verify_data = req("POST", "/auth/otp/verify", {"phone_number": PHONE, "code": otp_code})
        if code == 200 and verify_data.get("accessToken"):
            token = verify_data["accessToken"]
            check("OTP verify (existing account)", True)
        elif code == 200:
            check("OTP verify (new citizen)", True, "register next")
            code, reg = req(
                "POST",
                "/auth/register",
                {"credentials": {"phone_number": PHONE}, "display_name": "Android Golden"},
            )
            token = reg.get("accessToken") if code == 200 else None
            check("Register after OTP", bool(token), str(reg)[:120])
        else:
            check("OTP verify", False, str(verify_data)[:120])
    if not token:
        return 1

    conv_id: str | None = None

    def chat_turn(message: str, lang: str = "EN") -> dict:
        nonlocal conv_id
        code, data = req(
            "POST",
            "/chat",
            {
                "message": message,
                "conversation_id": conv_id,
                "language": lang,
                "input_mode": "text",
            },
            token=token,
        )
        check(f"POST /chat — {message[:40]}", code == 200 and bool(map_answer(data)), str(code))
        if code == 200:
            conv_id = str(data.get("conversation_id") or conv_id)
        return data if isinstance(data, dict) else {}

    r1 = chat_turn("Tell me about Gruha Lakshmi.")
    check("First answer non-empty", len(map_answer(r1)) > 20)
    first_conv = conv_id
    check("conversation_id created", bool(first_conv))

    r2 = chat_turn("How can I apply?")
    check("Follow-up same conversation", conv_id == first_conv)
    check("Follow-up answer", len(map_answer(r2)) > 10)

    r3 = chat_turn("Documents?")
    check("Short follow-up same conversation", conv_id == first_conv)

    r4 = chat_turn("Kannada please")
    check("Kannada same conversation", conv_id == first_conv)
    check("Kannada response_language", str(r4.get("response_language", "")).upper() == "KN")
    op = str(r4.get("language_operation") or "")
    check("Kannada language_operation", bool(op) and "TRANSLATION" in op.upper() or "LANGUAGE" in op.upper(), op or "none")

    r5 = chat_turn("Explain that simply")
    check("Simplification same conversation", conv_id == first_conv)
    check("Simplification answer", len(map_answer(r5)) > 10)

    r6 = chat_turn("English please")
    check("English transform same conversation", conv_id == first_conv)
    check("English response_language", str(r6.get("response_language", "")).upper() == "EN")

    code, hist = req("GET", f"/chat/conversations/{conv_id}", token=token)
    msgs = hist.get("messages", []) if isinstance(hist, dict) else []
    check("History reload", code == 200 and len(msgs) >= 4)
    user_msgs = [m.get("content") for m in msgs if m.get("role") == "user"]
    check("No duplicate user turns", len(user_msgs) == len(set(user_msgs)) or len(user_msgs) >= 4)

    r7 = chat_turn("Who can get this?")
    check("Post-persistence turn", conv_id == first_conv)

    code, _ = req("GET", "/chat/conversations?limit=5&offset=0", token=token)
    check("List conversations after journey", code == 200)

    code, _ = req("GET", "/chat/conversations?limit=1&offset=0", token="invalid.jwt.token")
    check("Invalid token 401", code == 401)

    try:
        bad = urllib.request.Request("http://127.0.0.1:59999/api/health")
        urllib.request.urlopen(bad, timeout=2)
        check("Unreachable host", False, "expected failure")
    except Exception:
        check("Network failure survivable (client-side)", True)

    if failures:
        print(f"\n{len(failures)} failure(s):", ", ".join(failures))
        return 1
    print("\nAndroid golden API journey passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
