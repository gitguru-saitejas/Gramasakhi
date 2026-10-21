"""Optional Ollama JSON intent classifier with safe fallback."""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Optional, Tuple

from app.services.human_language.intent_models import HumanLanguageIntent

logger = logging.getLogger("gramsakhi.human_language.llm")

_VALID = {m.value for m in HumanLanguageIntent}


def _parse_llm_json(text: str) -> Optional[dict]:
    raw = (text or "").strip()
    if not raw:
        return None
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def classify_with_llm(
    query: str,
    *,
    active_scheme: Optional[str] = None,
    timeout_seconds: float = 3.0,
) -> Tuple[Optional[HumanLanguageIntent], float]:
    """Return (intent, confidence) or (None, 0) on any failure."""
    from app.core.config import settings

    if not getattr(settings, "NLU_LLM_ENABLED", False):
        return None, 0.0

    scheme_line = f"Active scheme context: {active_scheme}\n" if active_scheme else ""
    prompt = (
        "Classify the citizen message into exactly one intent JSON object.\n"
        "Intents: SCHEME_DISCOVERY, GENERAL_INFORMATION, ELIGIBILITY, PERSONAL_ELIGIBILITY, "
        "BENEFITS, BENEFITS_AMOUNT, APPLICATION_PROCESS, APPLICATION_CHANNEL, "
        "DOCUMENTS_REQUIRED, STATUS, UNKNOWN\n"
        f"{scheme_line}"
        f"Message: {query}\n"
        'Reply with JSON only: {"intent":"...","scheme_id":null,"entities":{}}\n'
    )
    try:
        from app.services.llm_service import generate_from_fixed_prompt

        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(generate_from_fixed_prompt, prompt)
            raw = fut.result(timeout=timeout_seconds)
    except FuturesTimeout:
        logger.info("NLU LLM classify timeout")
        return None, 0.0
    except Exception as exc:  # noqa: BLE001
        logger.info("NLU LLM classify failed: %s", type(exc).__name__)
        return None, 0.0

    parsed = _parse_llm_json(str(raw.get("response") or ""))
    if not parsed:
        return None, 0.0
    name = (parsed.get("intent") or "").strip().upper()
    if name not in _VALID:
        return None, 0.0
    return HumanLanguageIntent(name), 0.55
