"""NLU clarification routing — complete queries must reach RAG, incomplete may clarify."""

from __future__ import annotations

import unittest

from app.services.citizen_assistance import CitizenIntent, build_assistance_context
from app.services.human_language import HumanLanguageIntent, interpret_human_language
from app.services.language_service import detect_previous_answer_transform

_GRUHA_CTX = {
    "conversation_active_scheme": "Gruha Lakshmi",
    "rewrite_active_scheme": "Gruha Lakshmi",
    "conversation_history": [{"role": "user", "content": "Tell me about Gruha Lakshmi."}],
}


class TestCompleteQueriesReachRetrieval(unittest.TestCase):
    def test_factual_pmfby_ministry(self):
        q = "Which ministry administers PMFBY according to the scheme note?"
        r = interpret_human_language(q, use_llm=False)
        self.assertFalse(r.needs_clarification)
        ctx = build_assistance_context(original_query=q)
        self.assertNotEqual(ctx.intent, CitizenIntent.CLARIFICATION)

    def test_eligibility_pm_kisan(self):
        q = "Who is eligible for PM-KISAN?"
        r = interpret_human_language(q, use_llm=False)
        self.assertEqual(r.intent, HumanLanguageIntent.ELIGIBILITY)
        ctx = build_assistance_context(original_query=q)
        self.assertNotEqual(ctx.intent, CitizenIntent.CLARIFICATION)

    def test_documents_gruha_lakshmi(self):
        q = "What documents are needed for Gruha Lakshmi?"
        r = interpret_human_language(q, use_llm=False)
        self.assertFalse(r.needs_clarification)
        self.assertEqual(r.intent, HumanLanguageIntent.DOCUMENTS_REQUIRED)

    def test_scenario_eligibility_pmsby(self):
        q = "Can a 45 year old woman in Karnataka apply for PMSBY?"
        r = interpret_human_language(q, use_llm=False)
        self.assertFalse(r.needs_clarification)
        ctx = build_assistance_context(original_query=q)
        self.assertNotEqual(ctx.intent, CitizenIntent.CLARIFICATION)

    def test_benefits_shakti(self):
        q = "What are the benefits of Shakti?"
        r = interpret_human_language(q, use_llm=False)
        self.assertFalse(r.needs_clarification)
        ctx = build_assistance_context(original_query=q)
        self.assertNotEqual(ctx.intent, CitizenIntent.CLARIFICATION)

    def test_apply_pmfby(self):
        q = "How do I apply for PMFBY?"
        r = interpret_human_language(q, use_llm=False)
        self.assertIn(
            r.intent,
            (HumanLanguageIntent.APPLICATION_PROCESS, HumanLanguageIntent.APPLICATION_CHANNEL),
        )
        self.assertFalse(r.needs_clarification)


class TestIncompleteQueriesClarify(unittest.TestCase):
    def test_scheme_token_only(self):
        r = interpret_human_language("PM-KISAN", use_llm=False)
        self.assertTrue(r.needs_clarification)

    def test_documents_without_scheme(self):
        ctx = build_assistance_context(original_query="documents")
        self.assertEqual(ctx.intent, CitizenIntent.CLARIFICATION)

    def test_am_i_eligible_without_context_still_routes(self):
        """Standalone personal eligibility is a complete question shape, not a menu."""
        r = interpret_human_language("Am I eligible?", use_llm=False)
        self.assertFalse(r.needs_clarification)


class TestPreservedPaths(unittest.TestCase):
    def test_short_followup_documents_with_context(self):
        r = interpret_human_language("Documents?", use_llm=False, **_GRUHA_CTX)
        self.assertEqual(r.intent, HumanLanguageIntent.DOCUMENTS_REQUIRED)
        self.assertFalse(r.needs_clarification)

    def test_language_change_not_clarification(self):
        r = interpret_human_language("Kannada please", use_llm=False, **_GRUHA_CTX)
        self.assertIn("LANGUAGE_CHANGE", r.conversational_tags)
        self.assertFalse(r.needs_clarification)

    def test_explain_that_simply_rephrase(self):
        tr = detect_previous_answer_transform("Explain that simply")
        self.assertEqual(tr.mode, "rephrase")

    def test_multilingual_factual_hi(self):
        q = "PMFBY ke liye kaun patra hai?"
        r = interpret_human_language(q, use_llm=False)
        self.assertFalse(r.needs_clarification)


class TestBenchmarkRegressionRouting(unittest.TestCase):
    """Ensure benchmark-shaped queries are not forced into CLARIFICATION."""

    def test_gsb1_0002_style(self):
        q = "Which ministry administers PMFBY according to the scheme note?"
        ctx = build_assistance_context(original_query=q)
        self.assertNotEqual(ctx.intent, CitizenIntent.CLARIFICATION)

    def test_gsb1_0066_installment_not_clarification(self):
        q = "How much money does PM-Kisan pay each installment?"
        ctx = build_assistance_context(original_query=q)
        self.assertNotEqual(ctx.intent, CitizenIntent.CLARIFICATION)
        self.assertIn(
            ctx.intent,
            (CitizenIntent.BENEFITS, CitizenIntent.OVERVIEW, CitizenIntent.UNKNOWN),
        )

    def test_gsb1_0074_mgnrega_wage(self):
        q = "What is the current MGNREGA daily wage in Karnataka?"
        ctx = build_assistance_context(original_query=q)
        self.assertNotEqual(ctx.intent, CitizenIntent.CLARIFICATION)

    def test_gsb1_0076_shakti_scope(self):
        q = "Does the Shakti scheme cover travel on all private buses in Karnataka?"
        ctx = build_assistance_context(original_query=q)
        self.assertNotEqual(ctx.intent, CitizenIntent.CLARIFICATION)

    def test_gsb1_0078_pmsby_crop(self):
        q = "Does PMSBY cover crop yield loss for farmers?"
        ctx = build_assistance_context(original_query=q)
        self.assertNotEqual(ctx.intent, CitizenIntent.CLARIFICATION)

    def test_gsb1_0059_pmfby_crop(self):
        q = "A farmer grows a crop that is not notified for this season. Does PMFBY coverage apply?"
        ctx = build_assistance_context(original_query=q)
        self.assertNotEqual(ctx.intent, CitizenIntent.CLARIFICATION)


class TestEligibilityFactsNotRetrievalQueries(unittest.TestCase):
    def test_income_answer_not_complete_query_routing(self):
        from app.services.human_language.conversational import query_has_retrieval_structure

        q = "My income is 1.5 lakh"
        self.assertFalse(query_has_retrieval_structure(q))
        r = interpret_human_language(q, use_llm=False)
        self.assertNotEqual(r.intent, HumanLanguageIntent.GENERAL_INFORMATION)

    def test_multi_fact_answer_not_unrelated(self):
        from app.services.eligibility_questioning import capture_session_answer, EligibilitySession

        session = EligibilitySession(
            conversation_id="test-nlu",
            active_scheme="PM-KISAN",
            required_information=["age", "state", "income"],
            missing_information=["age", "state", "income"],
            known_information={},
            current_question_type="age",
            response_language="EN",
            session_active=True,
        )
        captured, unrelated, _ = capture_session_answer(
            session, "I am 32 and I live in Karnataka."
        )
        self.assertTrue(captured)
        self.assertFalse(unrelated)


if __name__ == "__main__":
    unittest.main()
