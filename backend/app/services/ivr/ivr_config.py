"""IVR-A6 production configuration validation."""

from __future__ import annotations

from typing import List

from app.core.config import Settings
from app.services.ivr.public_url import validate_ivr_public_base_url


def ivr_production_validation_required(settings: Settings) -> bool:
    """Chat-only web deploys use IVR_PROVIDER=mock and skip telephony env requirements."""
    if not hasattr(settings, "IVR_PROVIDER"):
        return True
    provider = str(getattr(settings, "IVR_PROVIDER", "") or "mock").strip().lower()
    return provider not in ("mock", "disabled", "off")


def collect_ivr_production_config_errors(settings: Settings) -> List[str]:
    """Return human-readable config errors; empty list means OK."""
    if settings.APP_ENV.strip().lower() != "production":
        return []
    if not ivr_production_validation_required(settings):
        return []

    errors: List[str] = []

    if not (settings.IVR_PUBLIC_BASE_URL or "").strip():
        errors.append("IVR_PUBLIC_BASE_URL is required in production.")

    try:
        validate_ivr_public_base_url(settings.IVR_PUBLIC_BASE_URL, app_env=settings.APP_ENV)
    except ValueError as exc:
        errors.append(f"IVR_PUBLIC_BASE_URL invalid: {exc}")

    account_id = (settings.IVR_CITIZEN_ACCOUNT_ID or "").strip()
    account_phone = (settings.IVR_SYSTEM_ACCOUNT_PHONE or "").strip()
    if not account_id and not account_phone:
        errors.append("IVR_CITIZEN_ACCOUNT_ID or IVR_SYSTEM_ACCOUNT_PHONE required in production.")

    if settings.OTP_DEV_RETRIEVAL_ENABLED:
        errors.append("OTP_DEV_RETRIEVAL_ENABLED must be false in production.")

    if settings.OTP_CONSOLE_SIMULATOR_ENABLED and not settings.DATABASE_URL.startswith("sqlite"):
        errors.append("OTP_CONSOLE_SIMULATOR_ENABLED should be false in production.")

    secret = str(getattr(settings, "IVR_WEBHOOK_SHARED_SECRET", "") or "").strip()
    if not secret:
        errors.append(
            "IVR_WEBHOOK_SHARED_SECRET is required when IVR telephony is enabled in production."
        )

    return errors


def assert_ivr_production_config(settings: Settings) -> None:
    errors = collect_ivr_production_config_errors(settings)
    if errors:
        joined = "; ".join(errors)
        raise RuntimeError(f"IVR production configuration invalid: {joined}")
