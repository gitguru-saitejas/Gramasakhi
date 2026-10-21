"""Universal conversational NLU cases (not the official benchmark)."""

from __future__ import annotations

import unittest

from app.services.citizen_assistance import CitizenIntent, build_assistance_context
from app.services.human_language import HumanLanguageIntent, interpret_human_language
from app.services.human_language.conversational import detect_language_change, detect_multi_intents
from app.services.language_service import detect_translation_intent

_GRUHA_CTX = {
    "conversation_active_scheme": "Gruha Lakshmi",
    "rewrite_active_scheme": "Gruha Lakshmi",
    "conversation_history": [{"role": "user", "content": "Tell me about Gruha Lakshmi."}],
}


def _nlu(query: str, **ctx):
    return interpret_human_language(query, use_llm=False, **ctx)


class TestGruhaLakshmiConversation(unittest.TestCase):
    """Spec §31 conversation thread."""

    def test_step2_how_not_unknown_with_context(self):
        r = _nlu("How?", **_GRUHA_CTX)
        self.assertNotEqual(r.intent, HumanLanguageIntent.UNKNOWN)
        self.assertFalse(r.needs_clarification)
        self.assertEqual(r.scheme_name, "Gruha Lakshmi")

    def test_step3_apply(self):
        r = _nlu("How can I apply?", **_GRUHA_CTX)
        self.assertEqual(r.intent, HumanLanguageIntent.APPLICATION_PROCESS)

    def test_step4_documents(self):
        r = _nlu("Documents?", **_GRUHA_CTX)
        self.assertEqual(r.intent, HumanLanguageIntent.DOCUMENTS_REQUIRED)

    def test_step5_amount(self):
        r = _nlu("How much?", **_GRUHA_CTX)
        self.assertEqual(r.intent, HumanLanguageIntent.BENEFITS_AMOUNT)

    def test_step6_kannada_please(self):
        r = _nlu("Kannada please", **_GRUHA_CTX)
        self.assertIn("LANGUAGE_CHANGE", r.conversational_tags)
        is_tr, only, target = detect_translation_intent("Kannada please")
        self.assertTrue(only)
        self.assertEqual(target, "KN")

    def test_step7_personal_eligibility(self):
        r = _nlu("Can I get it?", **_GRUHA_CTX)
        self.assertEqual(r.intent, HumanLanguageIntent.PERSONAL_ELIGIBILITY)


class TestShortWithoutContext(unittest.TestCase):
    def test_documents_asks_scheme(self):
        ctx = build_assistance_context(original_query="documents")
        self.assertEqual(ctx.intent, CitizenIntent.CLARIFICATION)
        self.assertTrue(ctx.nlu_needs_clarification)
        self.assertIn("scheme", (ctx.nlu_clarification_prompt or "").lower())


class TestSchemeSwitch(unittest.TestCase):
    def test_pmfby_after_gruha(self):
        history = [
            {"role": "user", "content": "Tell me about Gruha Lakshmi."},
            {"role": "assistant", "content": "..."},
            {"role": "user", "content": "What about PMFBY?"},
        ]
        r = _nlu(
            "How do I apply?",
            conversation_history=history,
            conversation_active_scheme="PMFBY",
        )
        self.assertIn(r.intent, (
            HumanLanguageIntent.APPLICATION_PROCESS,
            HumanLanguageIntent.APPLICATION_CHANNEL,
        ))


class TestRuralColloquial(unittest.TestCase):
    _PHRASES = (
        ("Nanage idu sigutta?", HumanLanguageIntent.PERSONAL_ELIGIBILITY),
        ("Idu heg sigutte?", HumanLanguageIntent.APPLICATION_PROCESS),
        ("Nan en madbeku?", HumanLanguageIntent.APPLICATION_PROCESS),
        ("Yelli hogbeku?", HumanLanguageIntent.APPLICATION_CHANNEL),
        ("Yaava documents beku?", HumanLanguageIntent.DOCUMENTS_REQUIRED),
        ("Amount estu?", HumanLanguageIntent.BENEFITS_AMOUNT),
        ("Nanage eligible aa?", HumanLanguageIntent.PERSONAL_ELIGIBILITY),
        ("Idakke apply hege?", HumanLanguageIntent.APPLICATION_PROCESS),
        ("Enu madbeku?", HumanLanguageIntent.APPLICATION_PROCESS),
        ("Nan case alli?", HumanLanguageIntent.PERSONAL_ELIGIBILITY),
        ("Mujhe milega?", HumanLanguageIntent.PERSONAL_ELIGIBILITY),
        ("Main kya karu?", HumanLanguageIntent.APPLICATION_PROCESS),
        ("Kahan jana hai?", HumanLanguageIntent.APPLICATION_CHANNEL),
        ("Kaunse kagaz chahiye?", HumanLanguageIntent.DOCUMENTS_REQUIRED),
        ("Kitna paisa?", HumanLanguageIntent.BENEFITS_AMOUNT),
        ("Mere liye hai?", HumanLanguageIntent.PERSONAL_ELIGIBILITY),
        ("Ab kya karna hai?", HumanLanguageIntent.APPLICATION_PROCESS),
    )

    def test_rural_with_scheme(self):
        for phrase, expected in self._PHRASES:
            with self.subTest(phrase=phrase):
                r = _nlu(phrase, **_GRUHA_CTX)
                self.assertEqual(r.intent, expected, msg=phrase)


class TestSTTArtifacts(unittest.TestCase):
    _STT = (
        ("idu heg madbeku", HumanLanguageIntent.APPLICATION_PROCESS),
        ("nanage idu sigutta", HumanLanguageIntent.PERSONAL_ELIGIBILITY),
        ("documents yenu beku", HumanLanguageIntent.DOCUMENTS_REQUIRED),
        ("is ke liye apply kaise", HumanLanguageIntent.APPLICATION_PROCESS),
        ("kitna paisa milega", HumanLanguageIntent.BENEFITS_AMOUNT),
    )

    def test_stt_with_scheme(self):
        for phrase, expected in self._STT:
            with self.subTest(phrase=phrase):
                r = _nlu(phrase, **_GRUHA_CTX)
                self.assertEqual(r.intent, expected)


class TestCodeMix(unittest.TestCase):
    def test_kanglish(self):
        r = _nlu("Documents yenu beku?", **_GRUHA_CTX)
        self.assertEqual(r.intent, HumanLanguageIntent.DOCUMENTS_REQUIRED)
        r2 = _nlu("Apply hege madodu?", **_GRUHA_CTX)
        self.assertEqual(r2.intent, HumanLanguageIntent.APPLICATION_PROCESS)
        r3 = _nlu("Amount estu?", **_GRUHA_CTX)
        self.assertEqual(r3.intent, HumanLanguageIntent.BENEFITS_AMOUNT)


class TestMultiIntent(unittest.TestCase):
    def test_compound_question(self):
        q = "What is this scheme, who can get it and how do I apply?"
        found = detect_multi_intents(q)
        self.assertGreaterEqual(len(found), 2)


class TestLanguageCommands(unittest.TestCase):
    def test_hindi_script(self):
        is_lang, code = detect_language_change("हिंदी में बताइए")
        self.assertTrue(is_lang)
        self.assertEqual(code, "HI")

    def test_kannada_dalli(self):
        is_lang, code = detect_language_change("Kannada dalli heli")
        self.assertTrue(is_lang)
        self.assertEqual(code, "KN")


def _bulk_short_followups():
    """Generate many one-word follow-ups with Gruha context."""
    tokens = (
        ("money", HumanLanguageIntent.BENEFITS_AMOUNT),
        ("apply", HumanLanguageIntent.APPLICATION_PROCESS),
        ("status", HumanLanguageIntent.STATUS),
        ("eligibility", HumanLanguageIntent.ELIGIBILITY),
        ("where?", HumanLanguageIntent.APPLICATION_CHANNEL),
        ("how to get?", HumanLanguageIntent.APPLICATION_PROCESS),
        ("what next?", HumanLanguageIntent.APPLICATION_PROCESS),
        ("what about documents?", HumanLanguageIntent.DOCUMENTS_REQUIRED),
        ("what about money?", HumanLanguageIntent.BENEFITS_AMOUNT),
        ("and eligibility?", HumanLanguageIntent.ELIGIBILITY),
        ("for me?", HumanLanguageIntent.PERSONAL_ELIGIBILITY),
        ("me?", HumanLanguageIntent.PERSONAL_ELIGIBILITY),
        ("papers?", HumanLanguageIntent.DOCUMENTS_REQUIRED),
        ("kagaz?", HumanLanguageIntent.DOCUMENTS_REQUIRED),
        ("yelli?", HumanLanguageIntent.APPLICATION_CHANNEL),
        ("kahan?", HumanLanguageIntent.APPLICATION_CHANNEL),
        ("kitna?", HumanLanguageIntent.BENEFITS_AMOUNT),
        ("estu?", HumanLanguageIntent.BENEFITS_AMOUNT),
        ("benefits?", HumanLanguageIntent.BENEFITS),
        ("eligible?", HumanLanguageIntent.PERSONAL_ELIGIBILITY),
    )
    return tokens


class TestBulkShortFollowups(unittest.TestCase):
    def test_all(self):
        for token, expected in _bulk_short_followups():
            with self.subTest(token=token):
                r = _nlu(token, **_GRUHA_CTX)
                self.assertEqual(r.intent, expected)


class TestEnglishVariants(unittest.TestCase):
    _VARIANTS = (
        "How can I get it?",
        "What should I do?",
        "Where should I go?",
        "Which office?",
        "What papers?",
        "What proof?",
        "How much money?",
        "Can my mother get this?",
        "Will I get this?",
        "Is this for me?",
        "Application status?",
        "Did they approve it?",
        "Can I do it online?",
        "Which website?",
    )

    def test_with_context_not_unknown(self):
        for q in self._VARIANTS:
            with self.subTest(q=q):
                r = _nlu(q, **_GRUHA_CTX)
                self.assertNotEqual(r.intent, HumanLanguageIntent.UNKNOWN, msg=q)


class TestHindiKannadaFullQuestions(unittest.TestCase):
    _Q = (
        "इसके लिए क्या करना है?",
        "कहाँ जाना है?",
        "कौन से कागज चाहिए?",
        "मुझे ये मिलेगा?",
        "ಇದನ್ನು ಪಡೆಯೋದು ಹೇಗೆ?",
        "ಯಾವ ದಾಖಲೆ ಬೇಕು?",
        "ನಾನು ಇದಕ್ಕೆ ಅರ್ಹನಾ?",
    )

    def test_not_unknown(self):
        for q in self._Q:
            with self.subTest(q=q):
                r = _nlu(q, conversation_active_scheme="Gruha Lakshmi")
                self.assertNotEqual(r.intent, HumanLanguageIntent.UNKNOWN)


class TestNormalizedQuery(unittest.TestCase):
    def test_includes_scheme_for_short_how(self):
        r = _nlu("How?", **_GRUHA_CTX)
        self.assertIn("Gruha Lakshmi", r.normalized_query)


class TestRetrievalRoutingFlag(unittest.TestCase):
    def test_how_uses_nlu_query(self):
        from app.services.human_language.retrieval_routing import should_use_nlu_retrieval_query

        self.assertTrue(should_use_nlu_retrieval_query("How?", rewrite_was_applied=False))
        self.assertTrue(should_use_nlu_retrieval_query("Documents?", rewrite_was_applied=False))


# Pad to 100+ parameterized checks via duplicated intent families (unique utterances).
_EXTRA_UTTERANCES = [
    "How do I get this?",
    "I want this",
    "I need this benefit",
    "Where can I get it?",
    "Do I qualify?",
    "Am I eligible?",
    "Who is eligible?",
    "What do I get?",
    "What will I receive?",
    "Tell me about Gruha Lakshmi",
    "What is Gruha Lakshmi?",
    "How can I receive it?",
    "What all should I submit?",
    "Which papers should I submit?",
    "Can I apply?",
    "Will this be available to me?",
    "Has it come?",
    "Where is my application?",
    "Then?",
    "Next?",
    "Why?",
    "When?",
    "Hindi please",
    "English please",
    "Mujhe ye milega?",
    "Iske liye kya karna hai?",
    "Kahan apply karna hai?",
    "Kaunse documents chahiye?",
    "Nanage sigbeku",
    "Eligibility ideya?",
    "Where hogbeku?",
]


class TestExtraUtterances(unittest.TestCase):
    def test_gruha_context(self):
        for q in _EXTRA_UTTERANCES:
            with self.subTest(q=q):
                r = _nlu(q, **_GRUHA_CTX)
                if q.lower() in ("hindi please", "english please"):
                    self.assertIn("LANGUAGE_CHANGE", r.conversational_tags)
                elif q.lower().startswith("who is eligible"):
                    self.assertEqual(r.intent, HumanLanguageIntent.ELIGIBILITY)
                elif q.lower() in ("tell me about gruha lakshmi", "what is gruha lakshmi?"):
                    self.assertEqual(r.intent, HumanLanguageIntent.GENERAL_INFORMATION)
                else:
                    self.assertNotEqual(r.intent, HumanLanguageIntent.UNKNOWN, msg=q)


class TestConversationDataset(unittest.TestCase):
    """100+ cases from tests/data/nlu_conversation_cases.json (not the benchmark)."""

    @classmethod
    def setUpClass(cls):
        import json
        from pathlib import Path

        path = Path(__file__).resolve().parent / "data" / "nlu_conversation_cases.json"
        cls.cases = json.loads(path.read_text(encoding="utf-8"))
        assert len(cls.cases) >= 100, len(cls.cases)

    def test_dataset_cases(self):
        for row in self.cases:
            q = row["q"]
            scheme = row.get("scheme")
            with self.subTest(q=q, scheme=scheme):
                r = _nlu(
                    q,
                    conversation_active_scheme=scheme,
                    rewrite_active_scheme=scheme,
                )
                if row.get("tag") == "LANGUAGE_CHANGE":
                    self.assertIn("LANGUAGE_CHANGE", r.conversational_tags)
                elif row.get("clarify"):
                    self.assertTrue(r.needs_clarification)
                elif row.get("allow_unknown"):
                    pass
                elif row.get("not_intent"):
                    self.assertNotEqual(r.intent.value, row["not_intent"])
                else:
                    self.assertEqual(r.intent.value, row["intent"])


if __name__ == "__main__":
    unittest.main()
