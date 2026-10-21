"""Phase 3C — numeric grounding, drift, eligibility API, Gruha Lakshmi."""

from __future__ import annotations

import unittest

from app.services.claim_alignment import (
    check_answer_grounding,
    check_claim_support,
    query_requests_specific_amount,
)
from app.services.eligibility_api import eligibility_status_for_api
from app.services.eligibility_criteria import extract_eligibility_criteria
from app.services.eligibility_evaluation import EvaluationStatus, evaluate_eligibility
from app.services.eligibility_questioning import extract_scenario_facts_from_text
from app.services.output_grounding import apply_output_grounding_guard
from app.services.scenario_eligibility import try_evaluate_scenario_eligibility


def _doc(text: str, *, scheme: str = "Test", scheme_id: str | None = None) -> dict:
    return {
        "content": text,
        "scheme_name": scheme,
        "scheme_id": scheme_id,
        "similarity_score": 0.9,
        "source": "https://example.gov.in/scheme",
    }


class TestNumericGrounding(unittest.TestCase):
    def test_query_detects_installment_amount(self):
        q = "How much money does PM-Kisan pay each installment?"
        self.assertTrue(query_requests_specific_amount(q))

    def test_supported_amount_allowed(self):
        q = "What is the PMSBY accidental death benefit?"
        docs = [_doc("Accidental death: Rs 2 lakh sum insured.", scheme="PMSBY")]
        answer = "The benefit is Rs 2 lakh under PMSBY."
        self.assertTrue(check_answer_grounding(q, answer, docs).ok)

    def test_unsupported_amount_blocked(self):
        q = "How much money does PM-Kisan pay each installment?"
        docs = [_doc("PM-Kisan provides income support to farmers.", scheme="PM-KISAN")]
        answer = "Each installment is Rs 2000 and total Rs 6000 per year."
        result = check_answer_grounding(q, answer, docs)
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "answer_unsupported_amount")

    def test_unsupported_with_unrelated_numeric_evidence(self):
        q = "How much money does PM-Kisan pay each installment?"
        docs = [_doc("Other scheme pays Rs 5000 one-time grant.", scheme="Other")]
        answer = "PM-Kisan pays Rs 6000 per year."
        self.assertFalse(check_answer_grounding(q, answer, docs).ok)

    def test_admin_expense_amount_does_not_support_installment(self):
        q = "How much money does PM-Kisan pay each installment?"
        docs = [
            _doc(
                "State level function: Rs.50,000/- District level function: Rs.25,000/- reimbursement.",
                scheme="PM-KISAN",
            )
        ]
        answer = "Each installment is Rs 2000 totaling Rs 6000 per year."
        self.assertFalse(check_answer_grounding(q, answer, docs).ok)

    def test_negated_numeric_allowed(self):
        q = "Does the Shakti scheme pay women a monthly cash grant of Rs 2,000?"
        docs = [_doc("Shakti provides free bus travel on KSRTC.", scheme="Shakti")]
        answer = "The evidence does not establish a Rs 2,000 monthly cash grant under Shakti."
        self.assertTrue(check_answer_grounding(q, answer, docs).ok)

    def test_multiple_supported_numbers(self):
        q = "What is the PMSBY benefit?"
        docs = [_doc("Death benefit Rs 2 lakh. Premium Rs 20 per year.", scheme="PMSBY")]
        answer = "Death benefit is Rs 2 lakh and premium is Rs 20."
        self.assertTrue(check_answer_grounding(q, answer, docs).ok)

    def test_indian_number_formatting(self):
        q = "How much money does PM-Kisan pay each installment?"
        docs = [
            _doc(
                "Installment amount Rs 2,000 every four months.",
                scheme="PM-KISAN",
                scheme_id="pm-kisan",
            )
        ]
        answer = "The installment is Rs 2,000 every four months."
        self.assertTrue(check_answer_grounding(q, answer, docs).ok)

    def test_pm_kisan_installment_blocked_without_scheme_id_evidence(self):
        """Regression for gsb1-0066 — fragment/unscoped chunks must not ground amounts."""
        q = "How much money does PM-Kisan pay each installment?"
        docs = [
            _doc(
                "PM Kisan Samman Nidhi Scheme. Rs 6000 per year in three installments of Rs 2000 each.",
                scheme="PM-KISAN Samman Nidhi",
            ),
            _doc(
                "r land holdings. Rs.6000 per annum in installments of Rs.2000 each.",
                scheme="Who is eligible PM-KISAN",
                scheme_id="pm-kisan",
            ),
        ]
        answer = (
            "The benefit amount for PM-KISAN is Rs 6000 per year, released in three equal "
            "installments of Rs 2000 each every four months."
        )
        self.assertFalse(check_claim_support(q, docs).ok)
        self.assertFalse(check_answer_grounding(q, answer, docs).ok)
        grounded = apply_output_grounding_guard(q, answer, docs)
        self.assertFalse(grounded.validated)

    def test_words_six_thousand_blocked_without_evidence(self):
        q = "How much money does PM-Kisan pay each installment?"
        docs = [_doc("PM-Kisan farmer support scheme overview.", scheme="PM-KISAN")]
        answer = "The total benefit is six thousand rupees per year."
        self.assertFalse(check_answer_grounding(q, answer, docs).ok)


class TestAnswerDrift(unittest.TestCase):
    def test_mgnrega_procedural_drift_blocked(self):
        q = "What is the current MGNREGA daily wage in Karnataka?"
        docs = [_doc("MGNREGA provides employment guarantee.", scheme="MGNREGA")]
        answer = (
            "The daily wage is not explicitly stated. However, wages are deposited into "
            "bank accounts and paid on a weekly basis."
        )
        grounded = apply_output_grounding_guard(q, answer, docs)
        self.assertFalse(grounded.validated)

    def test_insufficiency_only_safe(self):
        q = "What is the current MGNREGA daily wage in Karnataka?"
        docs = [_doc("MGNREGA rural employment programme.", scheme="MGNREGA")]
        answer = "The available evidence does not provide the specific daily wage amount."
        self.assertTrue(check_answer_grounding(q, answer, docs).ok)


class TestEligibilityApiMapping(unittest.TestCase):
    def test_all_three_statuses(self):
        self.assertEqual(eligibility_status_for_api("ELIGIBLE"), "eligible")
        self.assertEqual(eligibility_status_for_api("NOT_ELIGIBLE"), "ineligible")
        self.assertEqual(eligibility_status_for_api("CANNOT_DETERMINE"), "uncertain")


class TestGruhaLakshmiHeadOfFamily(unittest.TestCase):
    GRUHA = (
        "Who is eligible (summary): - Woman must be a resident of Karnataka - "
        "Woman should be the head of the family - Applicant should have a valid "
        "Aadhaar-linked bank account for Direct Benefit Transfer"
    )

    def _criteria(self):
        return extract_eligibility_criteria(
            [_doc(self.GRUHA, scheme="Gruha Lakshmi", scheme_id="gruha-lakshmi")],
            scheme_identity={"scheme_name": "Gruha Lakshmi", "scheme_id": "gruha-lakshmi"},
            query="Gruha Lakshmi eligibility",
        )

    def test_female_head_positive(self):
        q = (
            "A woman who is a Karnataka resident, head of her family, with an Aadhaar-linked "
            "bank account asks about Gruha Lakshmi. Does this match the listed conditions?"
        )
        facts = extract_scenario_facts_from_text(q)
        self.assertEqual(facts.get("gender"), "female")
        self.assertTrue(facts.get("head_of_family"))
        result = try_evaluate_scenario_eligibility(query=q, criteria=self._criteria())
        self.assertIsNotNone(result)
        self.assertEqual(result.status, EvaluationStatus.ELIGIBLE.value)

    def test_male_head_negative(self):
        q = (
            "A man who is a Karnataka resident and head of family asks for Gruha Lakshmi. "
            "Is he eligible under the listed rules?"
        )
        facts = extract_scenario_facts_from_text(q)
        self.assertEqual(facts.get("gender"), "male")
        self.assertTrue(facts.get("head_of_family"))
        result = try_evaluate_scenario_eligibility(query=q, criteria=self._criteria())
        self.assertIsNotNone(result)
        self.assertEqual(result.status, EvaluationStatus.NOT_ELIGIBLE.value)

    def test_unknown_head_uncertain(self):
        q = "A Karnataka resident asks about Gruha Lakshmi eligibility."
        facts = extract_scenario_facts_from_text(q)
        self.assertNotIn("head_of_family", facts)
        criteria = self._criteria()
        result = evaluate_eligibility(
            criteria=criteria,
            citizen_answers=facts,
            scheme_name="Gruha Lakshmi",
            scheme_id="gruha-lakshmi",
            evidence_validated=True,
        )
        self.assertEqual(result.status, EvaluationStatus.CANNOT_DETERMINE.value)


class TestRegressions(unittest.TestCase):
    def test_pmsby_negated_crop(self):
        q = "Does PMSBY cover crop yield loss for farmers?"
        docs = [_doc("PMSBY accident insurance. Death Rs 2 lakh.", scheme="PMSBY")]
        answer = "No, PMSBY does not cover crop yield loss for farmers."
        self.assertTrue(check_answer_grounding(q, answer, docs).ok)

    def test_pmfby_notified_crop_ineligible(self):
        text = (
            "Coverage applies only for crops and areas notified for that season. "
            "All farmers growing notified crops in notified areas can enroll."
        )
        criteria = extract_eligibility_criteria(
            [_doc(text, scheme="PMFBY", scheme_id="pmfby")],
            scheme_identity={"scheme_name": "PMFBY", "scheme_id": "pmfby"},
            query="PMFBY",
        )
        q = "A farmer grows a crop that is not notified for this season. Does PMFBY coverage apply?"
        result = try_evaluate_scenario_eligibility(query=q, criteria=criteria)
        self.assertEqual(result.status, EvaluationStatus.NOT_ELIGIBLE.value)

    def test_pre_llm_unsupported_installment(self):
        q = "How much money does PM-Kisan pay each installment?"
        docs = [_doc("PM-Kisan overview for farmers.", scheme="PM-KISAN")]
        self.assertFalse(check_claim_support(q, docs).ok)

    def test_mgnrega_wage_allowed_with_scheme_scoped_evidence(self):
        """gsb1-0074 — legitimate wage when scheme-aligned chunk supports it."""
        q = "What is the current MGNREGA daily wage in Karnataka?"
        docs = [
            _doc(
                "The notified daily wage under MGNREGA for Karnataka is Rs 374 per day for unskilled work.",
                scheme="MGNREGA",
                scheme_id="mgnrega",
            )
        ]
        answer = "The notified daily wage is Rs 374 per day."
        self.assertTrue(check_answer_grounding(q, answer, docs).ok)

    def test_shakti_scope_refusal_without_universal_evidence(self):
        """gsb1-0076 — no universal private-bus claim without evidence."""
        q = "Does the Shakti scheme cover travel on all private buses in Karnataka?"
        docs = [_doc("Shakti provides free bus travel on KSRTC for eligible women.", scheme="Shakti", scheme_id="shakti")]
        answer = "No, the available evidence does not establish coverage on all private buses."
        self.assertTrue(check_answer_grounding(q, answer, docs).ok)

    def test_pmsby_crop_negation_still_allowed(self):
        """gsb1-0078 — negated crop claim remains safe."""
        q = "Does PMSBY cover crop yield loss for farmers?"
        docs = [_doc("PMSBY accident insurance. Death benefit Rs 2 lakh.", scheme="PMSBY", scheme_id="pmsby")]
        answer = "No, PMSBY does not cover crop yield loss for farmers."
        self.assertTrue(check_answer_grounding(q, answer, docs).ok)

    def test_pmfby_notified_crop_stays_ineligible(self):
        """gsb1-0059 — non-notified crop remains not eligible."""
        text = (
            "Coverage applies only for crops and areas notified for that season. "
            "All farmers growing notified crops in notified areas can enroll."
        )
        criteria = extract_eligibility_criteria(
            [_doc(text, scheme="PMFBY", scheme_id="pmfby")],
            scheme_identity={"scheme_name": "PMFBY", "scheme_id": "pmfby"},
            query="PMFBY",
        )
        q = "A farmer grows a crop that is not notified for this season. Does PMFBY coverage apply?"
        result = try_evaluate_scenario_eligibility(query=q, criteria=criteria)
        self.assertEqual(result.status, EvaluationStatus.NOT_ELIGIBLE.value)


if __name__ == "__main__":
    unittest.main()
