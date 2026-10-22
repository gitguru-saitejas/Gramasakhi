"""OTP delivery mode: development popup vs SMS (server-side only)."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.config import settings

logger = logging.getLogger("gramsakhi.auth")

DEV_POPUP_NOTICE = (
    "Development demo — simulated phone verification. "
    "This does not verify ownership of your phone number."
)


def is_production_env() -> bool:
    env = (settings.APP_ENV or "").strip().lower()
    return env in ("production", "prod")


def normalized_delivery_mode() -> str:
    return (settings.OTP_DELIVERY_MODE or "sms").strip().lower()


def dev_popup_active() -> bool:
    if is_production_env():
        return False
    if not settings.OTP_DEV_POPUP_ENABLED:
        return False
    return normalized_delivery_mode() == "dev_popup"


def production_otp_config_errors() -> list[str]:
    errors: list[str] = []
    mode = normalized_delivery_mode()
    if is_production_env():
        if mode == "dev_popup":
            errors.append("OTP_DELIVERY_MODE=dev_popup")
        if settings.OTP_DEV_POPUP_ENABLED:
            errors.append("OTP_DEV_POPUP_ENABLED=true")
    elif mode == "dev_popup" and not settings.OTP_DEV_POPUP_ENABLED:
        errors.append("OTP_DEV_POPUP_ENABLED must be true when OTP_DELIVERY_MODE=dev_popup")
    return errors


def validate_otp_delivery_config() -> None:
    """Refuse unsafe production OTP exposure."""
    if any(name in sys.modules for name in ("pytest", "unittest")):
        return
    errors = production_otp_config_errors()
    if errors:
        print(
            "FATAL: OTP delivery configuration invalid: " + "; ".join(errors),
            flush=True,
        )
        sys.exit(1)


def dispatch_otp_sms(phone_number: str, code: str, *, purpose: str) -> None:
    """Real SMS path — never log or return the OTP."""
    from app.services.otp_sms import deliver_otp_via_sms

    deliver_otp_via_sms(phone_number, code, purpose=purpose)


def build_otp_send_response(
    *,
    otp_verification_id: str,
    expires_at: datetime,
    dev_code: Optional[str] = None,
) -> Dict[str, Any]:
    """Public JSON for POST /otp/send (dev OTP field only when dev_popup_active)."""
    exp = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    expires_in = max(0, int((exp - now).total_seconds()))
    payload: Dict[str, Any] = {
        "message": "OTP verification code sent.",
        "otp_verification_id": otp_verification_id,
        "expires_in_seconds": expires_in,
    }
    if dev_popup_active() and dev_code:
        payload["delivery_mode"] = "dev_popup"
        payload["dev_otp"] = dev_code
        payload["dev_notice"] = DEV_POPUP_NOTICE
    else:
        payload["delivery_mode"] = "sms"
    return payload
