"""Voice + translation routing regressions for citizen UI contracts."""

from __future__ import annotations

import unittest

from app.services.language_service import detect_translation_intent


class TestLanguageTransformCommands(unittest.TestCase):
    def test_kannada_please_is_translation_only(self):
        is_tr, only, target = detect_translation_intent("Kannada please")
        self.assertTrue(is_tr and only)
        self.assertEqual(target, "KN")

    def test_hindi_please_is_translation_only(self):
        is_tr, only, target = detect_translation_intent("Hindi please")
        self.assertTrue(is_tr and only)
        self.assertEqual(target, "HI")


if __name__ == "__main__":
    unittest.main()
