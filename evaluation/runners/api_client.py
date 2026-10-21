"""HTTP client for the existing GramSakhi chat API. No production code is imported."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple


class GramSakhiApiError(RuntimeError):
    def __init__(self, message: str, status: Optional[int] = None, body: str = ""):
        super().__init__(message)
        self.status = status
        self.body = body


def _request(
    method: str,
    url: str,
    *,
    payload: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 180.0,
) -> Tuple[int, Dict[str, Any], float]:
    data = None
    req_headers = {"Accept": "application/json", **(headers or {})}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            latency_ms = (time.perf_counter() - started) * 1000.0
            body = json.loads(raw) if raw else {}
            return int(response.status), body if isinstance(body, dict) else {"value": body}, latency_ms
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        latency_ms = (time.perf_counter() - started) * 1000.0
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = {"detail": raw[:400]}
        raise GramSakhiApiError(f"HTTP {exc.code}", status=exc.code, body=raw) from exc
    except TimeoutError as exc:
        raise GramSakhiApiError("timeout", status=504) from exc
    except urllib.error.URLError as exc:
        reason = str(getattr(exc, "reason", exc))
        if "timed out" in reason.lower():
            raise GramSakhiApiError("timeout", status=504) from exc
        raise GramSakhiApiError(f"connection_failed: {exc.reason}", status=None) from exc


def env_token() -> Optional[str]:
    raw = os.environ.get("GRAMSAKHI_BENCH_TOKEN") or ""
    cleaned = raw.strip().strip('"').strip("'")
    return cleaned or None


def extract_access_token(body: Dict[str, Any]) -> Optional[str]:
    """Accept the live API field (accessToken) and the snake_case alias."""
    value = body.get("accessToken") or body.get("access_token")
    if not value:
        return None
    return str(value).strip() or None


def classify_unverified_jwt(token: Optional[str]) -> str:
    """Report token shape only. Does not verify the signature or print the value."""
    if not token:
        return "missing"
    parts = token.split(".")
    if len(parts) != 3:
        return "invalid"
    try:
        import base64
        import time

        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        exp = payload.get("exp")
        if isinstance(exp, (int, float)) and exp < time.time():
            return "expired"
        return "configured"
    except Exception:
        return "invalid"


class GramSakhiClient:
    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None, timeout: float = 180.0):
        self.base_url = (base_url or os.environ.get("GRAMSAKHI_API_BASE_URL") or "http://127.0.0.1:8000").rstrip("/")
        self.token = token if token is not None else env_token()
        self.timeout = timeout

    def login(self, phone: str, password: str) -> str:
        status, body, _ = _request(
            "POST",
            f"{self.base_url}/api/auth/login",
            payload={"phone_number": phone, "password": password, "login_type": "password"},
            timeout=min(self.timeout, 30.0),
        )
        token = extract_access_token(body)
        if status >= 400 or not token:
            raise GramSakhiApiError("login_failed", status=status)
        self.token = token
        return self.token

    def probe_auth(self) -> str:
        """Validate the current token against a protected citizen endpoint. Never prints the token."""
        shape = classify_unverified_jwt(self.token)
        if shape == "missing":
            return "missing"
        try:
            status, body, _ = _request(
                "GET",
                f"{self.base_url}/api/chat/conversations?limit=1",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=min(self.timeout, 15.0),
            )
        except GramSakhiApiError as exc:
            if exc.status in (401, 403):
                if shape == "expired":
                    return "expired"
                return "invalid"
            raise
        if 200 <= status < 300:
            return "configured"
        detail = ""
        if isinstance(body, dict):
            detail = str(body.get("detail") or "")
        if "expired" in detail.lower():
            return "expired"
        return "invalid"

    def health(self) -> Tuple[bool, str]:
        try:
            status, body, _ = _request("GET", f"{self.base_url}/health", timeout=10.0)
            return status == 200, json.dumps(body)[:200]
        except GramSakhiApiError as exc:
            return False, str(exc)

    def chat(self, question: str, language: Optional[str] = None) -> Tuple[Dict[str, Any], float, int]:
        if not self.token:
            raise GramSakhiApiError("missing_token")
        payload: Dict[str, Any] = {"message": question}
        if language:
            payload["language"] = language
        try:
            status, body, latency_ms = _request(
                "POST",
                f"{self.base_url}/api/chat",
                payload=payload,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=self.timeout,
            )
            return body, latency_ms, status
        except GramSakhiApiError as exc:
            if exc.status is None:
                raise
            if exc.status == 504 or str(exc) == "timeout":
                return {"detail": "timeout"}, 0.0, int(exc.status)
            try:
                parsed = json.loads(exc.body) if exc.body else {}
            except json.JSONDecodeError:
                parsed = {"detail": exc.body[:400]}
            return parsed if isinstance(parsed, dict) else {"detail": exc.body[:400]}, 0.0, int(exc.status)
