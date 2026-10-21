import unittest

from evaluation.metrics.v2.multilingual import match_keyphrase_multilingual


class TestMultilingualMatching(unittest.TestCase):
    def test_english_exact(self):
        result = match_keyphrase_multilingual("The premium is Rs 20", ["Rs 20"], language="en")
        self.assertEqual(result["label"], "correct")
        self.assertEqual(result["match_details"][0]["match_type"], "exact_match")

    def test_english_numeric_comma(self):
        result = match_keyphrase_multilingual("premium of 2000 rupees", ["2,000"], language="en")
        self.assertEqual(result["label"], "correct")
        self.assertEqual(result["match_details"][0]["match_type"], "normalized_match")

    def test_hindi_devanagari_numeric(self):
        answer = "पात्र महिला को प्रति माह २,००० रुपये मिलते हैं"
        result = match_keyphrase_multilingual(answer, ["2,000"], language="hi", facts=["Rs 2,000 per month"])
        self.assertEqual(result["label"], "correct")
        self.assertIn(
            result["match_details"][0]["match_type"],
            ("exact_match", "normalized_match", "multilingual_variant_match"),
        )

    def test_kannada_numeric(self):
        answer = "ತಿಂಗಳಿಗೆ ೨,೦೦೦ ನೆರವು"
        result = match_keyphrase_multilingual(answer, ["2,000"], language="kn")
        self.assertEqual(result["label"], "correct")

    def test_incorrect_answer(self):
        result = match_keyphrase_multilingual("no amount mentioned", ["2,000"], language="en")
        self.assertEqual(result["label"], "incorrect")

    def test_hindi_non_numeric_requires_review(self):
        result = match_keyphrase_multilingual("योजना कर्नाटक के लिए है", ["Karnataka"], language="hi")
        self.assertEqual(result["match_details"][0]["match_type"], "semantic_review_required")

    def test_partial_match(self):
        result = match_keyphrase_multilingual("Rs 20 premium", ["Rs 20", "auto-debit"], language="en")
        self.assertEqual(result["label"], "partial")
        self.assertAlmostEqual(result["score"], 0.5)


if __name__ == "__main__":
    unittest.main()
