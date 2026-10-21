"""Extract explicit entities from citizen text (no inference of missing facts)."""

from __future__ import annotations

import re
from typing import Any, Dict

from app.services.multilingual_retrieval_service import normalize_stt_artifacts


def extract_entities(text: str) -> Dict[str, Any]:
    raw = normalize_stt_artifacts(text or "")
    lower = raw.lower()
    out: Dict[str, Any] = {}

    if re.search(r"\b(karnataka|karntaka|ಕರ್ನಾಟಕ|कर्नाटक)\b", lower) or "karnataka" in lower:
        out["state"] = "Karnataka"

    gender_female = (
        r"\b(woman|women|female|mahila|mahile|ಮಹಿಳ|स्त्री|mother|mom|wife)\b",
        r"\b(ತಾಯಿ|amma|mother)\b",
    )
    gender_male = (r"\b(man|men|male|husband|father|dad)\b",)
    if any(re.search(p, lower, re.I) for p in gender_female):
        out["gender"] = "female"
    elif any(re.search(p, lower, re.I) for p in gender_male):
        out["gender"] = "male"

    age_m = re.search(r"\b(\d{1,3})\s*(years? old|yrs?|year)\b", lower)
    if age_m:
        try:
            out["age"] = int(age_m.group(1))
        except ValueError:
            pass

    if re.search(r"\b(farmer|kisan|raitha|ರೈತ|किसान)\b", lower, re.I):
        out["occupation"] = "farmer"

    rel_m = re.search(r"\b(my|meri|mera|nanna|nanage)\s+(mother|father|wife|husband|son|daughter)\b", lower)
    if rel_m:
        out["relation"] = rel_m.group(2)

    if re.search(r"\bhead of (the )?family\b|\bghar ka mukhiya\b", lower, re.I):
        out["family_head"] = True

    return out
