"""Phase 2 — claim alignment, output grounding, scenario eligibility, API status."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.claim_alignment import (
    analyze_claim,
    check_answer_grounding,
    check_claim_support,
)
from app.services.eligibility_api import eligibility_status_for_api, normalize_eligibility_status
from app.services.eligibility_criteria import extract_eligibility_criteria
from app.services.eligibility_evaluation import EvaluationStatus, evaluate_eligibility
from app.services.evidence_validator import EvidenceValidator
from app.services.output_grounding import apply_output_grounding_guard
from app.services.scenario_eligibility import (
    is_scenario_eligibility_query,
    try_evaluate_scenario_eligibility,
)


def _doc(text: str, *, scheme: str = "Test Scheme") -> dict:
    return {
        "content": text,
        "scheme_name": scheme,
        "similarity_score": 0.9,
        "source": "https://example.gov.in/scheme",
    }


class TestEligibilityApiMapping(unittest.TestCase):
    def test_internal_to_api(self):
        self.assertEqual(eligibility_status_for_api("ELIGIBLE"), "eligible")
        self.assertEqual(eligibility_status_for_api("NOT_ELIGIBLE"), "ineligible")
        self.assertEqual(eligibility_status_for_api("CANNOT_DETERMINE"), "uncertain")

    def test_api_passthrough(self):
        self.assertEqual(eligibility_status_for_api("eligible"), "eligible")
        self.assertEqual(normalize_eligibility_status("uncertain"), "CANNOT_DETERMINE")


class TestClaimAlignment(unittest.TestCase):
    def test_pmsby_crop_domain_mismatch_fails_pre_llm(self):
        query = "Does PMSBY cover crop yield loss for farmers?"
        docs = [
            _doc(
                "PMSBY provides accident insurance. Accidental death Rs 2 lakh. Premium Rs 20.",
                scheme="PMSBY",
            )
        ]
        result = check_claim_support(query, docs)
        self.assertFalse(result.ok)
        self.assertIn(result.reason, ("domain_mismatch", "unsupported_numeric_fact"))

    def test_mgnrega_wage_without_amount_fails(self):
        query = "What is the current MGNREGA daily wage in Karnataka?"
        docs = [
            _doc(
                "MGNREGA provides rural employment guarantee. Workers receive wages as notified by state.",
                scheme="MGNREGA",
            )
        ]
        result = check_claim_support(query, docs)
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "unsupported_numeric_fact")

    def test_shakti_universal_scope_without_evidence_fails(self):
        query = "Is Shakti free travel available on all private buses in Karnataka?"
        docs = [
            _doc(
                "Shakti scheme provides free travel for women on participating KSRTC and state transport buses.",
                scheme="Shakti",
            )
        ]
        result = check_claim_support(query, docs)
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "unsupported_scope_claim")

    def test_pmsby_crop_hallucination_blocked_post_llm(self):
        query = "Does PMSBY cover crop yield loss for farmers?"
        docs = [
            _doc(
                "PMSBY accident insurance. Accidental death Rs 2 lakh.",
                scheme="PMSBY",
            )
        ]
        answer = "Yes, PMSBY covers crop yield loss for farmers."
        result = check_answer_grounding(query, answer, docs)
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "answer_domain_mismatch")

    def test_pmsby_negated_crop_answer_allowed(self):
        query = "Does PMSBY cover crop yield loss for farmers?"
        docs = [_doc("PMSBY accident insurance. Accidental death Rs 2 lakh.", scheme="PMSBY")]
        answer = "No, PMSBY does not cover crop yield loss for farmers."
        result = check_answer_grounding(query, answer, docs)
        self.assertTrue(result.ok)

    def test_mgnrega_drift_after_insufficiency_blocked(self):
        query = "What is the current MGNREGA daily wage in Karnataka?"
        docs = [_doc("MGNREGA provides employment guarantee.", scheme="MGNREGA")]
        answer = (
            "The current wage is not explicitly stated in the evidence. "
            "MGNREGA provides 100 days of employment guarantee to rural households."
        )
        result = check_answer_grounding(query, answer, docs)
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "answer_drift_after_insufficiency")


class TestOutputGroundingGuard(unittest.TestCase):
    def test_guard_sets_validated_false(self):
        query = "What is the current MGNREGA daily wage in Karnataka?"
        docs = [_doc("MGNREGA employment guarantee programme.", scheme="MGNREGA")]
        grounded = apply_output_grounding_guard(
            query,
            "The daily wage is Rs 331 per day in Karnataka.",
            docs,
        )
        self.assertFalse(grounded.validated)
        self.assertIn("reliable information", grounded.answer.lower())


class TestEvidenceValidatorClaimGate(unittest.TestCase):
    def test_claim_gate_blocks_mgnrega_wage(self):
        embed_fn = lambda text: [1.0, 0.0] if text else [0.0, 1.0]  # noqa: E731
        validator = EvidenceValidator(
            embed_fn=embed_fn,
            relevance_threshold=0.1,
            coverage_threshold=0.2,
            min_query_terms=2,
        )
        docs = [
            {
                "content": "MGNREGA provides employment. Wages are paid as per state notification.",
                "scheme_name": "MGNREGA",
                "similarity_score": 0.95,
                "source": "https://nrega.nic.in/",
            }
        ]
        with patch("app.services.myscheme_service.filter_evidence_by_scheme", side_effect=lambda q, d: d):
            result = validator.validate(
                "What is the current MGNREGA daily wage in Karnataka?",
                docs,
            )
        self.assertFalse(result.ok)
        self.assertIn(result.reason, ("unsupported_numeric_fact", "unsupported_claim"))


class TestScenarioEligibility(unittest.TestCase):
    def test_scenario_query_detection(self):
        q = (
            "A man who is a Karnataka resident and head of family asks for Gruha Lakshmi. "
            "Is he eligible under the listed rules?"
        )
        self.assertTrue(is_scenario_eligibility_query(q))

    def test_gruha_lakshmi_man_ineligible(self):
        gruha_text = (
            "Eligible woman head of the family receives Rs 2,000 per month. "
            "Woman must be a resident of Karnataka."
        )
        sources = [_doc(gruha_text, scheme="Gruha Lakshmi")]
        criteria = extract_eligibility_criteria(
            sources,
            scheme_identity={"scheme_name": "Gruha Lakshmi", "scheme_id": "gruha-lakshmi"},
            query="Gruha Lakshmi eligibility for man head of family",
        )
        query = (
            "A man who is a Karnataka resident and head of family asks for Gruha Lakshmi. "
            "Is he eligible under the listed rules?"
        )
        result = try_evaluate_scenario_eligibility(
            query=query,
            criteria=criteria,
            scheme_name="Gruha Lakshmi",
            scheme_id="gruha-lakshmi",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.status, EvaluationStatus.NOT_ELIGIBLE.value)

    def test_missing_gender_uncertain(self):
        criteria = evaluate_eligibility  # type hint anchor
        from app.services.eligibility_criteria import EligibilityCriteriaResult, EligibilityCriterion, CriterionType

        crit = EligibilityCriteriaResult(
            scheme_name="Gruha Lakshmi",
            scheme_id="gruha-lakshmi",
            criteria=[
                EligibilityCriterion(
                    criterion_type=CriterionType.GENDER.value,
                    statement="Eligible woman head of the family",
                    operator="=",
                    value="female",
                    confidence="explicit",
                    explicitly_stated=True,
                )
            ],
        )
        result = try_evaluate_scenario_eligibility(
            query="Who is eligible for Gruha Lakshmi?",
            criteria=crit,
        )
        self.assertIsNone(result)


class TestRegressionHallucinationQueries(unittest.TestCase):
    def test_private_bus_scope_in_validator(self):
        analysis = analyze_claim("Is Shakti free travel available on all private buses in Karnataka?")
        self.assertTrue(analysis.is_scope_question)
        self.assertEqual(analysis.scheme_id, "shakti")

    def test_pmsby_crop_analysis(self):
        analysis = analyze_claim("Does PMSBY cover crop yield loss for farmers?")
        self.assertTrue(analysis.is_domain_topic_query)


if __name__ == "__main__":
    unittest.main()
