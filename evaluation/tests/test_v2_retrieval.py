import unittest

from evaluation.metrics.v2.normalize import (
    canonicalize_scheme_id,
    canonicalize_source_identity,
    extract_scheme_id_from_seed_path,
    extract_scheme_id_from_url,
    normalize_numeric_expression,
    normalize_text_for_language,
)
from evaluation.metrics.v2.retrieval import relevant_scheme_ids, retrieved_scheme_ids, score_retrieval


class TestRetrievalNormalization(unittest.TestCase):
    def test_seed_path_to_scheme_id(self):
        self.assertEqual(
            extract_scheme_id_from_seed_path("backend/data/seed_schemes/pmsby_overview.txt"),
            "pmsby",
        )
        self.assertEqual(
            extract_scheme_id_from_seed_path("backend/data/demo_seeds/pmfby_scheme.txt"),
            "pmfby",
        )

    def test_myscheme_url_to_scheme_id(self):
        self.assertEqual(
            extract_scheme_id_from_url("https://www.myscheme.gov.in/schemes/pmsby#sources"),
            "pmsby",
        )
        self.assertEqual(
            extract_scheme_id_from_url("https://api.myscheme.gov.in/schemes/v6/public/schemes?slug=gruha-lakshmi&lang=en"),
            "gruha-lakshmi",
        )

    def test_metadata_scheme_id(self):
        source = {"scheme_id": "PMFBY", "source": "https://example.com"}
        self.assertEqual(canonicalize_source_identity(source), "pmfby")

    def test_demo_seed_url(self):
        self.assertEqual(extract_scheme_id_from_url("demo_seed://pmfby_scheme"), "pmfby")

    def test_case_insensitive_and_hyphen(self):
        self.assertEqual(canonicalize_scheme_id("Gruha_Lakshmi"), "gruha-lakshmi")

    def test_invalid_source_returns_none(self):
        self.assertIsNone(canonicalize_scheme_id("random-portal"))
        self.assertIsNone(canonicalize_source_identity({"source": "https://example.com/unknown"}))

    def test_relevant_scheme_ids_from_case(self):
        case = {
            "scheme": "pmsby",
            "evidence": [{"document_id": "seed-pmsby", "document_path": "backend/data/seed_schemes/pmsby_overview.txt"}],
        }
        self.assertEqual(relevant_scheme_ids(case), {"pmsby"})

    def test_unspecified_scheme_unevaluated(self):
        case = {"scheme": "unspecified", "evidence": []}
        payload = {"sources": [{"scheme_id": "pmsby", "source": "x"}]}
        result = score_retrieval(case, payload)
        self.assertEqual(result["status"], "unevaluated")

    def test_no_source_status(self):
        case = {"scheme": "pmsby", "evidence": []}
        result = score_retrieval(case, {"sources": []})
        self.assertEqual(result["status"], "no_source")
        self.assertIsNone(result["precision_at_1"])

    def test_evaluated_hit(self):
        case = {"scheme": "pmsby", "evidence": []}
        payload = {
            "sources": [
                {"scheme_id": "pmsby", "source": "https://www.myscheme.gov.in/schemes/pmsby"},
                {"scheme_id": "pmfby", "source": "other"},
            ]
        }
        result = score_retrieval(case, payload)
        self.assertEqual(result["status"], "evaluated")
        self.assertEqual(result["precision_at_1"], 1.0)
        self.assertTrue(result["hit_at_1"])

    def test_retrieved_scheme_ids_order(self):
        payload = {
            "sources": [
                {"metadata": {"scheme_id": "shakti"}},
                {"source": "demo_seed://pmfby_scheme"},
                {"metadata": {"scheme_id": "shakti"}},
            ]
        }
        self.assertEqual(retrieved_scheme_ids(payload), ["shakti", "pmfby"])


class TestNumericNormalization(unittest.TestCase):
    def test_ascii_formats(self):
        self.assertIn(2000.0, normalize_numeric_expression("Rs 2,000 per month"))
        self.assertIn(2000.0, normalize_numeric_expression("2000"))

    def test_devanagari_digits(self):
        self.assertIn(2000.0, normalize_numeric_expression("२,०००"))
        self.assertIn(2000.0, normalize_numeric_expression("२०००"))

    def test_kannada_digits(self):
        self.assertIn(2000.0, normalize_numeric_expression("೨,೦೦೦"))

    def test_text_normalization(self):
        self.assertEqual(normalize_text_for_language("  PMFBY  ", "en"), "pmfby")


if __name__ == "__main__":
    unittest.main()
