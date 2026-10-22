"""Regression tests for development-only OTP retrieval."""

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
from app.models.citizen_account import OTPVerification
from app.services.auth_rate_limit import reset_auth_rate_limits


class TestOTPDevRetrieval(unittest.TestCase):
    DEV_KEY = "local-dev-only-secret"

    @classmethod
    def setUpClass(cls):
        cls.db_path = "test_otp_dev_retrieval.db"
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
        db.commit()
        db.close()

    def _dev_env(self):
        return patch.multiple(
            settings,
            APP_ENV="development",
            OTP_DEV_RETRIEVAL_ENABLED=True,
            OTP_DEV_RETRIEVAL_KEY=self.DEV_KEY,
        )

    def _retrieve(self, phone: str, key: str | None = DEV_KEY):
        headers = {}
        if key is not None:
            headers["X-Dev-OTP-Key"] = key
        return self.client.get(
            "/api/auth/otp/dev",
            params={"phone_number": phone},
            headers=headers,
        )

    def test_dev_retrieval_disabled_by_default(self):
        res = self._retrieve("9333333333")
        self.assertEqual(res.status_code, 404, res.text)

    def test_dev_retrieval_rejected_in_production(self):
        with patch.object(settings, "APP_ENV", "production"):
            with patch.object(settings, "OTP_DEV_RETRIEVAL_ENABLED", True):
                with patch.object(settings, "OTP_DEV_RETRIEVAL_KEY", self.DEV_KEY):
                    res = self._retrieve("9333333333")
        self.assertEqual(res.status_code, 404, res.text)

    def test_missing_dev_key_rejected(self):
        with self._dev_env():
            res = self._retrieve("9333333333", key=None)
        self.assertEqual(res.status_code, 404, res.text)

    def test_incorrect_dev_key_rejected(self):
        with self._dev_env():
            res = self._retrieve("9333333333", key="wrong-key")
        self.assertEqual(res.status_code, 404, res.text)

    def test_correct_key_retrieves_active_otp(self):
        phone = "9333333333"
        code = "654321"
        with self._dev_env():
            with patch.object(security, "generate_otp", return_value=code):
                send = self.client.post("/api/auth/otp/send", json={"phone_number": phone})
            self.assertEqual(send.status_code, 200, send.text)
            self.assertNotIn("otp", send.json())

            res = self._retrieve(phone)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["otp"], code)
        self.assertIn("expires_at", body)
        self.assertEqual(body["phone_number"], "***3333")

    def test_expired_otp_cannot_be_retrieved(self):
        phone = "9444444444"
        db = self.SessionLocal()
        db.add(
            OTPVerification(
                phone_number=phone,
                otp_hash=security.get_otp_hash("111111"),
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
                verified=False,
                attempt_count=0,
            )
        )
        db.commit()
        db.close()

        with self._dev_env():
            res = self._retrieve(phone)
        self.assertEqual(res.status_code, 404, res.text)

    def test_retrieval_does_not_consume_otp(self):
        phone = "9555555555"
        code = "123456"
        with self._dev_env():
            with patch.object(security, "generate_otp", return_value=code):
                self.client.post("/api/auth/otp/send", json={"phone_number": phone})
            self._retrieve(phone)
            verify = self.client.post(
                "/api/auth/otp/verify",
                json={"phone_number": phone, "code": code},
            )
        self.assertEqual(verify.status_code, 200, verify.text)

    def test_retrieval_does_not_increment_attempt_count(self):
        phone = "9666666666"
        code = "987654"
        with self._dev_env():
            with patch.object(security, "generate_otp", return_value=code):
                self.client.post("/api/auth/otp/send", json={"phone_number": phone})

            db = self.SessionLocal()
            before = (
                db.query(OTPVerification)
                .filter(OTPVerification.phone_number == phone)
                .order_by(OTPVerification.created_at.desc())
                .first()
            )
            self.assertIsNotNone(before)
            attempt_before = before.attempt_count
            db.close()

            self._retrieve(phone)

            db = self.SessionLocal()
            after = (
                db.query(OTPVerification)
                .filter(OTPVerification.phone_number == phone)
                .order_by(OTPVerification.created_at.desc())
                .first()
            )
            self.assertEqual(after.attempt_count, attempt_before)
            self.assertFalse(after.verified)
            db.close()

    def test_otp_send_behavior_unchanged(self):
        phone = "9777777777"
        buffer = io.StringIO()
        with patch.object(settings, "DATABASE_URL", "postgresql://user:pass@db.example.com/postgres"):
            with patch.object(settings, "APP_ENV", "production"):
                with patch.object(security, "generate_otp", return_value="112233"):
                    with redirect_stdout(buffer):
                        res = self.client.post("/api/auth/otp/send", json={"phone_number": phone})
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["message"], "OTP verification code sent.")
        self.assertNotIn("dev_otp", body)
        self.assertIn("otp_verification_id", body)
        self.assertNotIn("112233", buffer.getvalue())

    def test_otp_verify_behavior_unchanged(self):
        phone = "9888888888"
        code = "445566"
        with patch.object(security, "generate_otp", return_value=code):
            send = self.client.post("/api/auth/otp/send", json={"phone_number": phone})
        self.assertEqual(send.status_code, 200, send.text)

        bad = self.client.post(
            "/api/auth/otp/verify",
            json={"phone_number": phone, "code": "000000"},
        )
        self.assertEqual(bad.status_code, 400, bad.text)
        self.assertIn("Invalid OTP code", bad.json()["detail"])

        ok = self.client.post(
            "/api/auth/otp/verify",
            json={"phone_number": phone, "code": code},
        )
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertIn("message", ok.json())


if __name__ == "__main__":
    unittest.main()
