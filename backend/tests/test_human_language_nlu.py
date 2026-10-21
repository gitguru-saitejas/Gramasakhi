"""Shared human-language understanding (NLU) tests."""

from __future__ import annotations

import unittest

from app.services.human_language import HumanLanguageIntent, interpret_human_language
from app.services.human_language.patterns import classify_from_patterns
from app.services.citizen_assistance import CitizenIntent, build_assistance_context


class TestEnglishNLU(unittest.TestCase):
    def test_application_process(self):
        intent, _ = classify_from_patterns("How can I apply?")
        self.assertEqual(intent, HumanLanguageIntent.APPLICATION_PROCESS)

    def test_application_channel(self):
        intent, _ = classify_from_patterns("Where do I apply?")
        self.assertEqual(intent, HumanLanguageIntent.APPLICATION_CHANNEL)

    def test_documents(self):
        intent, _ = classify_from_patterns("What documents do I need?")
        self.assertEqual(intent, HumanLanguageIntent.DOCUMENTS_REQUIRED)

    def test_benefits_amount(self):
        intent, _ = classify_from_patterns("How much will I get?")
        self.assertEqual(intent, HumanLanguageIntent.BENEFITS_AMOUNT)

    def test_benefits(self):
        intent, _ = classify_from_patterns("What does this scheme give?")
        self.assertEqual(intent, HumanLanguageIntent.BENEFITS)

    def test_personal_eligibility(self):
        intent, _ = classify_from_patterns("Can I get this?")
        self.assertEqual(intent, HumanLanguageIntent.PERSONAL_ELIGIBILITY)

    def test_ambiguous_how(self):
        intent, _ = classify_from_patterns("How?")
        self.assertEqual(intent, HumanLanguageIntent.UNKNOWN)


class TestHindiKannadaNLU(unittest.TestCase):
    def test_hindi_apply(self):
        intent, _ = classify_from_patterns("इसके लिए आवेदन कैसे करूं?")
        self.assertEqual(intent, HumanLanguageIntent.APPLICATION_PROCESS)

    def test_hindi_documents(self):
        intent, _ = classify_from_patterns("कौन से कागज चाहिए?")
        self.assertEqual(intent, HumanLanguageIntent.DOCUMENTS_REQUIRED)

    def test_hindi_personal(self):
        intent, _ = classify_from_patterns("मैं इसके लिए पात्र हूं?")
        self.assertEqual(intent, HumanLanguageIntent.PERSONAL_ELIGIBILITY)

    def test_kannada_apply(self):
        intent, _ = classify_from_patterns("ಅರ್ಜಿ ಹೇಗೆ ಹಾಕಬೇಕು?")
        self.assertEqual(intent, HumanLanguageIntent.APPLICATION_PROCESS)

    def test_kannada_documents(self):
        intent, _ = classify_from_patterns("ಯಾವ ದಾಖಲೆ ಬೇಕು?")
        self.assertEqual(intent, HumanLanguageIntent.DOCUMENTS_REQUIRED)

    def test_kannada_personal(self):
        intent, _ = classify_from_patterns("ನಾನು ಇದಕ್ಕೆ ಅರ್ಹನಾ?")
        self.assertEqual(intent, HumanLanguageIntent.PERSONAL_ELIGIBILITY)


class TestCodeMixedNLU(unittest.TestCase):
    def test_hinglish_apply(self):
        intent, _ = classify_from_patterns("Iske liye apply kaise karna hai?")
        self.assertEqual(intent, HumanLanguageIntent.APPLICATION_PROCESS)

    def test_kanglish_documents(self):
        intent, _ = classify_from_patterns("Documents yenu beku?")
        self.assertEqual(intent, HumanLanguageIntent.DOCUMENTS_REQUIRED)

    def test_kanglish_apply(self):
        intent, _ = classify_from_patterns("Idakke apply hege madodu?")
        self.assertEqual(intent, HumanLanguageIntent.APPLICATION_PROCESS)


class TestContextResolution(unittest.TestCase):
    def test_gruha_lakshmi_followups(self):
        history = [{"role": "user", "content": "Tell me about Gruha Lakshmi."}]
        ctx = build_assistance_context(
            original_query="How can I apply?",
            conversation_history=history,
            conversation_active_scheme="Gruha Lakshmi",
            rewrite_active_scheme="Gruha Lakshmi",
        )
        self.assertEqual(ctx.intent, CitizenIntent.APPLICATION)
        self.assertEqual(ctx.detected_scheme, "Gruha Lakshmi")
        self.assertEqual(ctx.nlu_intent, HumanLanguageIntent.APPLICATION_PROCESS.value)

        ctx2 = build_assistance_context(
            original_query="What documents do I need?",
            conversation_history=history + [{"role": "assistant", "content": "..."}],
            conversation_active_scheme="Gruha Lakshmi",
            rewrite_active_scheme="Gruha Lakshmi",
        )
        self.assertEqual(ctx2.intent, CitizenIntent.DOCUMENTS)
        self.assertEqual(ctx2.nlu_intent, HumanLanguageIntent.DOCUMENTS_REQUIRED.value)

        ctx3 = build_assistance_context(
            original_query="How much will I get?",
            conversation_history=history,
            conversation_active_scheme="Gruha Lakshmi",
            rewrite_active_scheme="Gruha Lakshmi",
        )
        self.assertEqual(ctx3.nlu_intent, HumanLanguageIntent.BENEFITS_AMOUNT.value)

    def test_normalized_query_includes_scheme(self):
        nlu = interpret_human_language(
            "How can I get this?",
            conversation_active_scheme="Gruha Lakshmi",
        )
        self.assertIn("Gruha Lakshmi", nlu.normalized_query)
        self.assertEqual(nlu.intent, HumanLanguageIntent.APPLICATION_PROCESS)


if __name__ == "__main__":
    unittest.main()
