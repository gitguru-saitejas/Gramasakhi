"""Phase 5 — grounded Ollama generation unit tests (mocked HTTP, no live Ollama)."""

from __future__ import annotations

import json
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import numpy as np

from app.core.config import settings
from app.services import llm_service, rag as rag_service
from app.services.evidence_validator import (
    SAFE_FALLBACK_ANSWER,
    EvidenceValidator,
)
from app.services.prompt_builder import (
    build_prompt,
    detect_language,
    format_evidence_block,
)


PM_KISAN_EVIDENCE = [
    {
        "content": (
            "PM-KISAN Samman Nidhi provides income support of Rs 6000 per year "
            "to eligible landholding farmer families, paid in three equal installments."
        ),
        "scheme_name": "PM-KISAN",
        "source": "official government document",
        "ministry": "Ministry of Agriculture",
        "page": 12,
        "similarity_score": 0.92,
        "hybrid_score": 0.91,
        "ce_score": 8.5,
    },
    {
        "content": (
            "Under PM-KISAN, benefit installments are credited directly to the "
            "farmer's bank account through Direct Benefit Transfer."
        ),
        "scheme_name": "PM-KISAN",
        "source": "official government document",
        "page": 13,
        "similarity_score": 0.88,
        "hybrid_score": 0.87,
        "ce_score": 7.9,
    },
]


def _fake_urlopen_factory(payload: dict, status: int = 200):
    """Return a context-manager mock for urllib.request.urlopen."""

    class _Resp:
        def __init__(self):
            self._data = json.dumps(payload).encode("utf-8")
            self.status = status

        def read(self):
            return self._data

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def _urlopen(req, timeout=None):
        return _Resp()

    return _urlopen


def _emb(seed: str, dim: int = 32) -> list:
    rng = np.random.default_rng(abs(hash(seed)) % (2**32))
    v = rng.normal(size=dim).astype(np.float32)
    v = v / (np.linalg.norm(v) + 1e-12)
    return v.tolist()


class TestPromptBuilder(unittest.TestCase):
    def test_evidence_format_includes_metadata(self):
        block = format_evidence_block(PM_KISAN_EVIDENCE)
        self.assertIn("[EVIDENCE 1]", block)
        self.assertIn("Scheme: PM-KISAN", block)
        self.assertIn("Source: official government document", block)
        self.assertIn("Page: 12", block)
        self.assertIn("Rs 6000", block)

    def test_build_prompt_includes_query_evidence_language(self):
        prompt = build_prompt(
            "What are the benefits of PM-KISAN?",
            PM_KISAN_EVIDENCE,
            language="English",
        )
        self.assertIn("QUESTION:", prompt)
        self.assertIn("What are the benefits of PM-KISAN?", prompt)
        self.assertIn("LANGUAGE:\nEnglish", prompt)
        self.assertIn("EVIDENCE:", prompt)
        self.assertIn("PM-KISAN", prompt)
        self.assertIn("Do not invent", prompt)

    def test_kannada_language_in_prompt(self):
        q = "ಪಿಎಂ ಕಿಸಾನ್ ಯೋಜನೆಯ ಪ್ರಯೋಜನಗಳು ಏನು?"
        prompt = build_prompt(q, PM_KISAN_EVIDENCE)
        self.assertIn("LANGUAGE:\nKannada", prompt)
        self.assertIn("TARGET_RESPONSE_LANGUAGE: KN", prompt)
        self.assertEqual(detect_language(q), "Kannada")


class TestLlmServiceGeneration(unittest.TestCase):
    def setUp(self):
        settings.LLM_PROVIDER = "ollama"
        settings.LLM_FALLBACK_TO_OLLAMA = False

    def test_basic_generation_calls_ollama_once(self):
        fake = _fake_urlopen_factory(
            {"response": "PM-KISAN gives farmers Rs 6000 per year in three installments."}
        )
        with patch.object(llm_service.urllib.request, "urlopen", side_effect=fake) as mock_open:
            result = llm_service.generate_answer(
                "What are the benefits of PM-KISAN?",
                PM_KISAN_EVIDENCE,
            )
            self.assertTrue(result["success"])
            self.assertIn("6000", result["answer"])
            self.assertEqual(mock_open.call_count, 1)
            req = mock_open.call_args[0][0]
            body = json.loads(req.data.decode("utf-8"))
            self.assertFalse(body["stream"])
            self.assertAlmostEqual(body["options"]["temperature"], 0.1)
            self.assertIn("What are the benefits of PM-KISAN?", body["prompt"])
            self.assertIn("Rs 6000", body["prompt"])
            self.assertIn(settings.OLLAMA_LLM_MODEL or "llama3.2:3b", body["model"])

    def test_grounding_uses_supplied_evidence(self):
        fake = _fake_urlopen_factory(
            {"response": "Based on evidence, benefits are Rs 6000 per year."}
        )
        with patch.object(llm_service.urllib.request, "urlopen", side_effect=fake) as mock_open:
            result = llm_service.generate_answer("What are the benefits?", PM_KISAN_EVIDENCE)
            self.assertTrue(result["success"])
            prompt = json.loads(mock_open.call_args[0][0].data.decode("utf-8"))["prompt"]
            self.assertIn("income support of Rs 6000", prompt)

    def test_multilingual_prompt_language_kannada(self):
        fake = _fake_urlopen_factory(
            {"response": "PM-KISAN \u0caf\u0ccb\u0c9c\u0ca8\u0cc6\u0caf \u0caa\u0ccd\u0cb0\u0caf\u0ccb\u0c9c\u0ca8 \u0cb0\u0cc2. 6000."}
        )
        q = "\u0caa\u0cbf\u0c8e\u0c82 \u0c95\u0cbf\u0cb8\u0cbe\u0ca8\u0ccd \u0caa\u0ccd\u0cb0\u0caf\u0ccb\u0c9c\u0ca8\u0c97\u0cb3\u0cc1 \u0c8f\u0ca8\u0cc1?"
        with patch.object(llm_service.urllib.request, "urlopen", side_effect=fake) as mock_open:
            result = llm_service.generate_answer(q, PM_KISAN_EVIDENCE, response_language="KN")
            self.assertTrue(result["success"], result)
            prompt = json.loads(mock_open.call_args[0][0].data.decode("utf-8"))["prompt"]
            self.assertIn("LANGUAGE:\nKannada", prompt)
            self.assertEqual(result["language"], "Kannada")

    def test_ollama_http_500_controlled_error(self):
        def boom(req, timeout=None):
            raise HTTPError(
                url="http://localhost:11434/api/generate",
                code=500,
                msg="server error",
                hdrs=None,
                fp=BytesIO(b"error"),
            )

        with patch.object(llm_service.urllib.request, "urlopen", side_effect=boom):
            result = llm_service.generate_answer(
                "What are the benefits of PM-KISAN?",
                PM_KISAN_EVIDENCE,
            )
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], llm_service.LLM_UNAVAILABLE)
        self.assertNotIn("answer", result)

    def test_ollama_timeout_controlled_error(self):
        def boom(req, timeout=None):
            raise TimeoutError("timed out")

        with patch.object(llm_service.urllib.request, "urlopen", side_effect=boom):
            result = llm_service.generate_answer(
                "What are the benefits of PM-KISAN?",
                PM_KISAN_EVIDENCE,
            )
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], llm_service.LLM_TIMEOUT)

    def test_connection_error_controlled(self):
        def boom(req, timeout=None):
            raise URLError("connection refused")

        with patch.object(llm_service.urllib.request, "urlopen", side_effect=boom):
            result = llm_service.generate_answer(
                "What are the benefits?",
                PM_KISAN_EVIDENCE,
            )
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], llm_service.LLM_UNAVAILABLE)

    def test_empty_response_is_failure(self):
        fake = _fake_urlopen_factory({"response": "   "})
        with patch.object(llm_service.urllib.request, "urlopen", side_effect=fake):
            result = llm_service.generate_answer("What are the benefits?", PM_KISAN_EVIDENCE)
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], llm_service.LLM_EMPTY)


class TestEvidenceGateWithLlm(unittest.TestCase):
    def setUp(self):
        settings.LLM_PROVIDER = "ollama"
        settings.LLM_FALLBACK_TO_OLLAMA = False
        settings.EVIDENCE_GATE_ENABLED = True

    def test_unsupported_penalties_never_calls_ollama(self):
        """Evidence only has benefits; question about penalties should FAIL gate."""
        docs = [
            {
                "content": "PM-KISAN provides income support benefits of Rs 6000 per year.",
                "scheme_name": "PM-KISAN",
                "similarity_score": 0.95,
                "hybrid_score": 0.95,
                "ce_score": 9.0,
            }
        ]
        db = MagicMock()
        with patch.object(rag_service, "hybrid_retrieve", return_value=docs):
            with patch.object(llm_service.urllib.request, "urlopen") as mock_open:
                with patch.object(
                    rag_service, "_call_llm_after_validation"
                ) as llm_entry:
                    out = rag_service.answer_with_evidence_gate(
                        db, "What are the penalties under PM-KISAN?", top_k=3
                    )
                    llm_entry.assert_not_called()
                    mock_open.assert_not_called()
                    self.assertFalse(out["validated"])
                    self.assertFalse(out["llm_invoked"])
                    self.assertEqual(out["answer"], SAFE_FALLBACK_ANSWER)

    def test_unrelated_question_never_calls_ollama(self):
        docs = [
            {
                "content": "PM Kisan benefits for farmers.",
                "scheme_name": "PM-KISAN",
                "similarity_score": 0.2,
                "hybrid_score": 0.2,
            }
        ]
        db = MagicMock()
        with patch.object(rag_service, "hybrid_retrieve", return_value=docs):
            with patch.object(rag_service, "_call_llm_after_validation") as llm:
                out = rag_service.answer_with_evidence_gate(db, "How do I cook rice?", top_k=3)
                llm.assert_not_called()
                self.assertFalse(out["llm_invoked"])
                self.assertEqual(out["answer"], SAFE_FALLBACK_ANSWER)

    def test_pass_invokes_llm_and_preserves_sources(self):
        docs = list(PM_KISAN_EVIDENCE)

        def embed_fn(text: str):
            base = np.array(_emb("pm-kisan-cluster"), dtype=np.float32)
            noise = np.array(_emb(text[:50]), dtype=np.float32) * 0.05
            v = base + noise
            v = v / (np.linalg.norm(v) + 1e-12)
            return v.tolist()

        validator = EvidenceValidator(embed_fn=embed_fn)
        db = MagicMock()
        fake = _fake_urlopen_factory(
            {"response": "PM-KISAN gives Rs 6000 per year to eligible farmers."}
        )
        with patch.object(rag_service, "hybrid_retrieve", return_value=docs):
            with patch.object(llm_service.urllib.request, "urlopen", side_effect=fake) as mock_open:
                out = rag_service.answer_with_evidence_gate(
                    db,
                    "What are the benefits of PM-KISAN?",
                    top_k=3,
                    validator=validator,
                )
                self.assertTrue(out["validated"])
                self.assertTrue(out["llm_invoked"])
                self.assertEqual(mock_open.call_count, 1)
                self.assertIn("6000", out["answer"])
                self.assertTrue(out["sources"])
                # Sources come from retrieval metadata — not invented by LLM
                src0 = out["sources"][0]
                self.assertEqual(src0.get("scheme_name"), "PM-KISAN")
                self.assertEqual(src0.get("page"), 12)
                self.assertEqual(src0.get("source"), "official government document")

    def test_llm_failure_after_pass_is_controlled(self):
        docs = list(PM_KISAN_EVIDENCE)

        def embed_fn(text: str):
            base = np.array(_emb("pm-kisan-cluster"), dtype=np.float32)
            noise = np.array(_emb(text[:50]), dtype=np.float32) * 0.05
            v = base + noise
            v = v / (np.linalg.norm(v) + 1e-12)
            return v.tolist()

        validator = EvidenceValidator(embed_fn=embed_fn)
        db = MagicMock()

        def boom(req, timeout=None):
            raise HTTPError(
                "http://localhost:11434/api/generate",
                500,
                "err",
                None,
                BytesIO(b"err"),
            )

        with patch.object(rag_service, "hybrid_retrieve", return_value=docs):
            with patch.object(llm_service.urllib.request, "urlopen", side_effect=boom):
                out = rag_service.answer_with_evidence_gate(
                    db,
                    "What are the benefits of PM-KISAN?",
                    top_k=3,
                    validator=validator,
                )
        self.assertTrue(out["validated"])
        self.assertTrue(out["llm_invoked"])
        self.assertEqual(out["reason"], "llm_unavailable")
        self.assertEqual(out["answer"], rag_service.LLM_CONTROLLED_FAILURE_ANSWER)
        self.assertEqual(out["error"], llm_service.LLM_UNAVAILABLE)
        # Still return retrieval sources; never invent citations
        self.assertTrue(out["sources"])
        self.assertEqual(out["sources"][0].get("scheme_name"), "PM-KISAN")


if __name__ == "__main__":
    unittest.main()
