"""Canonical identity and text normalization for benchmark v2 evaluation."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, List, Optional, Set

# Known scheme aliases → canonical scheme_id (lowercase hyphenated).
_KNOWN_ALIASES: dict[str, str] = {
    "pmfby": "pmfby",
    "pm-fby": "pmfby",
    "pradhan mantri fasal bima yojana": "pmfby",
    "pmsby": "pmsby",
    "pm-sby": "pmsby",
    "pradhan mantri suraksha bima yojana": "pmsby",
    "shakti": "shakti",
    "shakti scheme": "shakti",
    "anna-bhagya": "anna-bhagya",
    "anna bhagya": "anna-bhagya",
    "gruha-lakshmi": "gruha-lakshmi",
    "gruha lakshmi": "gruha-lakshmi",
    "gruha-lakshmi scheme": "gruha-lakshmi",
}

_MYSCHEME_SLUG = re.compile(r"/schemes/([a-z0-9-]+)", re.I)
_API_SLUG = re.compile(r"[?&]slug=([a-z0-9-]+)", re.I)
_DEMO_SEED = re.compile(r"demo_seed://([a-z0-9_-]+)", re.I)
_SEED_DOC_ID = re.compile(r"^seed-([a-z0-9-]+)$", re.I)
_SEED_PATH = re.compile(r"/([a-z0-9_-]+?)(?:_(?:scheme|overview))?\.txt$", re.I)
_DEMO_SEED_SUFFIX = re.compile(r"^(?P<base>[a-z0-9-]+)(?:_|-)scheme$", re.I)

# Devanagari (U+0966–U+096F) and Kannada (U+CE6–U+CEF) digits → ASCII.
_DEVANAGARI_ZERO = ord("\u0966")
_KANNADA_ZERO = ord("\u0ce6")


def _slugify_token(value: str) -> str:
    text = unicodedata.normalize("NFKC", (value or "").strip().lower())
    text = text.replace("_", "-").replace(" ", "-")
    text = re.sub(r"[^a-z0-9-]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text


def canonicalize_scheme_id(value: Any) -> Optional[str]:
    """Normalize arbitrary scheme identifiers to a canonical scheme_id."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None

    lowered = raw.lower()
    if lowered.endswith("_scheme"):
        lowered = lowered[: -len("_scheme")]
    if lowered in _KNOWN_ALIASES:
        return _KNOWN_ALIASES[lowered]

    for extractor in (
        extract_scheme_id_from_url,
        extract_scheme_id_from_seed_path,
        extract_scheme_id_from_document_id,
    ):
        found = extractor(raw)
        if found:
            return found

    slug = _slugify_token(raw)
    demo_match = _DEMO_SEED_SUFFIX.match(slug)
    if demo_match:
        slug = demo_match.group("base")
    if slug in _KNOWN_ALIASES:
        return _KNOWN_ALIASES[slug]

    # Accept already-canonical ids for benchmark schemes.
    if slug in {"pmfby", "pmsby", "shakti", "anna-bhagya", "gruha-lakshmi"}:
        return slug

    return None


def extract_scheme_id_from_url(url: str) -> Optional[str]:
    if not url:
        return None
    text = str(url).strip()
    for pattern in (_API_SLUG, _MYSCHEME_SLUG, _DEMO_SEED):
        for match in pattern.finditer(text):
            found = canonicalize_scheme_id(match.group(1))
            if found:
                return found
    return None


def extract_scheme_id_from_seed_path(path: str) -> Optional[str]:
    if not path:
        return None
    text = str(path).replace("\\", "/")
    match = _SEED_PATH.search(text)
    if match:
        token = match.group(1).replace("_", "-")
        return canonicalize_scheme_id(token)
    return extract_scheme_id_from_url(text)


def extract_scheme_id_from_document_id(document_id: str) -> Optional[str]:
    if not document_id:
        return None
    match = _SEED_DOC_ID.match(str(document_id).strip())
    if match:
        return canonicalize_scheme_id(match.group(1))
    return None


def canonicalize_source_identity(source_item: dict[str, Any]) -> Optional[str]:
    """Resolve one API source record to a canonical scheme_id."""
    if not isinstance(source_item, dict):
        return None

    metadata = source_item.get("metadata") or {}
    candidates = [
        source_item.get("scheme_id"),
        metadata.get("scheme_id"),
        source_item.get("document_id"),
        source_item.get("id"),
        source_item.get("source"),
        source_item.get("document_url"),
        source_item.get("url"),
        source_item.get("source_url"),
        source_item.get("document_title"),
        source_item.get("scheme_name"),
    ]
    for candidate in candidates:
        found = canonicalize_scheme_id(candidate)
        if found:
            return found
        if isinstance(candidate, str):
            found = extract_scheme_id_from_url(candidate)
            if found:
                return found
            found = extract_scheme_id_from_seed_path(candidate)
            if found:
                return found
    return None


def _convert_indic_digits(text: str) -> str:
    chars: list[str] = []
    for ch in text:
        code = ord(ch)
        if _DEVANAGARI_ZERO <= code <= _DEVANAGARI_ZERO + 9:
            chars.append(chr(ord("0") + code - _DEVANAGARI_ZERO))
        elif _KANNADA_ZERO <= code <= _KANNADA_ZERO + 9:
            chars.append(chr(ord("0") + code - _KANNADA_ZERO))
        else:
            chars.append(ch)
    return "".join(chars)


def normalize_text_for_language(text: str, language: str = "en") -> str:
    """Lowercase, NFKC, collapse whitespace, optionally map Indic digits."""
    blob = unicodedata.normalize("NFKC", text or "")
    if language in ("hi", "kn"):
        blob = _convert_indic_digits(blob)
    blob = blob.lower()
    blob = re.sub(r"\s+", " ", blob).strip()
    return blob


def normalize_numeric_expression(text: str) -> List[float]:
    """Extract comparable numeric values from mixed-format expressions."""
    if not text:
        return []
    blob = _convert_indic_digits(unicodedata.normalize("NFKC", text))
    # Remove common currency / unit prefixes for number tokenization.
    cleaned = re.sub(r"(?i)\b(rs\.?|inr|₹|rupees?)\s*", " ", blob)
    values: Set[float] = set()
    for match in re.finditer(r"-?\d+(?:[.,]\d+)*", cleaned):
        token = match.group(0).replace(",", "")
        try:
            values.add(float(token))
        except ValueError:
            continue
    return sorted(values)


def numeric_phrase_values(phrase: str) -> List[float]:
    return normalize_numeric_expression(phrase)


def is_primarily_numeric_phrase(phrase: str) -> bool:
    stripped = re.sub(r"[\s,._-]+", "", phrase or "")
    return bool(stripped) and stripped.isdigit()
