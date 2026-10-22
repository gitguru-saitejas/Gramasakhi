"""Google Gemini API text generation (server-side only)."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any, Dict, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class GeminiGenerationError(Exception):
    """Controlled failure from Gemini API."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "unavailable",
        retryable: bool = False,
        http_status: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.http_status = http_status


def get_gemini_model() -> str:
    return (settings.GEMINI_MODEL or "gemini-3.5-flash-lite").strip()


def _extract_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if text:
        return str(text).strip()
    candidates = getattr(response, "candidates", None) or []
    for cand in candidates:
        content = getattr(cand, "content", None)
        if not content:
            continue
        parts = getattr(content, "parts", None) or []
        chunks = []
        for part in parts:
            t = getattr(part, "text", None)
            if t:
                chunks.append(str(t))
        if chunks:
            return "\n".join(chunks).strip()
    return ""


def _is_rate_limit(exc: Exception) -> bool:
    status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if status in (429, 503):
        return True
    msg = str(exc).lower()
    return "429" in msg or "rate" in msg or "quota" in msg or "resource_exhausted" in msg


def _is_auth_error(exc: Exception) -> bool:
    status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if status in (401, 403):
        return True
    msg = str(exc).lower()
    return "api key" in msg or "permission" in msg or "unauthenticated" in msg


def gemini_generate(prompt: str) -> Dict[str, Any]:
    """
    Single-shot Gemini generate_content call.
    Returns Ollama-compatible shape: {"response": str, "model": str}.
    """
    api_key = (settings.GEMINI_API_KEY or "").strip()
    if not api_key:
        raise GeminiGenerationError("GEMINI_API_KEY not configured", code="missing_api_key")

    model = get_gemini_model()
    if not (prompt or "").strip():
        raise GeminiGenerationError("Empty prompt", code="invalid_request", retryable=False)

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    timeout_s = float(settings.GEMINI_TIMEOUT_SECONDS)
    config = types.GenerateContentConfig(
        temperature=float(settings.GEMINI_TEMPERATURE),
        max_output_tokens=int(settings.GEMINI_MAX_OUTPUT_TOKENS),
    )

    max_attempts = max(1, int(settings.GEMINI_MAX_RETRIES) + 1)
    last_exc: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(
                    client.models.generate_content,
                    model=model,
                    contents=prompt,
                    config=config,
                )
                response = fut.result(timeout=timeout_s)
            text = _extract_text(response)
            if not text:
                raise GeminiGenerationError(
                    "Gemini returned empty text",
                    code="empty_response",
                    retryable=False,
                )
            logger.info(
                "gemini_generation_ok model=%s attempt=%s prompt_chars=%s",
                model,
                attempt,
                len(prompt),
            )
            return {"response": text, "model": model}
        except GeminiGenerationError:
            raise
        except FuturesTimeout as exc:
            last_exc = exc
            if attempt < max_attempts:
                continue
            raise GeminiGenerationError(
                "Gemini request timed out",
                code="timeout",
                retryable=True,
            ) from exc
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            retryable = _is_rate_limit(exc)
            if _is_auth_error(exc):
                raise GeminiGenerationError(
                    "Gemini authentication failed",
                    code="invalid_api_key",
                    retryable=False,
                    http_status=getattr(exc, "code", None),
                ) from exc
            if retryable and attempt < max_attempts:
                delay = min(8.0, 0.5 * (2 ** (attempt - 1)))
                logger.warning(
                    "gemini_retryable_error attempt=%s err=%s sleep=%.1fs",
                    attempt,
                    type(exc).__name__,
                    delay,
                )
                time.sleep(delay)
                continue
            code = "rate_limited" if retryable else "unavailable"
            raise GeminiGenerationError(
                f"Gemini request failed: {type(exc).__name__}",
                code=code,
                retryable=retryable,
                http_status=getattr(exc, "code", None),
            ) from exc

    raise GeminiGenerationError(
        f"Gemini request failed: {type(last_exc).__name__ if last_exc else 'unknown'}",
        code="unavailable",
    )


def check_gemini_llm() -> Dict[str, Any]:
    """Health helper — does not consume quota when API key is missing."""
    model = get_gemini_model()
    result: Dict[str, Any] = {
        "gemini_configured": bool((settings.GEMINI_API_KEY or "").strip()),
        "model": model,
        "detail": None,
        "gemini_available": False,
    }
    if not result["gemini_configured"]:
        result["detail"] = "GEMINI_API_KEY not set"
        return result
    try:
        from google import genai

        client = genai.Client(api_key=settings.GEMINI_API_KEY.strip())
        # Lightweight list call to verify credentials (no generation quota).
        listed = client.models.list()
        next(iter(listed), None)
        result["gemini_available"] = True
        result["detail"] = "ok"
    except Exception as exc:  # noqa: BLE001
        result["detail"] = f"{type(exc).__name__}"
        if _is_auth_error(exc):
            result["detail"] = "invalid_api_key"
    return result
