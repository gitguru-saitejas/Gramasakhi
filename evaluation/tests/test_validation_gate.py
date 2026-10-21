import unittest

from evaluation.eligibility import derive_eligibility
from evaluation.validate import validate_benchmark, validate_case


ALLOWED_PATHS = {"backend/data/seed_schemes/pmsby_overview.txt"}
ALLOWED_URLS = {"https://www.myscheme.gov.in/schemes/pmsby"}


def _evidence():
    return [
        {
            "document_id": "seed-pmsby",
            "document_path": "backend/data/seed_schemes/pmsby_overview.txt",
            "source_url": None,
            "excerpt": "Indian citizens in the eligible age band as notified (commonly 18 to 70 years). Annual premium is Rs 20 per member per year.",
        }
    ]


class TestEvidenceAndUnsupported(unittest.TestCase):
    def test_keyphrase_must_appear_in_evidence(self):
        case = {
            "id": "gsb1-0001",
            "scheme": "pmsby",
            "category": "factual",
            "difficulty": "easy",
            "language": "en",
            "question": "What is the PMSBY premium?",
            "expected_behavior": "answer_from_evidence",
            "ground_truth": {"facts": ["x"], "required_keyphrases": ["not-in-document-xyz"]},
            "evidence": _evidence(),
        }
        errors = validate_case(case, allowed_urls=ALLOWED_URLS, allowed_paths=ALLOWED_PATHS)
        self.assertTrue(any("keyphrases" in e for e in errors))

    def test_fabricated_path_rejected(self):
        case = {
            "id": "gsb1-0002",
            "scheme": "pmsby",
            "category": "factual",
            "difficulty": "easy",
            "language": "en",
            "question": "What is the PMSBY premium?",
            "expected_behavior": "answer_from_evidence",
            "ground_truth": {"facts": ["Rs 20"], "required_keyphrases": ["Rs 20"]},
            "evidence": [
                {
                    "document_id": "fake",
                    "document_path": "backend/data/not_real.txt",
                    "excerpt": "Annual premium is Rs 20 per member per year",
                }
            ],
        }
        errors = validate_case(case, allowed_urls=ALLOWED_URLS, allowed_paths=ALLOWED_PATHS)
        self.assertTrue(any("document_path" in e for e in errors))

    def test_unsupported_must_not_be_in_evidence(self):
        case = {
            "id": "gsb1-0003",
            "scheme": "pmsby",
            "category": "unsupported",
            "difficulty": "adversarial",
            "language": "en",
            "question": "Does PMSBY pay for illness death?",
            "expected_behavior": "unsupported",
            "ground_truth": {"must_not_assert": ["commonly 18 to 70 years"]},
            "evidence": _evidence(),
        }
        errors = validate_case(case, allowed_urls=ALLOWED_URLS, allowed_paths=ALLOWED_PATHS)
        self.assertTrue(any("appears in evidence" in e for e in errors))

    def test_true_unsupported_passes(self):
        case = {
            "id": "gsb1-0004",
            "scheme": "pmsby",
            "category": "unsupported",
            "difficulty": "adversarial",
            "language": "en",
            "question": "Does PMSBY pay for death due to common illness?",
            "expected_behavior": "unsupported",
            "ground_truth": {"must_not_assert": ["illness death", "natural death"]},
            "evidence": _evidence(),
        }
        self.assertEqual(validate_case(case, allowed_urls=ALLOWED_URLS, allowed_paths=ALLOWED_PATHS), [])


class TestEligibilityValidation(unittest.TestCase):
    def test_derivation_matches_expected(self):
        self.assertEqual(
            derive_eligibility("pmsby", {"age_in_common_band": True, "has_savings_bank": True}),
            "eligible",
        )
        self.assertEqual(derive_eligibility("pmsby", {"age_in_common_band": False, "has_savings_bank": True}), "ineligible")
        self.assertEqual(derive_eligibility("shakti", {"is_man": True, "state_karnataka": True}), "ineligible")
        self.assertEqual(derive_eligibility("shakti", {"is_woman": True, "state_karnataka": True}), "eligible")

    def test_mismatch_rejected(self):
        case = {
            "id": "gsb1-0005",
            "scheme": "pmsby",
            "category": "eligibility",
            "difficulty": "easy",
            "language": "en",
            "question": "Is a 16-year-old eligible for PMSBY?",
            "expected_behavior": "ineligible",
            "ground_truth": {
                "facts": ["18 to 70"],
                "required_keyphrases": ["18 to 70"],
                "eligibility_status": "eligible",
                "citizen_profile": {"age_in_common_band": False, "has_savings_bank": True},
            },
            "evidence": _evidence(),
        }
        errors = validate_case(case, allowed_urls=ALLOWED_URLS, allowed_paths=ALLOWED_PATHS)
        self.assertTrue(any("derived eligibility" in e for e in errors))


class TestMultilingualAndDuplicates(unittest.TestCase):
    def test_hindi_requires_devanagari_and_validation(self):
        case = {
            "id": "gsb1-0006",
            "scheme": "pmsby",
            "category": "multilingual",
            "difficulty": "easy",
            "language": "hi",
            "question": "What is the PMSBY premium?",
            "expected_behavior": "answer_from_evidence",
            "ground_truth": {"facts": ["Rs 20"], "required_keyphrases": ["Rs 20"]},
            "evidence": _evidence(),
        }
        errors = validate_case(case, allowed_urls=ALLOWED_URLS, allowed_paths=ALLOWED_PATHS)
        self.assertTrue(any("Devanagari" in e or "translation-validated" in e for e in errors))

    def test_validated_hindi_passes(self):
        case = {
            "id": "gsb1-0007",
            "scheme": "pmsby",
            "category": "multilingual",
            "difficulty": "easy",
            "language": "hi",
            "question": "पीएमएसबीवाई की वार्षिक प्रीमियम राशि कितनी है?",
            "expected_behavior": "answer_from_evidence",
            "ground_truth": {"facts": ["Rs 20"], "required_keyphrases": ["Rs 20"]},
            "evidence": _evidence(),
            "translation": {"validated": True, "source_question": "What is the annual premium listed for PMSBY?"},
        }
        self.assertEqual(validate_case(case, allowed_urls=ALLOWED_URLS, allowed_paths=ALLOWED_PATHS), [])

    def test_duplicate_dropped(self):
        case_a = {
            "id": "gsb1-0008",
            "scheme": "pmsby",
            "category": "factual",
            "difficulty": "easy",
            "language": "en",
            "question": "What is the PMSBY premium?",
            "expected_behavior": "answer_from_evidence",
            "ground_truth": {"facts": ["Rs 20"], "required_keyphrases": ["Rs 20"]},
            "evidence": _evidence(),
        }
        case_b = dict(case_a)
        case_b["id"] = "gsb1-0009"
        gate = validate_benchmark([case_a, case_b], allowed_urls=ALLOWED_URLS, allowed_paths=ALLOWED_PATHS)
        self.assertEqual(len(gate["accepted"]), 1)
        self.assertEqual(len(gate["rejected"]), 1)
