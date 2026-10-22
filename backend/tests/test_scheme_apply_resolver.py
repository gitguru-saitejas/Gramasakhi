"""Verified scheme Apply Online URL resolution."""

from __future__ import annotations

import unittest

from app.services.myscheme_service import (
    is_trusted_government_apply_url,
    resolve_scheme_apply_targets,
)


class TestSchemeApplyResolver(unittest.TestCase):
    def test_rejects_unsafe_schemes(self):
        self.assertFalse(is_trusted_government_apply_url("javascript:alert(1)"))
        self.assertFalse(is_trusted_government_apply_url("https://evil.example/apply"))

    def test_pm_kisan_slug_information_page(self):
        result = resolve_scheme_apply_targets("PM-KISAN")
        self.assertEqual(result["scheme_id"], "pm-kisan")
        self.assertIn("myscheme.gov.in/schemes/pm-kisan", result["official_information_url"])
        self.assertFalse(result["has_verified_application_url"])

    def test_trusted_application_url_preserved(self):
        portal = "https://pmkisan.gov.in/"
        result = resolve_scheme_apply_targets(
            "PM-KISAN",
            application_url=portal,
        )
        self.assertEqual(result["application_url"], portal)
        self.assertTrue(result["has_verified_application_url"])

    def test_apply_online_button_must_not_use_chat_prompt(self):
        """Regression: Apply Online uses external URL, not a chat message."""
        result = resolve_scheme_apply_targets(
            "PM-KISAN",
            application_url="https://pmkisan.gov.in/",
        )
        self.assertTrue(result["application_url"].startswith("https://"))


if __name__ == "__main__":
    unittest.main()
