"""Deterministic eligibility derivation from seed-backed rules and profiles."""

from __future__ import annotations

from typing import Any, Dict, Optional


def derive_eligibility(scheme: str, profile: Dict[str, Any]) -> Optional[str]:
    """Return eligible/ineligible from encoded seed rules. None if profile is incomplete."""
    if not isinstance(profile, dict) or not profile:
        return None

    if scheme == "shakti":
        if profile.get("is_man") is True:
            return "ineligible"
        if profile.get("is_woman") is True and profile.get("state_karnataka") is True:
            return "eligible"
        if profile.get("is_woman") is True and profile.get("state_karnataka") is False:
            return "ineligible"
        return None

    if scheme == "pmsby":
        if profile.get("age_in_common_band") is False:
            return "ineligible"
        if profile.get("has_savings_bank") is False:
            return "ineligible"
        if profile.get("age_in_common_band") is True and profile.get("has_savings_bank") is True:
            return "eligible"
        return None

    if scheme == "gruha-lakshmi":
        if profile.get("another_woman_already_beneficiary") is True:
            return "ineligible"
        if profile.get("is_woman") is False or profile.get("is_man") is True:
            return "ineligible"
        if profile.get("state_karnataka") is False:
            return "ineligible"
        if profile.get("is_head_of_family") is False:
            return "ineligible"
        if profile.get("aadhaar_linked_bank") is False:
            return "ineligible"
        if (
            profile.get("is_woman") is True
            and profile.get("state_karnataka") is True
            and profile.get("is_head_of_family") is True
            and profile.get("aadhaar_linked_bank") is True
        ):
            return "eligible"
        return None

    if scheme == "pmfby":
        if profile.get("is_farmer") is False:
            return "ineligible"
        if profile.get("crop_notified") is False:
            return "ineligible"
        if profile.get("area_notified") is False:
            return "ineligible"
        if profile.get("is_farmer") and profile.get("crop_notified") and profile.get("area_notified"):
            return "eligible"
        return None

    if scheme == "anna-bhagya":
        if profile.get("has_karnataka_ration_card") is True:
            return "eligible"
        if profile.get("has_karnataka_ration_card") is False:
            return "ineligible"
        return None

    return None
