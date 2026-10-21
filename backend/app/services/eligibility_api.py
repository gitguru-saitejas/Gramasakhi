"""API-facing eligibility status mapping (Phase 2).

Internal evaluation uses ELIGIBLE / NOT_ELIGIBLE / CANNOT_DETERMINE.
The public API exposes eligible / ineligible / uncertain.
"""

from __future__ import annotations

from typing import Optional

_INTERNAL_TO_API = {
    "ELIGIBLE": "eligible",
    "NOT_ELIGIBLE": "ineligible",
    "CANNOT_DETERMINE": "uncertain",
}

_API_TO_INTERNAL = {v: k for k, v in _INTERNAL_TO_API.items()}


def eligibility_status_for_api(status: Optional[str]) -> Optional[str]:
    if not status:
        return None
    upper = status.strip().upper()
    if upper in _INTERNAL_TO_API:
        return _INTERNAL_TO_API[upper]
    lower = status.strip().lower()
    if lower in _API_TO_INTERNAL:
        return lower
    return status


def normalize_eligibility_status(status: Optional[str]) -> Optional[str]:
    """Normalize any known status variant to internal enum value."""
    if not status:
        return None
    upper = status.strip().upper()
    if upper in _INTERNAL_TO_API:
        return upper
    lower = status.strip().lower()
    return _API_TO_INTERNAL.get(lower, upper)
