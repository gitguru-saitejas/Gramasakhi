"""Phase 3A.1 — targeted eligibility pipeline hardening tests."""

from __future__ import annotations

import unittest
from pathlib import Path

from app.services.eligibility_api import eligibility_status_for_api
from app.services.eligibility_criteria import extract_eligibility_criteria
from app.services.eligibility_evaluation import EvaluationStatus, evaluate_eligibility
from app.services.eligibility_questioning import extract_scenario_facts_from_text
from app.services.scenario_eligibility import try_evaluate_scenario_eligibility


def _doc(text: str, *, scheme: str = "Test", scheme_id: str = "test") -> dict:
    return {
        "content": text,
        "scheme_name": scheme,
        "scheme_id": scheme_id,
        "source": "https://example.gov.in/seed",
    }


class TestSchemeIdentity(unittest.TestCase):
    def test_criteria_identity_used_for_evaluation(self):
        text = "Eligible woman head of the family. Woman must be a resident of Karnataka."
        criteria = extract_eligibility_criteria(
            [_doc(text, scheme="Gruha Lakshmi", scheme_id="gruha-lakshmi")],
            scheme_identity={"scheme_name": "Gruha Lakshmi", "scheme_id": "gruha-lakshmi"},
            query="Gruha Lakshmi woman",
        )
        q = "A man who is a Karnataka resident asks for Gruha Lakshmi. Is he eligible?"
        result = try_evaluate_scenario_eligibility(
            query=q,
            criteria=criteria,
            scheme_name="Wrong Alias",
            scheme_id="wrong-id",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.status, EvaluationStatus.NOT_ELIGIBLE.value)

    def test_cross_scheme_evidence_rejected(self):
        shakti = _doc(
            "Women citizens of Karnataka are intended beneficiaries.",
            scheme="Shakti",
            scheme_id="shakti",
        )
        criteria = extract_eligibility_criteria(
            [shakti],
            scheme_identity={"scheme_name": "PMSBY", "scheme_id": "pmsby", "normalized_key": "pmsby"},
            query="PMSBY eligibility",
        )
        self.assertTrue(criteria.rejected or not criteria.criteria)


class TestPmsbyCriteria(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pmsby_text = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "seed_schemes"
            / "pmsby_overview.txt"
        ).read_text(encoding="utf-8")

    def _criteria(self):
        return extract_eligibility_criteria(
            [_doc(self.pmsby_text, scheme="PMSBY", scheme_id="pmsby")],
            scheme_identity={"scheme_name": "PMSBY", "scheme_id": "pmsby"},
            query="PMSBY eligibility",
        )

    def test_age_band_parsed_as_min_and_max(self):
        criteria = self._criteria()
        age_ops = sorted(c.operator for c in criteria.criteria if c.criterion_type == "age")
        self.assertIn(">=", age_ops)
        self.assertIn("<=", age_ops)

    def test_age_below_minimum_ineligible(self):
        result = try_evaluate_scenario_eligibility(
            query="A 16-year-old with a savings account asks to enroll in PMSBY.",
            criteria=self._criteria(),
        )
        self.assertEqual(result.status, EvaluationStatus.NOT_ELIGIBLE.value)

    def test_age_inside_range_eligible(self):
        result = try_evaluate_scenario_eligibility(
            query="A 35-year-old with a savings account and auto-debit consent asks about PMSBY eligibility.",
            criteria=self._criteria(),
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.status, EvaluationStatus.ELIGIBLE.value)

    def test_age_above_maximum_ineligible(self):
        result = try_evaluate_scenario_eligibility(
            query="A 75-year-old with a savings account asks to enroll in PMSBY.",
            criteria=self._criteria(),
        )
        self.assertEqual(result.status, EvaluationStatus.NOT_ELIGIBLE.value)

    def test_missing_age_uncertain(self):
        result = try_evaluate_scenario_eligibility(
            query="A citizen with a savings account asks about PMSBY eligibility.",
            criteria=self._criteria(),
        )
        self.assertEqual(result.status, EvaluationStatus.CANNOT_DETERMINE.value)

    def test_no_savings_account_ineligible(self):
        result = try_evaluate_scenario_eligibility(
            query="A 40-year-old Indian citizen has no savings bank account and asks about PMSBY.",
            criteria=self._criteria(),
        )
        self.assertEqual(result.status, EvaluationStatus.NOT_ELIGIBLE.value)


class TestPmfbyCriteria(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pmfby_text = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "demo_seeds"
            / "pmfby_scheme.txt"
        ).read_text(encoding="utf-8")

    def _criteria(self):
        return extract_eligibility_criteria(
            [_doc(self.pmfby_text, scheme="PMFBY", scheme_id="pmfby")],
            scheme_identity={"scheme_name": "PMFBY", "scheme_id": "pmfby"},
            query="PMFBY eligibility",
        )

    def test_notified_crop_criterion_extracted(self):
        criteria = self._criteria()
        self.assertTrue(
            any(c.value == "notified_crop_area" for c in criteria.criteria)
        )

    def test_crop_not_notified_ineligible_without_notified_criterion(self):
        """Live evidence may omit notified_crop_area criterion — explicit fact still fails closed."""
        empty = extract_eligibility_criteria(
            [_doc("Farmers can enroll in PMFBY.", scheme="PMFBY", scheme_id="pmfby")],
            scheme_identity={"scheme_name": "PMFBY", "scheme_id": "pmfby"},
            query="PMFBY",
        )
        q = "A farmer grows a crop that is not notified for this season. Does PMFBY coverage apply?"
        result = try_evaluate_scenario_eligibility(query=q, criteria=empty)
        self.assertIsNotNone(result)
        self.assertEqual(result.status, EvaluationStatus.NOT_ELIGIBLE.value)

    def test_crop_not_notified_ineligible(self):
        q = "A farmer grows a crop that is not notified for this season. Does PMFBY coverage apply?"
        result = try_evaluate_scenario_eligibility(query=q, criteria=self._criteria())
        self.assertEqual(result.status, EvaluationStatus.NOT_ELIGIBLE.value)

    def test_not_growing_crop_ineligible(self):
        q = "A person who is not growing any crop asks to enroll in PMFBY."
        result = try_evaluate_scenario_eligibility(query=q, criteria=self._criteria())
        self.assertEqual(result.status, EvaluationStatus.NOT_ELIGIBLE.value)


class TestFactExtraction(unittest.TestCase):
    def test_maharashtra_residency_not_karnataka_scheme_mention(self):
        q = (
            "A woman who lives in Maharashtra asks for Shakti free bus travel in Karnataka. "
            "Is she in the intended beneficiary group?"
        )
        facts = extract_scenario_facts_from_text(q)
        self.assertEqual(facts.get("state"), "Maharashtra")

    def test_tamil_nadu_not_confused_with_requirement_mention(self):
        q = "A woman living in Tamil Nadu asks for Gruha Lakshmi. Does the note require Karnataka residence?"
        facts = extract_scenario_facts_from_text(q)
        self.assertEqual(facts.get("state"), "Tamil Nadu")

    def test_multiple_locations(self):
        q = "I live in Maharashtra but my ration card is from Karnataka."
        facts = extract_scenario_facts_from_text(q)
        self.assertEqual(facts.get("state"), "Maharashtra")
        self.assertTrue(facts.get("has_ration_card"))
        self.assertTrue(facts.get("karnataka_ration_card"))

    def test_i_am_16_years_old(self):
        facts = extract_scenario_facts_from_text("I am 16 years old and ask about PMSBY.")
        self.assertEqual(facts.get("age"), 16)

    def test_explicit_negation_head_of_family(self):
        facts = extract_scenario_facts_from_text(
            "A Karnataka woman with an Aadhaar-linked bank account is not the head of the family."
        )
        self.assertFalse(facts.get("head_of_family"))

    def test_dont_have_ration_card(self):
        facts = extract_scenario_facts_from_text("I don't have a ration card.")
        self.assertFalse(facts.get("has_ration_card"))

    def test_meta_farmer_not_extracted(self):
        q = "A person who is not growing any crop asks to enroll in PMFBY. Does the note describe this person as an eligible farmer?"
        facts = extract_scenario_facts_from_text(q)
        self.assertFalse(facts.get("growing_crop"))
        self.assertNotIn("occupation", facts)


class TestEvaluationRules(unittest.TestCase):
    def test_unknown_not_treated_as_false(self):
        text = "Eligible woman head of the family. Woman must be a resident of Karnataka."
        criteria = extract_eligibility_criteria(
            [_doc(text, scheme="Gruha Lakshmi", scheme_id="gruha-lakshmi")],
            scheme_identity={"scheme_name": "Gruha Lakshmi", "scheme_id": "gruha-lakshmi"},
            query="Gruha Lakshmi",
        )
        result = evaluate_eligibility(
            criteria=criteria,
            citizen_answers={"gender": "female", "state": "Karnataka"},
            scheme_name=criteria.scheme_name,
            scheme_id=criteria.scheme_id,
        )
        self.assertEqual(result.status, EvaluationStatus.CANNOT_DETERMINE.value)


class TestApiStatusLock(unittest.TestCase):
    def test_api_lowercase_mapping_preserves_internal_enum(self):
        self.assertEqual(eligibility_status_for_api("ELIGIBLE"), "eligible")
        self.assertEqual(eligibility_status_for_api("NOT_ELIGIBLE"), "ineligible")
        self.assertEqual(eligibility_status_for_api("CANNOT_DETERMINE"), "uncertain")

    def test_deterministic_status_not_downgraded_to_null(self):
        """Regression: scenario eval status must survive through API mapping."""
        internal = EvaluationStatus.NOT_ELIGIBLE.value
        api = eligibility_status_for_api(internal)
        self.assertEqual(api, "ineligible")
        self.assertNotEqual(api, None)


if __name__ == "__main__":
    unittest.main()
