import base64
import json
import time
import unittest
from unittest.mock import patch

from evaluation.runners.api_client import (
    GramSakhiApiError,
    GramSakhiClient,
    classify_unverified_jwt,
    extract_access_token,
)
from evaluation.runners.execute import _auth_client, pending_cases, run_cases


def _unsigned_jwt(payload: dict) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{header}.{body}.sig"


class TestRunnerBehavior(unittest.TestCase):
    def test_chat_sends_existing_api_payload(self):
        client = GramSakhiClient(base_url="http://127.0.0.1:8000", token="tok")
        captured = {}

        def fake_request(method, url, payload=None, headers=None, timeout=180.0):
            captured["method"] = method
            captured["url"] = url
            captured["payload"] = payload
            captured["headers"] = headers
            return 200, {"answer": "Rs 20", "sources": [], "validated": True}, 15.5

        with patch("evaluation.runners.api_client._request", side_effect=fake_request):
            body, latency, status = client.chat("What is the PMSBY premium?", language="en")
        self.assertEqual(status, 200)
        self.assertEqual(body["answer"], "Rs 20")
        self.assertEqual(latency, 15.5)
        self.assertEqual(captured["url"], "http://127.0.0.1:8000/api/chat")
        self.assertEqual(captured["payload"], {"message": "What is the PMSBY premium?", "language": "en"})
        self.assertEqual(captured["headers"]["Authorization"], "Bearer tok")

    def test_missing_token(self):
        client = GramSakhiClient(base_url="http://127.0.0.1:8000", token=None)
        with self.assertRaises(GramSakhiApiError):
            client.chat("hello")

    def test_run_cases_records_errors(self):
        client = GramSakhiClient(base_url="http://127.0.0.1:8000", token="tok")

        def boom(*args, **kwargs):
            raise GramSakhiApiError("connection_failed", status=None)

        with patch.object(client, "chat", side_effect=boom):
            runs = run_cases(
                [{"id": "gsb1-0001", "question": "q", "language": "en", "category": "factual"}],
                client=client,
            )
        self.assertFalse(runs[0]["ok"])
        self.assertIn("connection_failed", runs[0]["error"])

    def test_timeout_is_recorded_not_raised(self):
        client = GramSakhiClient(base_url="http://127.0.0.1:8000", token="tok")

        def fake_request(*args, **kwargs):
            raise GramSakhiApiError("timeout", status=504)

        with patch("evaluation.runners.api_client._request", side_effect=fake_request):
            body, _, status = client.chat("q")
        self.assertEqual(status, 504)
        self.assertEqual(body.get("detail"), "timeout")

    def test_http_error_body_is_json(self):
        client = GramSakhiClient(base_url="http://127.0.0.1:8000", token="tok")

        def fake_request(*args, **kwargs):
            raise GramSakhiApiError("HTTP 401", status=401, body=json.dumps({"detail": "nope"}))

        with patch("evaluation.runners.api_client._request", side_effect=fake_request):
            body, _, status = client.chat("q")
        self.assertEqual(status, 401)
        self.assertEqual(body["detail"], "nope")

    def test_login_reads_accessToken_field(self):
        client = GramSakhiClient(base_url="http://127.0.0.1:8000", token=None)

        def fake_request(method, url, payload=None, headers=None, timeout=180.0):
            self.assertEqual(payload["login_type"], "password")
            return 200, {"accessToken": "citizen-jwt", "citizen_account_id": "1"}, 5.0

        with patch("evaluation.runners.api_client._request", side_effect=fake_request):
            token = client.login("9000000000", "password123")
        self.assertEqual(token, "citizen-jwt")
        self.assertEqual(client.token, "citizen-jwt")

    def test_extract_access_token_prefers_live_field(self):
        self.assertEqual(extract_access_token({"accessToken": "a", "access_token": "b"}), "a")
        self.assertEqual(extract_access_token({"access_token": "b"}), "b")
        self.assertIsNone(extract_access_token({}))

    def test_classify_expired_and_missing_jwt(self):
        self.assertEqual(classify_unverified_jwt(None), "missing")
        self.assertEqual(classify_unverified_jwt("not-a-jwt"), "invalid")
        expired = _unsigned_jwt({"exp": 1, "sub": "x"})
        self.assertEqual(classify_unverified_jwt(expired), "expired")
        fresh = _unsigned_jwt({"exp": int(time.time()) + 3600, "sub": "x"})
        self.assertEqual(classify_unverified_jwt(fresh), "configured")

    def test_auth_client_rejects_expired_token_without_login(self):
        expired = _unsigned_jwt({"exp": 1, "sub": "x"})
        env = {"GRAMSAKHI_BENCH_TOKEN": expired}

        def fake_request(method, url, payload=None, headers=None, timeout=180.0):
            raise GramSakhiApiError("HTTP 401", status=401, body=json.dumps({"detail": "Authentication token is expired or invalid."}))

        with patch.dict("os.environ", env, clear=False):
            with patch("evaluation.runners.api_client._request", side_effect=fake_request):
                with patch.dict("os.environ", {"GRAMSAKHI_BENCH_PHONE": "", "GRAMSAKHI_BENCH_PASSWORD": ""}, clear=False):
                    with self.assertRaises(GramSakhiApiError) as ctx:
                        _auth_client(10.0)
        self.assertIn("expired", str(ctx.exception))

    def test_auth_client_falls_back_to_login_when_token_expired(self):
        expired = _unsigned_jwt({"exp": 1, "sub": "x"})
        fresh = _unsigned_jwt({"exp": int(time.time()) + 3600, "sub": "x"})

        def fake_request(method, url, payload=None, headers=None, timeout=180.0):
            if url.endswith("/login"):
                return 200, {"accessToken": fresh}, 4.0
            if "conversations" in url:
                if headers and headers.get("Authorization") == f"Bearer {fresh}":
                    return 200, {"conversations": []}, 4.0
                raise GramSakhiApiError("HTTP 401", status=401, body='{"detail":"Authentication token is expired or invalid."}')
            raise AssertionError("unexpected url")

        env = {
            "GRAMSAKHI_BENCH_TOKEN": expired,
            "GRAMSAKHI_BENCH_PHONE": "9000000000",
            "GRAMSAKHI_BENCH_PASSWORD": "password123",
        }
        with patch.dict("os.environ", env, clear=False):
            with patch("evaluation.runners.api_client._request", side_effect=fake_request):
                client = _auth_client(10.0)
                self.assertEqual(client.probe_auth(), "configured")

    def test_pending_cases_resumes_after_id(self):
        cases = [{"id": f"gsb1-{i:04d}"} for i in range(1, 6)]
        pending = pending_cases(cases, start_after="gsb1-0003")
        self.assertEqual([c["id"] for c in pending], ["gsb1-0004", "gsb1-0005"])
        pending = pending_cases(cases, done_ids={"gsb1-0004"}, start_after="gsb1-0003")
        self.assertEqual([c["id"] for c in pending], ["gsb1-0005"])
