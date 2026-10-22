"""Grounded LLM generation for GramSakhi (Phase 5).

Supports configurable providers (Gemini API or local Ollama). Call ONLY after
Evidence Sufficiency Validator PASS. Does not retrieve documents or talk to the
database — it receives validated evidence.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.language_quality import (
    build_regen_instruction,
    cache_get_translation,
    cache_put_translation,
    validate_answer_quality,
)
from app.services.language_service import (
    build_rephrase_prompt,
    build_translation_prompt,
    controlled_language_failure_message,
    language_name,
    normalize_language_code,
    resolve_response_language,
)
from app.services.gemini_llm import GeminiGenerationError
from app.services.prompt_builder import build_prompt, detect_language

logger = logging.getLogger(__name__)

LLM_UNAVAILABLE = "LLM service unavailable"
LLM_TIMEOUT = "LLM service timeout"
LLM_EMPTY = "LLM returned an empty response"


def get_ollama_base_url() -> str:
    """Prefer OLLAMA_BASE_URL; fall back to existing OLLAMA_API_URL."""
    base = (settings.OLLAMA_BASE_URL or settings.OLLAMA_API_URL or "").strip()
    return base.rstrip("/")


def get_llm_provider() -> str:
    return (settings.LLM_PROVIDER or "ollama").strip().lower()


def get_llm_model() -> str:
    if get_llm_provider() == "gemini":
        from app.services.gemini_llm import get_gemini_model

        return get_gemini_model()
    return (settings.OLLAMA_LLM_MODEL or settings.OLLAMA_MODEL or "llama3.2:3b").strip()


def clean_llm_response(text: str) -> str:
    """Strip obvious protocol artifacts; do not rewrite factual content."""
    if not text:
        return ""
    cleaned = text.strip()
    # Common chat wrappers some models emit
    for marker in ("Assistant:", "GramSakhi:", "Answer:"):
        if cleaned.startswith(marker):
            cleaned = cleaned[len(marker) :].lstrip()
    return cleaned.strip()


def _post_generate(prompt: str) -> Dict[str, Any]:
    """Low-level Ollama /api/generate call. Not for use outside this module."""
    url = f"{get_ollama_base_url()}/api/generate"
    model = get_llm_model()
    options: Dict[str, Any] = {
        "temperature": float(settings.OLLAMA_LLM_TEMPERATURE),
    }
    if settings.OLLAMA_LLM_NUM_PREDICT and int(settings.OLLAMA_LLM_NUM_PREDICT) > 0:
        options["num_predict"] = int(settings.OLLAMA_LLM_NUM_PREDICT)

    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": options,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    timeout = float(settings.OLLAMA_LLM_TIMEOUT_SECONDS)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


def check_ollama_llm() -> Dict[str, Any]:
    """Health helper: reachable + whether configured generation model is listed."""
    base = get_ollama_base_url()
    model = get_llm_model()
    result = {
        "ollama_available": False,
        "model_available": False,
        "base_url": base,
        "model": model,
        "detail": None,
    }
    if not base:
        result["detail"] = "OLLAMA_BASE_URL / OLLAMA_API_URL not configured"
        return result
    try:
        req = urllib.request.Request(f"{base}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5.0) as response:
            data = json.loads(response.read().decode("utf-8"))
        result["ollama_available"] = True
        names = []
        for m in data.get("models") or []:
            name = m.get("name") or m.get("model") or ""
            if name:
                names.append(name)
        # Accept exact match or same model:tag prefix
        result["model_available"] = any(
            name == model or name.startswith(f"{model}") for name in names
        )
        if not result["model_available"]:
            result["detail"] = f"Model '{model}' not found in ollama list"
        else:
            result["detail"] = "ok"
    except Exception as e:  # noqa: BLE001
        result["detail"] = f"{type(e).__name__}: {e}"
    return result


def _generate_once(prompt: str) -> Dict[str, Any]:
    """
    Single completion call using configured provider.
    Optional fallback: Gemini → Ollama when LLM_FALLBACK_TO_OLLAMA is true.
    Raises urllib errors for transport failures (Ollama) or mapped Gemini failures.
    """
    provider = get_llm_provider()
    chain: List[tuple[str, Any]] = []
    from app.services.runtime_profile import is_cloud_runtime

    allow_ollama_fallback = settings.LLM_FALLBACK_TO_OLLAMA and not is_cloud_runtime()
    if provider == "gemini":
        chain.append(("gemini", None))
        if allow_ollama_fallback:
            chain.append(("ollama", _post_generate))
    elif provider == "ollama":
        chain.append(("ollama", _post_generate))
    else:
        logger.warning("Unknown LLM_PROVIDER=%s; using ollama", provider)
        chain.append(("ollama", _post_generate))

    last_gemini_code: Optional[str] = None
    for idx, (name, fn) in enumerate(chain):
        try:
            if name == "gemini":
                from app.services.gemini_llm import gemini_generate

                raw = gemini_generate(prompt)
            else:
                raw = fn(prompt)
            logger.info(
                "LLM provider_used=%s model=%s",
                name,
                (raw.get("model") if isinstance(raw, dict) else None) or get_llm_model(),
            )
            return raw
        except GeminiGenerationError as exc:
            last_gemini_code = exc.code
            logger.warning(
                "Gemini generation failed code=%s retryable=%s",
                exc.code,
                exc.retryable,
            )
            if name == "gemini" and idx + 1 < len(chain):
                continue
            if exc.code == "empty_response":
                return {"response": "", "model": get_llm_model()}
            reason = f"gemini:{exc.code}"
            if exc.code == "timeout":
                reason = "gemini:timeout"
            raise urllib.error.URLError(reason) from exc
        except TimeoutError:
            if idx + 1 < len(chain):
                continue
            raise
        except urllib.error.HTTPError:
            if idx + 1 < len(chain):
                continue
            raise
        except (urllib.error.URLError, ConnectionError, OSError):
            if idx + 1 < len(chain):
                continue
            raise

    raise urllib.error.URLError(f"gemini:{last_gemini_code or 'unavailable'}")


def generate_from_fixed_prompt(prompt: str) -> Dict[str, Any]:
    """Constrained single-shot generation (e.g. eligibility explanation)."""
    try:
        raw = _generate_once(prompt)
    except Exception:  # noqa: BLE001
        return {"model": get_llm_model(), "response": ""}
    model = (raw.get("model") if isinstance(raw, dict) else None) or get_llm_model()
    return {
        "model": model,
        "response": raw.get("response") or "",
    }


def generate_answer(
    query: str,
    evidence: List[Dict[str, Any]],
    language: Optional[str] = None,
    conversation_context: Any = None,
    response_language: Optional[str] = None,
    strict_language_mode: bool = False,
    assistance_context: Any = None,
) -> Dict[str, Any]:
    """
    Generate a grounded GramSakhi answer via the configured LLM provider.

    After generation, runs the language quality gate and may regenerate
    up to MAX_LANGUAGE_REGEN_ATTEMPTS times. Does not bypass Evidence Validator
    (caller must only invoke after PASS).
    """
    model = get_llm_model()
    code = normalize_language_code(response_language) or normalize_language_code(language)
    if not code:
        code = resolve_response_language(query or "").response_language
    lang = language_name(code)
    started = time.perf_counter()
    max_attempts = max(1, int(getattr(settings, "MAX_LANGUAGE_REGEN_ATTEMPTS", 2)) + 1)
    gate_on = bool(getattr(settings, "LANGUAGE_QUALITY_GATE_ENABLED", True))

    if not (query or "").strip():
        return {
            "success": False,
            "error": "Empty query",
            "model": model,
            "language": lang,
            "response_language": code,
            "latency_ms": 0,
        }
    if not evidence:
        return {
            "success": False,
            "error": "No evidence provided",
            "model": model,
            "language": lang,
            "response_language": code,
            "latency_ms": 0,
        }

    from app.services.evidence_validator import has_substantive_content

    substantive = [d for d in evidence if has_substantive_content(d)]
    if not substantive:
        return {
            "success": False,
            "error": "No substantive evidence provided",
            "model": model,
            "language": lang,
            "response_language": code,
            "latency_ms": 0,
        }
    evidence = substantive

    regen_note = None
    last_quality = None
    answer = ""
    attempt = 0
    transport_error = None

    for attempt in range(1, max_attempts + 1):
        prompt = build_prompt(
            query,
            evidence,
            language=language,
            conversation_context=conversation_context,
            response_language=code,
            strict_language_mode=strict_language_mode,
            regen_note=regen_note,
            assistance_context=assistance_context,
        )
        logger.info(
            "LLM request started model=%s evidence_chunks=%s language=%s "
            "response_language=%s generation_attempt=%s",
            model,
            len(evidence),
            lang,
            code,
            attempt,
        )
        try:
            raw = _generate_once(prompt)
        except TimeoutError:
            transport_error = LLM_TIMEOUT
            break
        except urllib.error.HTTPError as e:
            logger.warning(
                "LLM generation HTTP error model=%s status=%s", model, e.code
            )
            transport_error = LLM_UNAVAILABLE
            break
        except urllib.error.URLError as e:
            reason = str(getattr(e, "reason", e))
            if reason.startswith("gemini:timeout") or "timeout" in reason.lower():
                transport_error = LLM_TIMEOUT
            else:
                transport_error = LLM_UNAVAILABLE
            logger.warning(
                "LLM generation transport failure model=%s reason=%s",
                model,
                reason[:80],
            )
            break
        except (ConnectionError, OSError) as e:
            logger.warning(
                "LLM generation connection failure model=%s err=%s",
                model,
                type(e).__name__,
            )
            transport_error = LLM_UNAVAILABLE
            break
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "LLM generation unexpected error model=%s err=%s",
                model,
                type(e).__name__,
            )
            transport_error = LLM_UNAVAILABLE
            break

        answer = clean_llm_response(raw.get("response") or "")
        if not answer:
            transport_error = LLM_EMPTY
            break

        if not gate_on:
            last_quality = None
            break

        last_quality = validate_answer_quality(
            answer,
            response_language=code,
            evidence=evidence,
            strict_language_mode=strict_language_mode,
            mode="generation",
            query=query,
        )
        logger.info(
            "language_validation attempt=%s passed=%s failures=%s",
            attempt,
            last_quality.passed,
            last_quality.failures,
        )
        if last_quality.passed:
            break
        if attempt >= max_attempts:
            break
        regen_note = build_regen_instruction(last_quality, response_language=code)

    latency_ms = int((time.perf_counter() - started) * 1000)

    if transport_error and not answer:
        return {
            "success": False,
            "error": transport_error,
            "model": model,
            "language": lang,
            "response_language": code,
            "latency_ms": latency_ms,
            "generation_attempt": attempt,
        }

    if gate_on and last_quality is not None and not last_quality.passed:
        logger.warning(
            "quality_gate_result=FAIL after attempts=%s failures=%s",
            attempt,
            last_quality.failures,
        )
        return {
            "success": False,
            "error": "language_quality_failed",
            "answer": controlled_language_failure_message(code, kind="generation"),
            "model": model,
            "language": lang,
            "response_language": code,
            "latency_ms": latency_ms,
            "generation_attempt": attempt,
            "quality_failures": list(last_quality.failures),
            "quality_scores": dict(last_quality.scores),
            "controlled_failure": True,
        }

    logger.info(
        "LLM generation completed model=%s latency_ms=%s response_language=%s "
        "generation_attempt=%s quality_gate_result=%s",
        model,
        latency_ms,
        code,
        attempt,
        "PASS" if not last_quality or last_quality.passed else "FAIL",
    )
    return {
        "success": True,
        "answer": answer,
        "model": model,
        "language": lang,
        "response_language": code,
        "latency_ms": latency_ms,
        "generation_attempt": attempt,
        "quality_scores": dict(last_quality.scores) if last_quality else {},
    }


def rephrase_answer(
    previous_answer: str,
    *,
    response_language: str,
    strict_language_mode: bool = False,
) -> Dict[str, Any]:
    """Simplify/rephrase prior assistant answer in the same language (no RAG)."""
    model = get_llm_model()
    code = normalize_language_code(response_language) or "EN"
    lang = language_name(code)
    started = time.perf_counter()
    if not (previous_answer or "").strip():
        return {
            "success": False,
            "error": "No previous answer to rephrase",
            "model": model,
            "language": lang,
            "response_language": code,
            "latency_ms": 0,
        }
    prompt = build_rephrase_prompt(previous_answer, response_language=code)
    try:
        raw = _generate_once(prompt)
    except Exception as e:  # noqa: BLE001
        logger.warning("LLM rephrase failure err=%s", type(e).__name__)
        return {
            "success": False,
            "error": LLM_UNAVAILABLE,
            "model": model,
            "language": lang,
            "response_language": code,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    answer = clean_llm_response(raw.get("response") or "")
    if not answer:
        return {
            "success": False,
            "error": LLM_EMPTY,
            "model": model,
            "language": lang,
            "response_language": code,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    return {
        "success": True,
        "answer": answer,
        "model": model,
        "language": lang,
        "response_language": code,
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "knowledge_source": "rephrase",
    }


def translate_answer(
    previous_answer: str,
    *,
    target_language: str,
    strict_language_mode: bool = False,
) -> Dict[str, Any]:
    """Translate a prior assistant answer. Does not retrieve or validate evidence."""
    model = get_llm_model()
    code = normalize_language_code(target_language) or "EN"
    lang = language_name(code)
    started = time.perf_counter()
    max_attempts = max(1, int(getattr(settings, "MAX_LANGUAGE_REGEN_ATTEMPTS", 2)) + 1)
    gate_on = bool(getattr(settings, "LANGUAGE_QUALITY_GATE_ENABLED", True))

    if not (previous_answer or "").strip():
        return {
            "success": False,
            "error": "No previous answer to translate",
            "model": model,
            "language": lang,
            "response_language": code,
            "latency_ms": 0,
        }

    cached = cache_get_translation(previous_answer, code)
    if cached:
        logger.info("translation cache hit target=%s", code)
        return {
            "success": True,
            "answer": cached,
            "model": model,
            "language": lang,
            "response_language": code,
            "latency_ms": 0,
            "knowledge_source": "translation",
            "cached": True,
        }

    regen_note = None
    last_quality = None
    answer = ""
    attempt = 0
    transport_error = None

    for attempt in range(1, max_attempts + 1):
        prompt = build_translation_prompt(
            previous_answer, target_language=code, regen_note=regen_note
        )
        logger.info(
            "LLM translation started model=%s target=%s generation_attempt=%s",
            model,
            code,
            attempt,
        )
        try:
            raw = _generate_once(prompt)
        except TimeoutError:
            transport_error = LLM_TIMEOUT
            break
        except Exception as e:  # noqa: BLE001
            logger.warning("LLM translation failure err=%s", type(e).__name__)
            transport_error = LLM_UNAVAILABLE
            break

        answer = clean_llm_response(raw.get("response") or "")
        if not answer:
            transport_error = LLM_EMPTY
            break

        if not gate_on or code == "EN":
            break

        last_quality = validate_answer_quality(
            answer,
            response_language=code,
            source_text=previous_answer,
            strict_language_mode=strict_language_mode,
            mode="translation",
        )
        logger.info(
            "translation language_validation attempt=%s passed=%s failures=%s",
            attempt,
            last_quality.passed,
            last_quality.failures,
        )
        if last_quality.passed:
            break
        if attempt >= max_attempts:
            break
        regen_note = build_regen_instruction(last_quality, response_language=code)

    latency_ms = int((time.perf_counter() - started) * 1000)

    if transport_error and not answer:
        return {
            "success": False,
            "error": transport_error,
            "model": model,
            "language": lang,
            "response_language": code,
            "latency_ms": latency_ms,
            "generation_attempt": attempt,
        }

    if gate_on and code != "EN" and last_quality is not None and not last_quality.passed:
        return {
            "success": False,
            "error": "translation_quality_failed",
            "answer": controlled_language_failure_message(code, kind="translation"),
            "model": model,
            "language": lang,
            "response_language": code,
            "latency_ms": latency_ms,
            "generation_attempt": attempt,
            "quality_failures": list(last_quality.failures),
            "controlled_failure": True,
            "knowledge_source": "translation",
        }

    if answer and (not gate_on or code == "EN" or (last_quality and last_quality.passed)):
        cache_put_translation(previous_answer, code, answer)

    return {
        "success": True,
        "answer": answer,
        "model": model,
        "language": lang,
        "response_language": code,
        "latency_ms": latency_ms,
        "knowledge_source": "translation",
        "generation_attempt": attempt,
        "quality_scores": dict(last_quality.scores) if last_quality else {},
    }
