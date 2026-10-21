import unittest

from evaluation.metrics.v2.evaluate import aggregate_scores_v2, classification_changes, score_case_v2


class TestV2Aggregation(unittest.TestCase):
    def _case(self, **overrides):
        base = {
            "id": "gsb1-test",
            "category": "factual",
            "language": "en",
            "difficulty": "easy",
            "scheme": "pmsby",
            "ground_truth": {"required_keyphrases": ["Rs 20"], "eligibility_status": None},
            "evidence": [{"document_id": "seed-pmsby", "document_path": "backend/data/seed_schemes/pmsby_overview.txt"}],
        }
        base.update(overrides)
        return base

    def test_score_case_v2_preserves_legacy(self):
        case = self._case()
        run = {
            "ok": True,
            "http_status": 200,
            "latency_ms": 10.0,
            "response": {
                "answer": "The premium is Rs 20 per year.",
                "sources": [{"scheme_id": "pmsby", "source": "demo_seed://pmsby"}],
                "validated": True,
            },
        }
        scored = score_case_v2(case, run)
        self.assertIn("legacy", scored)
        self.assertIn("factual_v2", scored)
        self.assertIn("retrieval_v2", scored)
        self.assertEqual(scored["factual_v2"]["label"], "correct")

    def test_aggregate_no_division_by_zero(self):
        metrics = aggregate_scores_v2([])
        self.assertEqual(metrics["legacy_v1"]["n_cases"], 0)
        self.assertIn("re_evaluated_v2", metrics)

    def test_classification_changes_detects_factual_shift(self):
        case = self._case(category="multilingual", language="hi", ground_truth={"required_keyphrases": ["2,000"], "facts": ["Rs 2,000"]})
        run = {
            "ok": True,
            "http_status": 200,
            "latency_ms": 1.0,
            "response": {"answer": "मासिक २,००० रुपये", "sources": [], "validated": True},
        }
        scored = score_case_v2(case, run)
        changes = classification_changes([scored])
        self.assertTrue(any(c["id"] == "gsb1-test" for c in changes))

    def test_unsupported_metrics_unchanged_path(self):
        case = self._case(
            category="unsupported",
            scheme="unspecified",
            ground_truth={"must_not_assert": ["wage"], "required_keyphrases": []},
        )
        run = {
            "ok": True,
            "http_status": 200,
            "latency_ms": 1.0,
            "response": {"answer": "Insufficient evidence.", "sources": [], "validated": False},
        }
        scored = score_case_v2(case, run)
        metrics = aggregate_scores_v2([scored])
        self.assertEqual(metrics["re_evaluated_v2"]["unsupported_detection_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
