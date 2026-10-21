import unittest

from evaluation.metrics.v2.eligibility import (
    eligibility_confusion_matrix,
    eligibility_prf_from_matrix,
    extract_eligibility_polarity,
    score_eligibility_v2,
)


class TestEligibilityPolarity(unittest.TestCase):
    def test_explicit_eligible(self):
        pol = extract_eligibility_polarity("You are eligible to apply for this scheme.", "en")
        self.assertEqual(pol["polarity"], "ELIGIBLE")

    def test_explicit_ineligible(self):
        pol = extract_eligibility_polarity("You are not eligible because you do not meet the criteria.", "en")
        self.assertEqual(pol["polarity"], "INELIGIBLE")

    def test_can_avail_without_literal_eligible(self):
        pol = extract_eligibility_polarity(
            "Women aged 18 to 60 who meet the household criteria can avail this benefit.",
            "en",
        )
        self.assertEqual(pol["polarity"], "ELIGIBLE")

    def test_conditional_uncertain(self):
        pol = extract_eligibility_polarity("You may be eligible if you meet the income criteria.", "en")
        self.assertEqual(pol["polarity"], "UNCERTAIN")

    def test_negation_overrides_eligible_word(self):
        pol = extract_eligibility_polarity(
            "The scheme does not treat a woman citizen as an intended beneficiary.",
            "en",
        )
        self.assertEqual(pol["polarity"], "INELIGIBLE")

    def test_insufficient_evidence_uncertain(self):
        pol = extract_eligibility_polarity("I couldn't identify the requested scheme from trusted sources.", "en")
        self.assertEqual(pol["polarity"], "UNCERTAIN")

    def test_hindi_ineligible(self):
        pol = extract_eligibility_polarity("आप इस योजना के लिए पात्र नहीं हैं", "hi")
        self.assertEqual(pol["polarity"], "INELIGIBLE")

    def test_kannada_eligible(self):
        pol = extract_eligibility_polarity("ಈ ಯೋಜನೆಗೆ ನೀವು ಅರ್ಹರಾಗಿದ್ದೀರಿ", "kn")
        self.assertEqual(pol["polarity"], "ELIGIBLE")

    def test_score_eligibility_correct(self):
        result = score_eligibility_v2("eligible", "You can apply for the scheme.", language="en")
        self.assertEqual(result["label"], "correct")

    def test_score_eligibility_incorrect(self):
        result = score_eligibility_v2("ineligible", "You are eligible for the benefit.", language="en")
        self.assertEqual(result["label"], "incorrect")

    def test_score_eligibility_uncertain(self):
        result = score_eligibility_v2("eligible", "Eligibility depends on official notification.", language="en")
        self.assertEqual(result["label"], "uncertain")
        self.assertIsNone(result["score"])

    def test_confusion_matrix_and_prf(self):
        rows = [
            ("eligible", "ELIGIBLE"),
            ("eligible", "INELIGIBLE"),
            ("eligible", "UNCERTAIN"),
            ("ineligible", "ELIGIBLE"),
            ("ineligible", "INELIGIBLE"),
        ]
        matrix = eligibility_confusion_matrix(rows)
        stats = eligibility_prf_from_matrix(matrix)
        self.assertEqual(stats["support"], 5)
        self.assertEqual(stats["uncertain_count"], 1)
        self.assertAlmostEqual(stats["accuracy"], 0.4)


if __name__ == "__main__":
    unittest.main()
