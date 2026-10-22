"""CORS configuration for citizen frontend origins."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

PRODUCTION_FRONTEND = "https://gramasakhi-1.onrender.com"
LOCAL_FRONTEND = "http://127.0.0.1:5173"


class TestCorsConfiguration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_production_frontend_in_allowed_origins(self):
        origins = list(settings.BACKEND_CORS_ORIGINS or [])
        self.assertIn(PRODUCTION_FRONTEND, origins)

    def test_cors_preflight_otp_send_production_origin(self):
        response = self.client.options(
            "/api/auth/otp/send",
            headers={
                "Origin": PRODUCTION_FRONTEND,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            PRODUCTION_FRONTEND,
        )
        allow_methods = (response.headers.get("access-control-allow-methods") or "").upper()
        self.assertIn("POST", allow_methods)

    def test_cors_preflight_localhost_origin(self):
        response = self.client.options(
            "/api/auth/otp/send",
            headers={
                "Origin": LOCAL_FRONTEND,
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), LOCAL_FRONTEND)

    def test_disallowed_origin_not_reflected(self):
        response = self.client.options(
            "/api/auth/otp/send",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
