"""Development OTP popup mode — API and security regression tests."""

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
from app.models.citizen_account import OTPVerification
from app.services.auth_rate_limit import reset_auth_rate_limits
from app.services.otp_delivery import production_otp_config_errors


class TestOtpDevPopup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = "test_otp_dev_popup.db"
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        cls.engine = create_engine(
            f"sqlite:///{cls.db_path}", connect_args={"check_same_thread": False}
        )
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
            os.remove(cls.db_path)

    def setUp(self):
        reset_auth_rate_limits()
        db = self.SessionLocal()
        db.query(OTPVerification).delete()
        db.commit()
        db.close()

    def test_dev_popup_returns_otp_when_enabled(self):
        phone = "9000333300"
        with patch.object(settings, "APP_ENV", "development"):
            with patch.object(settings, "OTP_DELIVERY_MODE", "dev_popup"):
                with patch.object(settings, "OTP_DEV_POPUP_ENABLED", True):
                    with patch.object(security, "generate_otp", return_value="445566"):
                        res = self.client.post("/api/auth/otp/send", json={"phone_number": phone})
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["dev_otp"], "445566")
        self.assertEqual(body["delivery_mode"], "dev_popup")
        self.assertIn("otp_verification_id", body)
        self.assertNotIn("445566", body.get("message", ""))

    def test_sms_mode_never_returns_dev_otp(self):
        phone = "9000333301"
        with patch.object(settings, "OTP_DELIVERY_MODE", "sms"):
            with patch.object(settings, "OTP_DEV_POPUP_ENABLED", False):
                with patch.object(security, "generate_otp", return_value="778899"):
                    res = self.client.post("/api/auth/otp/send", json={"phone_number": phone})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertNotIn("dev_otp", body)
        self.assertEqual(body.get("delivery_mode"), "sms")

    def test_verify_with_transaction_id(self):
        phone = "9000333302"
        with patch.object(settings, "APP_ENV", "development"):
            with patch.object(settings, "OTP_DELIVERY_MODE", "dev_popup"):
                with patch.object(settings, "OTP_DEV_POPUP_ENABLED", True):
                    with patch.object(security, "generate_otp", return_value="112233"):
                        send = self.client.post("/api/auth/otp/send", json={"phone_number": phone})
        vid = send.json()["otp_verification_id"]
        verify = self.client.post(
            "/api/auth/otp/verify",
            json={"phone_number": phone, "code": "112233", "otp_verification_id": vid},
        )
        self.assertEqual(verify.status_code, 200, verify.text)

    def test_wrong_code_for_transaction_rejects(self):
        phone = "9000333303"
        with patch.object(security, "generate_otp", return_value="112233"):
            send1 = self.client.post("/api/auth/otp/send", json={"phone_number": phone})
        with patch.object(security, "generate_otp", return_value="445566"):
            send2 = self.client.post("/api/auth/otp/send", json={"phone_number": phone})
        latest_id = send2.json()["otp_verification_id"]
        bad = self.client.post(
            "/api/auth/otp/verify",
            json={
                "phone_number": phone,
                "code": "112233",
                "otp_verification_id": latest_id,
            },
        )
        self.assertEqual(bad.status_code, 400)
        self.assertIn("Invalid OTP", bad.json()["detail"])

    def test_expired_otp_rejected(self):
        phone = "9000333304"
        db = self.SessionLocal()
        db.add(
            OTPVerification(
                phone_number=phone,
                otp_hash=security.get_otp_hash("112233"),
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
                verified=False,
                attempt_count=0,
            )
        )
        db.commit()
        db.close()
        res = self.client.post(
            "/api/auth/otp/verify",
            json={"phone_number": phone, "code": "112233"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("expired", res.json()["detail"].lower())

    def test_dev_mirror_not_served_over_http(self):
        from app.services.otp_console import DEV_OTP_MIRROR_FILE

        DEV_OTP_MIRROR_FILE.write_text("secret", encoding="utf-8")
        try:
            res = self.client.get("/.dev_otp_last.txt")
            self.assertIn(res.status_code, (404, 405))
            res2 = self.client.get("/static/.dev_otp_last.txt")
            self.assertIn(res2.status_code, (404, 405))
        finally:
            if DEV_OTP_MIRROR_FILE.exists():
                DEV_OTP_MIRROR_FILE.unlink()

    def test_production_config_guard_blocks_dev_popup(self):
        with patch.object(settings, "APP_ENV", "production"):
            with patch.object(settings, "OTP_DELIVERY_MODE", "dev_popup"):
                with patch.object(settings, "OTP_DEV_POPUP_ENABLED", True):
                    errors = production_otp_config_errors()
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
