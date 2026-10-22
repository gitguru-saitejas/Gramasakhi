"""Unit tests for staged embedding migration (mocked API; no live Gemini)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.config import settings
from app.services.embedding_migration import (
    append_staging_rows,
    build_candidate_indexes,
    load_staging_vectors,
    migration_paths,
    validate_candidate_indexes,
    validate_staging_complete,
    validate_vector,
    validate_vectors_for_ids,
)
from app.services.gemini_embedding import GeminiEmbeddingError, embed_texts


class TestEmbeddingValidation(unittest.TestCase):
    def test_dimension_mismatch(self):
        with self.assertRaises(ValueError):
            validate_vector([0.1] * 10, 768)

    def test_non_finite_rejected(self):
        with self.assertRaises(ValueError):
            validate_vector([float("nan")] + [0.1] * 767, 768)

    def test_count_mismatch(self):
        with self.assertRaises(ValueError):
            validate_vectors_for_ids([[0.1] * 768], ["a", "b"], 768)


class TestGeminiEmbeddingMocked(unittest.TestCase):
    def test_count_mismatch_raises(self):
        fake_emb = type("E", (), {"values": [0.1] * 768})()
        fake_resp = type("R", (), {"embeddings": [fake_emb]})()

        with patch.object(settings, "GEMINI_API_KEY", "k"):
            with patch.object(settings, "EMBEDDING_DIMENSIONS", 768):
                with patch("google.genai.Client") as client_cls:
                    client_cls.return_value.models.embed_content.return_value = fake_resp
                    with self.assertRaises(GeminiEmbeddingError):
                        embed_texts(["one", "two"])

    def test_wrong_dimension_raises(self):
        fake_emb = type("E", (), {"values": [0.1] * 100})()
        fake_resp = type("R", (), {"embeddings": [fake_emb]})()

        with patch.object(settings, "GEMINI_API_KEY", "k"):
            with patch.object(settings, "EMBEDDING_DIMENSIONS", 768):
                with patch("google.genai.Client") as client_cls:
                    client_cls.return_value.models.embed_content.return_value = fake_resp
                    with self.assertRaises(GeminiEmbeddingError):
                        embed_texts(["hello"])


class TestStagingWorkflow(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.root = Path(self._tmpdir.name)

    @patch("app.services.embedding_migration.migrations_root")
    def test_staging_file_roundtrip(self, mock_root):
        mock_root.return_value = self.root
        paths = migration_paths("testmigration")
        paths["base"].mkdir(parents=True)
        dim = 4
        staging = paths["staging"]
        append_staging_rows(staging, ["c1"], [[0.5, 0.6, 0.7, 0.8]], dim)
        loaded = load_staging_vectors(staging, dim)
        self.assertEqual(len(loaded), 1)

    def test_validate_staging_incomplete(self):
        class Row:
            def __init__(self, cid):
                self.id = cid

        class FakeQuery:
            def all(self):
                return [Row("c1"), Row("c2")]

        fake_db = type("DB", (), {"query": lambda self, *a, **k: FakeQuery()})()
        staging = Path(tempfile.mkdtemp()) / "staging.jsonl"
        append_staging_rows(staging, ["c1"], [[0.1] * 768], 768)
        with self.assertRaises(ValueError):
            validate_staging_complete(fake_db, staging, 768, 2)


class TestCandidateIndexBuild(unittest.TestCase):
    def test_build_candidate_from_staging_mock_db(self):
        dim = 8
        staging_path = Path(tempfile.mkdtemp()) / "staging.jsonl"
        cid = "00000000-0000-0000-0000-000000000001"
        vec = [float(i) / 10 for i in range(dim)]
        append_staging_rows(staging_path, [cid], [vec], dim)
        candidate_dir = staging_path.parent / "candidate"
        chunk = {
            "chunk_id": cid,
            "content": "PM-KISAN",
            "embedding": vec,
            "document_id": "d1",
            "chunk_index": 0,
            "metadata": {},
        }

        class FakeQuery:
            def all(self):
                return []

        fake_db = type("DB", (), {"query": lambda self, *a, **k: FakeQuery()})()

        with patch(
            "app.services.embedding_migration.load_all_chunks_from_db",
            return_value=[chunk],
        ):
            stats = build_candidate_indexes(fake_db, candidate_dir, staging_path, dim)
        self.assertEqual(stats["chunk_count"], 1)
        validate_candidate_indexes(candidate_dir, dim, 1)


if __name__ == "__main__":
    unittest.main()
