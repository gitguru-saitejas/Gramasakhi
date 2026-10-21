import unittest

from evaluation.metrics.compute import binary_prf, percentile, precision_at_k, recall_at_k
from evaluation.metrics.evaluate import keyphrase_correctness, score_case, unsupported_detection


class TestMetricCalculations(unittest.TestCase):
    def test_precision_and_recall(self):
        relevant = ["seed-pmsby", "seed-pmfby"]
        retrieved = ["seed-pmsby", "other", "seed-pmfby"]
        self.assertEqual(precision_at_k(relevant, retrieved, 1), 1.0)
        self.assertAlmostEqual(precision_at_k(relevant, retrieved, 3), 2 / 3)
        self.assertEqual(recall_at_k(relevant, retrieved, 3), 1.0)
        self.assertIsNone(precision_at_k([], retrieved, 3))

    def test_percentile(self):
        self.assertEqual(percentile([1, 2, 3, 4, 5], 50), 3)
        self.assertIsNone(percentile([], 95))

    def test_binary_prf(self):
        stats = binary_prf([(True, True), (True, False), (False, False), (False, True)])
        self.assertEqual(stats["support"], 4)
        self.assertAlmostEqual(stats["precision"], 0.5)
        self.assertAlmostEqual(stats["recall"], 0.5)

    def test_keyphrase_partial(self):
        result = keyphrase_correctness("The premium is Rs 20 per year", ["Rs 20", "auto-debit"])
        self.assertEqual(result["label"], "partial")
        self.assertEqual(result["method"], "deterministic_keyphrase")

    def test_unsupported_hallucination(self):
        detected = unsupported_detection("Yes, PMSBY pays for illness death.", ["illness death"], True)
        self.assertTrue(detected["hallucinated"])
        refused = unsupported_detection("Insufficient evidence in the official note.", ["illness death"], False)
        self.assertTrue(refused["unsupported_detected"])
        self.assertFalse(refused["hallucinated"])

    def test_negated_claim_not_counted_as_leak(self):
        answer = "No, PMSBY does not cover crop yield loss for farmers."
        detected = unsupported_detection(answer, ["crop", "yield loss"], True)
        self.assertFalse(detected["hallucinated"])
        self.assertEqual(detected["leaked_claims"], [])

    def test_score_case_retrieval_na_without_sources(self):
        case = {
            "id": "gsb1-0001",
            "category": "factual",
            "language": "en",
            "difficulty": "easy",
            "scheme": "pmsby",
            "ground_truth": {"required_keyphrases": ["Rs 20"]},
            "evidence": [{"document_id": "seed-pmsby", "document_path": "backend/data/seed_schemes/pmsby_overview.txt"}],
        }
        run = {"ok": True, "http_status": 200, "latency_ms": 12.0, "response": {"answer": "Rs 20 per year"}}
        scored = score_case(case, run)
        self.assertIsNone(scored["precision_at_1"])
        self.assertEqual(scored["factual"]["label"], "correct")
