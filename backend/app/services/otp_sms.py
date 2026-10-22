"""SMS OTP delivery hook (production path)."""

from __future__ import annotations

import logging

logger = logging.getLogger("gramsakhi.auth")


def _mask_phone(phone_number: str) -> str:
    digits = (phone_number or "").strip()
    if len(digits) <= 4:
        return "***"
    return f"+91 ***{digits[-4:]}"


def deliver_otp_via_sms(phone_number: str, code: str, *, purpose: str) -> None:
    """
    Dispatch OTP via configured SMS provider.
    Never log the OTP value — only masked phone and purpose.
    """
    # Integrate Exotel/other provider here when credentials are configured.
    logger.info(
        "otp_sms_dispatch purpose=%s phone=%s (code not logged)",
        purpose,
        _mask_phone(phone_number),
    )
