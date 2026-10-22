"""Gemini LLM provider tests (mocked SDK — no network/quota)."""

from __future__ import annotations

import json
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from app.core.config import settings
from app.services import llm_service, rag as rag_service
from app.services.evidence_validator import EvidenceValidator, SAFE_FALLBACK_ANSWER
from app.services.gemini_llm import GeminiGenerationError, gemini_generate
from app.services.prompt_builder import build_prompt

PM_EVIDENCE = [
    {
        "content": "PM-KISAN provides Rs 6000 per year to eligible farmers.",
        "scheme_name": "PM-KISAN",
        "source": "official government document",
        "similarity_score": 0.9,
        "hybrid_score": 0.9,
        "ce_score": 8.0,
    }
]


class TestGeminiProvider(unittest.TestCase):
    def setUp(self):
        self._orig_provider = settings.LLM_PROVIDER
        self._orig_key = settings.GEMINI_API_KEY
        self._orig_fallback = settings.LLM_FALLBACK_TO_OLLAMA

    def tearDown(self):
        settings.LLM_PROVIDER = self._orig_provider
        settings.GEMINI_API_KEY = self._orig_key
        settings.LLM_FALLBACK_TO_OLLAMA = self._orig_fallback

    @patch("app.services.gemini_llm.gemini_generate")
    def test_gemini_success(self, mock_gemini):
        settings.LLM_PROVIDER = "gemini"
        settings.LLM_FALLBACK_TO_OLLAMA = False
        mock_gemini.return_value = {
            "response": "PM-KISAN provides Rs 6000 per year to eligible farmers.",
            "model": "gemini-3.5-flash-lite",
        }
        result = llm_service.generate_answer("PM-KISAN benefits?", PM_EVIDENCE)
        self.assertTrue(result["success"])
        self.assertIn("6000", result["answer"])
        mock_gemini.assert_called_once()

    @patch("app.services.gemini_llm.gemini_generate")
    def test_gemini_empty_response(self, mock_gemini):
        settings.LLM_PROVIDER = "gemini"
        settings.LLM_FALLBACK_TO_OLLAMA = False
        mock_gemini.return_value = {"response": "   ", "model": "gemini-3.5-flash-lite"}
        result = llm_service.generate_answer("PM-KISAN benefits?", PM_EVIDENCE)
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], llm_service.LLM_EMPTY)

    def test_missing_api_key_raises_before_network(self):
        settings.GEMINI_API_KEY = ""
        with self.assertRaises(GeminiGenerationError) as ctx:
            gemini_generate("hello")
        self.assertEqual(ctx.exception.code, "missing_api_key")

    def test_invalid_provider_defaults_to_ollama_path(self):
        settings.LLM_PROVIDER = "unknown-provider"
        fake = MagicMock()
        fake.return_value = {"response": "ok from ollama", "model": "llama3.2:3b"}
        with patch.object(llm_service, "_post_generate", fake):
            raw = llm_service._generate_once("test prompt")
        self.assertEqual(raw["response"], "ok from ollama")
        fake.assert_called_once()

    @patch("app.services.gemini_llm.gemini_generate")
    def test_rate_limit_with_fallback_to_ollama(self, mock_gemini):
        settings.LLM_PROVIDER = "gemini"
        settings.LLM_FALLBACK_TO_OLLAMA = True
        mock_gemini.side_effect = GeminiGenerationError("429", code="rate_limited", retryable=True)
        ollama_payload = {"response": "fallback answer", "model": "llama3.2:3b"}
        with patch.object(llm_service, "_post_generate", return_value=ollama_payload) as mock_ollama:
            raw = llm_service._generate_once("prompt")
        self.assertEqual(raw["response"], "fallback answer")
        mock_ollama.assert_called_once()

    @patch("app.services.gemini_llm.gemini_generate")
    def test_no_fallback_when_disabled(self, mock_gemini):
        settings.LLM_PROVIDER = "gemini"
        settings.LLM_FALLBACK_TO_OLLAMA = False
        mock_gemini.side_effect = GeminiGenerationError("down", code="unavailable")
        with patch.object(llm_service, "_post_generate") as mock_ollama:
            with self.assertRaises(URLError):
                llm_service._generate_once("prompt")
            mock_ollama.assert_not_called()

    @patch("app.services.gemini_llm.gemini_generate")
    def test_both_providers_fail(self, mock_gemini):
        settings.LLM_PROVIDER = "gemini"
        settings.LLM_FALLBACK_TO_OLLAMA = True
        mock_gemini.side_effect = GeminiGenerationError("down", code="unavailable")

        def boom(_prompt):
            raise URLError("connection refused")

        with patch.object(llm_service, "_post_generate", side_effect=boom):
            with self.assertRaises(URLError):
                llm_service._generate_once("prompt")

    @patch("app.services.gemini_llm.gemini_generate")
    def test_evidence_gate_still_blocks_before_llm(self, mock_gemini):
        settings.LLM_PROVIDER = "gemini"
        db = MagicMock()
        weak = [{"content": "unrelated", "similarity_score": 0.1, "hybrid_score": 0.1}]
        with patch.object(rag_service, "hybrid_retrieve", return_value=weak):
            out = rag_service.answer_with_evidence_gate(db, "How to cook rice?", top_k=3)
        mock_gemini.assert_not_called()
        self.assertFalse(out["llm_invoked"])
        self.assertEqual(out["answer"], SAFE_FALLBACK_ANSWER)

    def test_hindi_prompt_construction(self):
        q = "पीएम किसान योजना के लाभ क्या हैं?"
        prompt = build_prompt(q, PM_EVIDENCE, response_language="HI")
        self.assertIn("Hindi", prompt)
        self.assertIn("TARGET_RESPONSE_LANGUAGE: HI", prompt)

    def test_kannada_prompt_construction(self):
        q = "ಪಿಎಂ ಕಿಸಾನ್ ಯೋಜನೆಯ ಪ್ರಯೋಜನಗಳು?"
        prompt = build_prompt(q, PM_EVIDENCE, response_language="KN")
        self.assertIn("Kannada", prompt)

    @patch("app.services.gemini_llm.gemini_generate")
    def test_ollama_provider_unchanged(self, mock_gemini):
        settings.LLM_PROVIDER = "ollama"
        payload = {
            "response": "PM-KISAN provides Rs 6000 per year via Ollama.",
            "model": "llama3.2:3b",
        }

        def fake_urlopen(req, timeout=None):
            class _R:
                def read(self):
                    return json.dumps(payload).encode()

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

            return _R()

        with patch.object(llm_service.urllib.request, "urlopen", side_effect=fake_urlopen):
            result = llm_service.generate_answer("PM-KISAN?", PM_EVIDENCE)
        self.assertTrue(result["success"])
        mock_gemini.assert_not_called()


if __name__ == "__main__":
    unittest.main()
