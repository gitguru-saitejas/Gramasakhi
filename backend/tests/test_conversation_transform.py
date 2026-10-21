"""Previous-answer transform (language / rephrase) without RAG."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.services.language_service import (
    LANG_EN,
    LANG_HI,
    LANG_KN,
    detect_previous_answer_transform,
    detect_translation_intent,
    resolve_response_language,
)


class TestTransformDetection(unittest.TestCase):
    def test_kannada_please_translation_only(self):
        is_tr, only, target = detect_translation_intent("Kannada please")
        self.assertTrue(is_tr)
        self.assertTrue(only)
        self.assertEqual(target, LANG_KN)

    def test_explain_in_kannada(self):
        is_tr, only, target = detect_translation_intent("Explain in Kannada")
        self.assertTrue(only)
        self.assertEqual(target, LANG_KN)

    def test_hindi_please(self):
        d = resolve_response_language("Hindi please", conversation_language="EN")
        self.assertTrue(d.is_translation_only)
        self.assertEqual(d.response_language, LANG_HI)

    def test_explain_again_rephrase(self):
        t = detect_previous_answer_transform("Explain again", conversation_language="EN")
        self.assertTrue(t.apply)
        self.assertEqual(t.mode, "rephrase")

    def test_i_dont_understand(self):
        t = detect_previous_answer_transform(
            "I don't understand", conversation_language="KN"
        )
        self.assertTrue(t.apply)
        self.assertEqual(t.mode, "rephrase")
        self.assertEqual(t.target_language, LANG_KN)

    def _assert_rephrase(self, message: str) -> None:
        t = detect_previous_answer_transform(message, conversation_language="EN")
        self.assertTrue(t.apply, msg=message)
        self.assertEqual(t.mode, "rephrase", msg=message)

    def test_rephrase_natural_simplify_commands(self):
        for phrase in (
            "Explain simply",
            "Explain that simply",
            "Explain it simply",
            "Explain this simply",
            "Explain in simple words",
            "Explain that in simple words",
            "Say that simply",
            "Tell me simply",
            "Make it simple",
            "I don't understand, explain simply",
        ):
            with self.subTest(phrase=phrase):
                self._assert_rephrase(phrase)

    def test_documents_question_not_rephrase(self):
        t = detect_previous_answer_transform(
            "What documents do I need?",
            conversation_language="EN",
        )
        self.assertFalse(t.apply)
        self.assertEqual(t.mode, "none")


class TestTransformChatFlow(unittest.TestCase):
    def test_kannada_please_skips_rag(self):
        from app.services import conversation_service

        db = MagicMock()
        citizen = MagicMock()
        citizen.id = "c1"
        conv = MagicMock()
        conv.id = "conv1"
        conv.language = "EN"
        conv.active_scheme_context = "Gruha Lakshmi"
        conv.title = "Gruha Lakshmi"
        prev = MagicMock()
        prev.role = "assistant"
        prev.content = "Gruha Lakshmi is a Karnataka scheme for women heads of household."

        with patch.object(conversation_service, "get_owned_conversation", return_value=conv):
            with patch.object(
                conversation_service, "load_recent_messages", return_value=[prev]
            ):
                with patch.object(
                    conversation_service,
                    "store_message",
                    side_effect=lambda *a, **k: MagicMock(id="asst-kn"),
                ):
                    with patch("app.services.rag.answer_with_evidence_gate") as rag:
                        with patch(
                            "app.services.llm_service.translate_answer",
                            return_value={
                                "success": True,
                                "answer": "KN translated text about Gruha Lakshmi.",
                                "response_language": "KN",
                                "model": "m",
                                "latency_ms": 1,
                            },
                        ) as tr:
                            out = conversation_service.handle_citizen_chat(
                                db,
                                citizen,
                                message="Kannada please",
                                conversation_id="conv1",
                            )
                            rag.assert_not_called()
                            tr.assert_called_once()
                            self.assertIn("KN translated", out.get("answer", ""))
                            self.assertEqual(out.get("rewrite_method"), "translation_only")

    def test_explain_again_rephrase_skips_rag(self):
        from app.services import conversation_service

        db = MagicMock()
        citizen = MagicMock()
        citizen.id = "c1"
        conv = MagicMock()
        conv.id = "conv1"
        conv.language = "EN"
        conv.active_scheme_context = None
        conv.title = "t"
        prev = MagicMock()
        prev.role = "assistant"
        prev.content = "Apply through the official Seva Sindhu portal with Aadhaar."

        with patch.object(conversation_service, "get_owned_conversation", return_value=conv):
            with patch.object(
                conversation_service, "load_recent_messages", return_value=[prev]
            ):
                with patch.object(
                    conversation_service,
                    "store_message",
                    side_effect=lambda *a, **k: MagicMock(id="asst-rp"),
                ):
                    with patch("app.services.rag.answer_with_evidence_gate") as rag:
                        with patch(
                            "app.services.llm_service.rephrase_answer",
                            return_value={
                                "success": True,
                                "answer": "Go to Seva Sindhu and use your Aadhaar.",
                                "response_language": "EN",
                                "model": "m",
                                "latency_ms": 1,
                            },
                        ) as rp:
                            out = conversation_service.handle_citizen_chat(
                                db,
                                citizen,
                                message="Explain again",
                                conversation_id="conv1",
                            )
                            rag.assert_not_called()
                            rp.assert_called_once()
                            self.assertIn("Seva Sindhu", out.get("answer", ""))

    def test_explain_that_simply_rephrase_skips_rag(self):
        from app.services import conversation_service

        db = MagicMock()
        citizen = MagicMock()
        citizen.id = "c1"
        conv = MagicMock()
        conv.id = "conv1"
        conv.language = "EN"
        conv.active_scheme_context = "Gruha Lakshmi"
        conv.title = "Gruha Lakshmi"
        prev = MagicMock()
        prev.role = "assistant"
        prev.content = "Gruha Lakshmi is a Karnataka scheme for women heads of household."

        with patch.object(conversation_service, "get_owned_conversation", return_value=conv):
            with patch.object(
                conversation_service, "load_recent_messages", return_value=[prev]
            ):
                with patch.object(
                    conversation_service,
                    "store_message",
                    side_effect=lambda *a, **k: MagicMock(id="asst-rp2"),
                ):
                    with patch("app.services.rag.answer_with_evidence_gate") as rag:
                        with patch(
                            "app.services.llm_service.rephrase_answer",
                            return_value={
                                "success": True,
                                "answer": "Simple: women heads of household in Karnataka may qualify.",
                                "response_language": "EN",
                                "model": "m",
                                "latency_ms": 1,
                            },
                        ) as rp:
                            out = conversation_service.handle_citizen_chat(
                                db,
                                citizen,
                                message="Explain that simply",
                                conversation_id="conv1",
                            )
                            rag.assert_not_called()
                            rp.assert_called_once()
                            self.assertIn("Simple:", out.get("answer", ""))


if __name__ == "__main__":
    unittest.main()
