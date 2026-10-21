"""Phase 3A — eligibility pipeline hardening tests."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.eligibility_api import eligibility_status_for_api
from app.services.eligibility_criteria import extract_eligibility_criteria
from app.services.eligibility_evaluation import EvaluationStatus, evaluate_eligibility
from app.services.eligibility_explanation import explain_eligibility_evaluation, _contradicts_status
from app.services.eligibility_questioning import extract_scenario_facts_from_text
from app.services.scenario_eligibility import (
    is_scenario_eligibility_query,
    should_attempt_scenario_evaluation,
    try_evaluate_scenario_eligibility,
)


def _doc(text: str, *, scheme: str = "Test") -> dict:
    return {"content": text, "scheme_name": scheme, "source": "https://example.gov.in/seed"}


class TestScenarioFactExtraction(unittest.TestCase):
    def test_husband_head_woman_not_head(self):
        q = "My husband is the head of our family and I am a woman in Karnataka."
        facts = extract_scenario_facts_from_text(q)
        self.assertEqual(facts.get("gender"), "female")
        self.assertFalse(facts.get("head_of_family"))

    def test_not_head_of_family(self):
        q = "A Karnataka woman with an Aadhaar-linked bank account is not the head of the family."
        facts = extract_scenario_facts_from_text(q)
        self.assertEqual(facts.get("gender"), "female")
        self.assertFalse(facts.get("head_of_family"))

    def test_age_from_year_old(self):
        facts = extract_scenario_facts_from_text("A 16-year-old with a savings account asks to enroll in PMSBY.")
        self.assertEqual(facts.get("age"), 16)

    def test_no_savings_account(self):
        facts = extract_scenario_facts_from_text(
            "A 40-year-old Indian citizen has no savings bank account."
        )
        self.assertFalse(facts.get("has_savings_account"))

    def test_does_not_infer_unstated_income(self):
        facts = extract_scenario_facts_from_text("A woman in Karnataka asks about Gruha Lakshmi.")
        self.assertNotIn("income", facts)


class TestScenarioDetection(unittest.TestCase):
    def test_does_the_note_pattern(self):
        q = "A woman citizen of Karnataka boards a participating notified state bus. Does the note treat her as an intended beneficiary?"
        self.assertTrue(should_attempt_scenario_evaluation(q))

    def test_personal_query_excluded(self):
        self.assertFalse(should_attempt_scenario_evaluation("Am I eligible for Shakti?"))


class TestDeterministicEvaluation(unittest.TestCase):
    def test_male_gruha_lakshmi_ineligible(self):
        text = (
            "Eligible woman head of the family receives Rs 2,000 per month. "
            "Woman must be a resident of Karnataka."
        )
        criteria = extract_eligibility_criteria(
            [_doc(text, scheme="Gruha Lakshmi")],
            scheme_identity={"scheme_name": "Gruha Lakshmi", "scheme_id": "gruha-lakshmi"},
            query="Gruha Lakshmi man head of family",
        )
        q = "A man who is a Karnataka resident and head of family asks for Gruha Lakshmi. Is he eligible?"
        result = try_evaluate_scenario_eligibility(
            query=q, criteria=criteria, scheme_name="Gruha Lakshmi", scheme_id="gruha-lakshmi"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.status, EvaluationStatus.NOT_ELIGIBLE.value)

    def test_female_unknown_head_uncertain(self):
        text = "Eligible woman head of the family. Woman must be a resident of Karnataka."
        criteria = extract_eligibility_criteria(
            [_doc(text, scheme="Gruha Lakshmi")],
            scheme_identity={"scheme_name": "Gruha Lakshmi", "scheme_id": "gruha-lakshmi"},
            query="Gruha Lakshmi woman resident",
        )
        q = "A woman who is a Karnataka resident asks about Gruha Lakshmi eligibility. Is she eligible?"
        result = try_evaluate_scenario_eligibility(
            query=q, criteria=criteria, scheme_name="Gruha Lakshmi", scheme_id="gruha-lakshmi"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.status, EvaluationStatus.CANNOT_DETERMINE.value)

    def test_pmsby_age_outside_band(self):
        from pathlib import Path

        text = Path(__file__).resolve().parents[1] / "data" / "seed_schemes" / "pmsby_overview.txt"
        content = text.read_text(encoding="utf-8")
        criteria = extract_eligibility_criteria(
            [_doc(content, scheme="PMSBY")],
            scheme_identity={"scheme_name": "PMSBY", "scheme_id": "pmsby"},
            query="PMSBY age",
        )
        self.assertTrue(any(c.criterion_type == "age" for c in criteria.criteria))
        result = try_evaluate_scenario_eligibility(
            query="A 16-year-old with a savings account asks to enroll in PMSBY. Is this age inside the band?",
            criteria=criteria,
            scheme_name="PMSBY",
            scheme_id="pmsby",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.status, EvaluationStatus.NOT_ELIGIBLE.value)


class TestStatusLockAndApi(unittest.TestCase):
    def test_api_mapping(self):
        self.assertEqual(eligibility_status_for_api("NOT_ELIGIBLE"), "ineligible")
        self.assertEqual(eligibility_status_for_api("CANNOT_DETERMINE"), "uncertain")

    def test_explanation_cannot_contradict_ineligible(self):
        self.assertTrue(
            _contradicts_status("You are eligible for this scheme.", EvaluationStatus.NOT_ELIGIBLE.value)
        )


class TestCriteriaExtraction(unittest.TestCase):
    def test_pmsby_age_and_savings(self):
        from pathlib import Path

        content = Path(__file__).resolve().parents[1] / "data" / "seed_schemes" / "pmsby_overview.txt"
        content = content.read_text(encoding="utf-8")
        criteria = extract_eligibility_criteria(
            [_doc(content, scheme="PMSBY")],
            scheme_identity={"scheme_name": "PMSBY", "scheme_id": "pmsby"},
            query="PMSBY eligibility",
        )
        types = {c.criterion_type for c in criteria.criteria}
        self.assertIn("age", types)
        self.assertIn("beneficiary_status", types)


if __name__ == "__main__":
    unittest.main()
