"""H7-A — security and privacy hardening regression tests."""

from __future__ import annotations

import io
import os
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import security
from app.core.config import settings
from app.database.session import Base, get_db
from app.main import app
from app.models import citizen_account, user, rag, audit, conversation  # noqa: F401
from app.models.citizen_account import CitizenAccount, OTPVerification
from app.services.auth_rate_limit import reset_auth_rate_limits


class TestH7ASecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = "test_h7a_security.db"
        if os.path.exists(cls.db_path):
            try:
                os.remove(cls.db_path)
            except Exception:
                pass
        cls.engine = create_engine(
            f"sqlite:///{cls.db_path}", connect_args={"check_same_thread": False}
        )
        Base.metadata.drop_all(bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

        def _override_db():
            db = cls.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _override_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        cls.engine.dispose()
        if os.path.exists(cls.db_path):
            try:
                os.remove(cls.db_path)
            except Exception:
                pass

    def setUp(self):
        reset_auth_rate_limits()
        db = self.SessionLocal()
        db.query(OTPVerification).delete()
        db.query(CitizenAccount).delete()
        db.commit()
        db.close()

    def _register_payload(self, phone: str = "9333333333"):
        return {
            "credentials": {"phone_number": phone, "password": "password123"},
            "display_name": "Test Citizen",
        }

    def _send_and_verify_otp(self, phone: str = "9333333333", code: str = "654321"):
        with patch.object(security, "generate_otp", return_value=code):
            send = self.client.post("/api/auth/otp/send", json={"phone_number": phone})
        self.assertEqual(send.status_code, 200, send.text)
        verify = self.client.post(
            "/api/auth/otp/verify",
            json={"phone_number": phone, "code": code},
        )
        self.assertEqual(verify.status_code, 200, verify.text)

    def test_register_without_verified_otp_rejected(self):
        res = self.client.post("/api/auth/register", json=self._register_payload())
        self.assertEqual(res.status_code, 401, res.text)
        self.assertIn("OTP verification is required", res.json()["detail"])

    def test_register_after_otp_verification_succeeds(self):
        self._send_and_verify_otp()
        res = self.client.post("/api/auth/register", json=self._register_payload())
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertIn("accessToken", body)
        self.assertEqual(body["phone_number"], "9333333333")
        payload = security.decode_access_token(body["accessToken"])
        self.assertTrue(security.token_use_allowed(payload, "citizen"))

    def test_password_reset_blocks_after_max_attempts(self):
        db = self.SessionLocal()
        account = CitizenAccount(
            phone_number="9444444444",
            password_hash=security.get_password_hash("password123"),
            display_name="Reset User",
        )
        db.add(account)
        otp_rec = OTPVerification(
            phone_number="9444444444",
            otp_hash=security.get_otp_hash("111111"),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=3),
            verified=False,
            attempt_count=5,
        )
        db.add(otp_rec)
        db.commit()
        db.close()

        res = self.client.post(
            "/api/auth/forgot-password/reset",
            json={
                "phone_number": "9444444444",
                "otp_code": "111111",
                "new_password": "newpassword123",
            },
        )
        self.assertEqual(res.status_code, 400, res.text)
        self.assertIn("Too many failed verification attempts", res.json()["detail"])

    def test_otp_send_rate_limited(self):
        phone = "9555555555"
        with patch.object(security, "generate_otp", return_value="123456"):
            for _ in range(settings.AUTH_OTP_SEND_MAX_PER_WINDOW):
                res = self.client.post("/api/auth/otp/send", json={"phone_number": phone})
                self.assertEqual(res.status_code, 200, res.text)
            blocked = self.client.post("/api/auth/otp/send", json={"phone_number": phone})
        self.assertEqual(blocked.status_code, 429, blocked.text)

    def test_otp_not_printed_for_non_sqlite_database(self):
        phone = "9666666666"
        buffer = io.StringIO()
        with patch.object(settings, "DATABASE_URL", "postgresql://user:pass@db.example.com/postgres"):
            with patch.object(settings, "APP_ENV", "production"):
                with patch.object(security, "generate_otp", return_value="987654"):
                    with redirect_stdout(buffer):
                        res = self.client.post("/api/auth/otp/send", json={"phone_number": phone})
        self.assertEqual(res.status_code, 200, res.text)
        output = buffer.getvalue()
        self.assertNotIn("987654", output)
        self.assertNotIn(phone, output)

    def test_otp_printed_in_development_even_on_postgres(self):
        phone = "9666666667"
        buffer = io.StringIO()
        with patch.object(settings, "DATABASE_URL", "postgresql://user:pass@db.example.com/postgres"):
            with patch.object(settings, "APP_ENV", "development"):
                with patch.object(settings, "OTP_CONSOLE_SIMULATOR_ENABLED", True):
                    with patch.object(security, "generate_otp", return_value="987654"):
                        with redirect_stdout(buffer):
                            res = self.client.post("/api/auth/otp/send", json={"phone_number": phone})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertIn("OTP: 987654", buffer.getvalue())

    def test_security_headers_present(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(res.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")

    def test_health_db_host_redacted_for_non_sqlite(self):
        with patch.object(settings, "DATABASE_URL", "postgresql://user:pass@secret-host/db"):
            res = self.client.get("/health/db")
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["host"], "redacted")

    def test_generate_otp_format(self):
        code = security.generate_otp()
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

    def test_unknown_phone_login_does_not_enumerate(self):
        unknown = self.client.post(
            "/api/auth/login",
            json={"phone_number": "9000000000", "password": "wrongpass", "login_type": "password"},
        )
        self.assertEqual(unknown.status_code, 401, unknown.text)
        self.assertEqual(unknown.json()["detail"], "Invalid phone number or password.")

        self._send_and_verify_otp("9111111111")
        self.client.post("/api/auth/register", json=self._register_payload("9111111111"))
        wrong = self.client.post(
            "/api/auth/login",
            json={"phone_number": "9111111111", "password": "not-the-password", "login_type": "password"},
        )
        self.assertEqual(wrong.status_code, 401, wrong.text)
        self.assertEqual(wrong.json()["detail"], unknown.json()["detail"])

    def test_login_failures_are_rate_limited(self):
        with patch.object(settings, "AUTH_LOGIN_MAX_PER_WINDOW", 3):
            reset_auth_rate_limits()
            payload = {"phone_number": "9000000001", "password": "nope", "login_type": "password"}
            for _ in range(3):
                res = self.client.post("/api/auth/login", json=payload)
                self.assertEqual(res.status_code, 401, res.text)
            blocked = self.client.post("/api/auth/login", json=payload)
            self.assertEqual(blocked.status_code, 429, blocked.text)

    def test_forgot_password_does_not_enumerate_accounts(self):
        res = self.client.post(
            "/api/auth/forgot-password/request",
            json={"phone_number": "9000000002"},
        )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["message"], "OTP verification code sent.")

    def test_static_uploads_are_not_public(self):
        res = self.client.get("/static/uploads/knowledge-base__schemes__local-fallback-test.txt")
        self.assertEqual(res.status_code, 404)

    def test_admin_token_rejected_on_citizen_routes(self):
        from app.models.user import User

        db = self.SessionLocal()
        admin = User(
            email="admin-sec@example.com",
            password_hash=security.get_password_hash("password123"),
            first_name="Sec",
            last_name="Admin",
            role="ADMIN",
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        token = security.create_access_token(subject=str(admin.id), token_use="admin")
        db.close()

        res = self.client.get(
            "/api/chat/conversations",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(res.status_code, 401, res.text)

    def test_legacy_sha256_otp_still_verifies(self):
        import hashlib

        phone = "9222222222"
        code = "424242"
        db = self.SessionLocal()
        db.add(
            OTPVerification(
                phone_number=phone,
                otp_hash=hashlib.sha256(code.encode("utf-8")).hexdigest(),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=3),
                verified=False,
                attempt_count=0,
            )
        )
        db.commit()
        db.close()
        res = self.client.post(
            "/api/auth/otp/verify",
            json={"phone_number": phone, "code": code},
        )
        self.assertEqual(res.status_code, 200, res.text)

    def test_schema_enables_rls(self):
        from pathlib import Path

        schema = Path("app/database/migrations/supabase_schema.sql").read_text(encoding="utf-8")
        self.assertIn("ENABLE ROW LEVEL SECURITY", schema)
        self.assertNotIn("USING (true)", schema)

    def test_auth_responses_are_not_cached(self):
        with patch.object(security, "generate_otp", return_value="111111"):
            res = self.client.post("/api/auth/otp/send", json={"phone_number": "9333333330"})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.headers.get("Cache-Control"), "no-store")


if __name__ == "__main__":
    unittest.main()
