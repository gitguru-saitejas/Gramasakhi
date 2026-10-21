import unittest

from evaluation.schema import find_duplicate_questions, normalize_question, validate_case_schema


def _valid_case(**overrides):
    case = {
        "id": "gsb1-0001",
        "scheme": "pmsby",
        "category": "factual",
        "difficulty": "easy",
        "language": "en",
        "question": "What annual premium does PMSBY list?",
        "expected_behavior": "answer_from_evidence",
        "ground_truth": {"facts": ["Rs 20"], "required_keyphrases": ["Rs 20"]},
        "evidence": [
            {
                "document_id": "seed-pmsby",
                "document_path": "backend/data/seed_schemes/pmsby_overview.txt",
                "excerpt": "Annual premium is Rs 20 per member per year",
            }
        ],
    }
    case.update(overrides)
    return case


class TestSchema(unittest.TestCase):
    def test_valid_case(self):
        self.assertEqual(validate_case_schema(_valid_case()), [])

    def test_missing_id(self):
        case = _valid_case()
        del case["id"]
        self.assertTrue(validate_case_schema(case))

    def test_invalid_language(self):
        self.assertTrue(validate_case_schema(_valid_case(language="fr")))

    def test_empty_ground_truth(self):
        self.assertTrue(validate_case_schema(_valid_case(ground_truth={})))

    def test_normalize_and_duplicates(self):
        self.assertEqual(normalize_question("  What is PMSBY?  "), "what is pmsby")
        cases = [
            _valid_case(id="gsb1-0001", question="What is PMSBY?"),
            _valid_case(id="gsb1-0002", question="what is pmsby?"),
        ]
        dupes = find_duplicate_questions(cases)
        self.assertEqual(len(dupes), 1)
        self.assertEqual(dupes[0][0], "gsb1-0001")
        self.assertEqual(dupes[0][1], "gsb1-0002")
