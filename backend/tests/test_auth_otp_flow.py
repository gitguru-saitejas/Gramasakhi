"""Auth / OTP end-to-end regression tests."""

from __future__ import annotations

import os
import unittest
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


class TestAuthOtpFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = "test_auth_otp_flow.db"
        if os.path.exists(cls.db_path):
            try:
                os.remove(cls.db_path)
            except OSError:
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
            except OSError:
                pass

    def setUp(self):
        reset_auth_rate_limits()
        db = self.SessionLocal()
        db.query(OTPVerification).delete()
        db.query(CitizenAccount).delete()
        db.commit()
        db.close()

    def _send_otp(self, phone: str, code: str = "112233") -> None:
        with patch.object(security, "generate_otp", return_value=code):
            res = self.client.post("/api/auth/otp/send", json={"phone_number": phone})
        self.assertEqual(res.status_code, 200, res.text)

    def test_login_otp_verify_issues_citizen_jwt(self):
        phone = "9000111100"
        self._send_otp(phone)
        db = self.SessionLocal()
        db.add(
            CitizenAccount(
                phone_number=phone,
                password_hash=security.get_password_hash("password123"),
                display_name="Citizen",
            )
        )
        db.commit()
        db.close()

        verify = self.client.post(
            "/api/auth/otp/verify",
            json={"phone_number": phone, "code": "112233"},
        )
        self.assertEqual(verify.status_code, 200, verify.text)
        body = verify.json()
        self.assertIn("accessToken", body)
        payload = security.decode_access_token(body["accessToken"])
        self.assertTrue(security.token_use_allowed(payload, "citizen"))

    def test_invalid_otp_rejected(self):
        phone = "9000111101"
        self._send_otp(phone, code="112233")
        bad = self.client.post(
            "/api/auth/otp/verify",
            json={"phone_number": phone, "code": "999999"},
        )
        self.assertEqual(bad.status_code, 400, bad.text)
        self.assertIn("Invalid OTP", bad.json()["detail"])

    def test_expired_otp_rejected(self):
        phone = "9000111102"
        db = self.SessionLocal()
        db.add(
            OTPVerification(
                phone_number=phone,
                otp_hash=security.get_otp_hash("445566"),
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
                verified=False,
                attempt_count=0,
            )
        )
        db.commit()
        db.close()
        res = self.client.post(
            "/api/auth/otp/verify",
            json={"phone_number": phone, "code": "445566"},
        )
        self.assertEqual(res.status_code, 400, res.text)
        self.assertIn("expired", res.json()["detail"].lower())

    def test_otp_single_use_after_login_verify(self):
        phone = "9000111103"
        self._send_otp(phone)
        db = self.SessionLocal()
        db.add(
            CitizenAccount(
                phone_number=phone,
                password_hash=security.get_password_hash("password123"),
                display_name="Citizen",
            )
        )
        db.commit()
        db.close()
        first = self.client.post(
            "/api/auth/otp/verify",
            json={"phone_number": phone, "code": "112233"},
        )
        self.assertEqual(first.status_code, 200, first.text)
        second = self.client.post(
            "/api/auth/login",
            json={"phone_number": phone, "login_type": "otp"},
        )
        self.assertEqual(second.status_code, 401, second.text)

    def test_resend_otp_rate_limit(self):
        phone = "9000111104"
        with patch.object(security, "generate_otp", return_value="112233"):
            for _ in range(settings.AUTH_OTP_SEND_MAX_PER_WINDOW):
                res = self.client.post("/api/auth/otp/send", json={"phone_number": phone})
                self.assertEqual(res.status_code, 200, res.text)
            blocked = self.client.post("/api/auth/otp/send", json={"phone_number": phone})
        self.assertEqual(blocked.status_code, 429, blocked.text)

    def test_dev_otp_logged_to_terminal_channel(self):
        phone = "9000111105"
        with patch.object(settings, "APP_ENV", "development"):
            with patch.object(settings, "OTP_CONSOLE_SIMULATOR_ENABLED", True):
                with patch.object(security, "generate_otp", return_value="556677"):
                    with self.assertLogs("uvicorn.error", level="WARNING") as captured:
                        res = self.client.post("/api/auth/otp/send", json={"phone_number": phone})
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["message"], "OTP verification code sent.")
        self.assertNotIn("dev_otp", body)
        joined = "\n".join(captured.output)
        self.assertIn("OTP: 556677", joined)
        self.assertNotIn("556677", res.text)

    def test_dev_otp_mirror_file_written(self):
        from app.services import otp_console as oc

        phone = "9000111107"
        mirror = oc.DEV_OTP_MIRROR_FILE
        if mirror.exists():
            mirror.unlink()
        with patch.object(settings, "APP_ENV", "development"):
            with patch.object(settings, "OTP_CONSOLE_SIMULATOR_ENABLED", True):
                with patch.object(security, "generate_otp", return_value="889900"):
                    res = self.client.post("/api/auth/otp/send", json={"phone_number": phone})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertTrue(mirror.is_file())
        self.assertIn("OTP: 889900", mirror.read_text(encoding="utf-8"))
        mirror.unlink(missing_ok=True)

    def test_register_after_otp_issues_jwt(self):
        phone = "9000111108"
        self._send_otp(phone)
        verify = self.client.post(
            "/api/auth/otp/verify",
            json={"phone_number": phone, "code": "112233"},
        )
        self.assertEqual(verify.status_code, 200, verify.text)
        self.assertNotIn("accessToken", verify.json())

        reg = self.client.post(
            "/api/auth/register",
            json={
                "credentials": {"phone_number": phone},
                "display_name": "New Citizen",
            },
        )
        self.assertEqual(reg.status_code, 200, reg.text)
        body = reg.json()
        self.assertIn("accessToken", body)
        self.assertEqual(body.get("display_name"), "New Citizen")
        payload = security.decode_access_token(body["accessToken"])
        self.assertTrue(security.token_use_allowed(payload, "citizen"))

        dup = self.client.post(
            "/api/auth/register",
            json={"credentials": {"phone_number": phone}, "display_name": "Dup"},
        )
        self.assertEqual(dup.status_code, 401, dup.text)

        db = self.SessionLocal()
        db.add(
            OTPVerification(
                phone_number=phone,
                otp_hash=security.get_otp_hash("334455"),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=3),
                verified=True,
                attempt_count=0,
            )
        )
        db.commit()
        db.close()
        dup2 = self.client.post(
            "/api/auth/register",
            json={"credentials": {"phone_number": phone}, "display_name": "Dup"},
        )
        self.assertEqual(dup2.status_code, 400, dup2.text)
        self.assertIn("already exists", dup2.json()["detail"].lower())

    def test_production_does_not_log_otp_code(self):
        phone = "9000111106"
        with patch.object(settings, "APP_ENV", "production"):
            with patch.object(settings, "OTP_CONSOLE_SIMULATOR_ENABLED", True):
                with patch.object(security, "generate_otp", return_value="667788"):
                    with self.assertLogs("gramsakhi.auth", level="INFO") as captured:
                        res = self.client.post("/api/auth/otp/send", json={"phone_number": phone})
        self.assertEqual(res.status_code, 200, res.text)
        joined = "\n".join(captured.output)
        self.assertNotIn("667788", joined)
        self.assertNotIn("VERIFICATION OTP", joined)


if __name__ == "__main__":
    unittest.main()
