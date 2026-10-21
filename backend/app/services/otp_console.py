"""Development-only OTP terminal simulator (never exposes OTP via API)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger("gramsakhi.auth")
uvicorn_error = logging.getLogger("uvicorn.error")

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEV_OTP_MIRROR_FILE = _BACKEND_ROOT / ".dev_otp_last.txt"


def otp_console_simulator_enabled() -> bool:
    if not settings.OTP_CONSOLE_SIMULATOR_ENABLED:
        return False
    env = (settings.APP_ENV or "").strip().lower()
    if env in ("production", "prod"):
        return False
    return True


def _mask_mobile(phone_number: str) -> str:
    digits = (phone_number or "").strip()
    if len(digits) <= 4:
        return "***"
    return f"+91 ***{digits[-4:]}"


def _write_dev_otp_mirror(code: str, masked: str) -> None:
    try:
        DEV_OTP_MIRROR_FILE.write_text(
            "\n".join(
                [
                    "========================================",
                    "VERIFICATION OTP",
                    f"Mobile: {masked}",
                    f"OTP: {code}",
                    "========================================",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    except OSError:
        pass


def emit_dev_otp_to_terminal(phone_number: str, code: str, *, purpose: str) -> None:
    """Surface OTP in terminal logs and a local dev mirror file (development only)."""
    masked = _mask_mobile(phone_number)
    if not otp_console_simulator_enabled():
        logger.info("otp_sent purpose=%s phone=%s", purpose, masked)
        return

    banner = (
        "\n========================================\n"
        "VERIFICATION OTP\n"
        f"Mobile: {masked}\n"
        f"OTP: {code}\n"
        "========================================\n"
    )
    log_line = f"VERIFICATION OTP | Mobile: {masked} | OTP: {code} | purpose={purpose}"

    uvicorn_error.warning(log_line)
    logger.warning(log_line)

    for stream in (sys.stderr, sys.stdout):
        try:
            stream.write(banner)
            stream.flush()
        except OSError:
            pass

    _write_dev_otp_mirror(code, masked)
