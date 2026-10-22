"""Cloud vs local runtime expectations."""

from __future__ import annotations

import sys
from typing import List

from app.core.config import settings


def runtime_profile() -> str:
    return (settings.RUNTIME_PROFILE or "local").strip().lower()


def is_cloud_runtime() -> bool:
    return runtime_profile() == "cloud"


def is_production_env() -> bool:
    return (settings.APP_ENV or "").strip().lower() in ("production", "prod")


def cloud_config_errors() -> List[str]:
    if not is_cloud_runtime():
        return []
    errors: List[str] = []
    if (settings.LLM_PROVIDER or "").strip().lower() != "gemini":
        errors.append("LLM_PROVIDER must be gemini in cloud runtime")
    if not (settings.GEMINI_API_KEY or "").strip():
        errors.append("GEMINI_API_KEY is required in cloud runtime")
    if (settings.EMBEDDING_PROVIDER or "").strip().lower() != "gemini":
        errors.append("EMBEDDING_PROVIDER must be gemini in cloud runtime")
    if settings.LLM_FALLBACK_TO_OLLAMA:
        errors.append("LLM_FALLBACK_TO_OLLAMA must be false in cloud runtime")
    if is_production_env():
        from app.services.otp_delivery import production_otp_config_errors

        errors.extend(production_otp_config_errors())
    return errors


def validate_runtime_profile() -> None:
    if any(m in sys.modules for m in ("pytest", "unittest")):
        return
    errors = cloud_config_errors()
    if errors:
        print("FATAL: Cloud runtime configuration invalid: " + "; ".join(errors), flush=True)
        sys.exit(1)


def should_warm_cross_encoder_at_startup() -> bool:
    """CrossEncoder + PyTorch can exceed 512MB; defer load until first rerank when disabled."""
    if not settings.HYBRID_RERANK_ENABLED:
        return False
    if not getattr(settings, "STARTUP_WARM_CROSS_ENCODER", True):
        return False
    return True
