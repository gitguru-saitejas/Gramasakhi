"""Phase 3B — RAG & evidence quality hardening tests."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.services.claim_alignment import check_answer_grounding
from app.services.evidence_expansion import (
    boost_eligibility_ranked_docs,
    chunk_has_eligibility_signal,
    chunk_section_tags,
    expand_adjacent_chunks,
    is_eligibility_focused_query,
)
from app.services.myscheme_service import filter_evidence_by_scheme, select_question_aware_evidence
from app.services.output_grounding import apply_output_grounding_guard


def _doc(
    text: str,
    *,
    scheme: str = "Test Scheme",
    scheme_id: str | None = None,
    chunk_id: str = "c1",
    document_id: str | None = None,
    chunk_index: int | None = None,
    score: float = 0.8,
    metadata: dict | None = None,
) -> dict:
    meta = dict(metadata or {})
    if scheme_id:
        meta.setdefault("scheme_id", scheme_id)
    if document_id:
        meta.setdefault("document_id", document_id)
    if chunk_index is not None:
        meta.setdefault("chunk_index", chunk_index)
    return {
        "chunk_id": chunk_id,
        "content": text,
        "scheme_name": scheme,
        "scheme_id": scheme_id,
        "document_id": document_id,
        "chunk_index": chunk_index,
        "similarity_score": score,
        "hybrid_score": score,
        "metadata": meta,
        "source": "https://example.gov.in/scheme",
    }


PMSBY_DOC = _doc(
    "PMSBY accident insurance. Age 18 to 70. Savings bank account required.",
    scheme="PMSBY",
    scheme_id="pmsby",
    chunk_id="pmsby-1",
)
PMFBY_DOC = _doc(
    "PMFBY crop insurance for notified crops in notified areas.",
    scheme="PMFBY",
    scheme_id="pmfby",
    chunk_id="pmfby-1",
)
GRUHA_DOC = _doc(
    "Gruha Lakshmi: eligible woman head of the family in Karnataka receives Rs 2000.",
    scheme="Gruha Lakshmi",
    scheme_id="gruha-lakshmi",
    chunk_id="gruha-1",
)
SHAKTI_DOC = _doc(
    "Shakti free travel for women on participating KSRTC buses.",
    scheme="Shakti",
    scheme_id="shakti",
    chunk_id="shakti-1",
)
ANNA_DOC = _doc(
    "Anna Bhagya subsidized food grains for eligible ration card holders.",
    scheme="Anna Bhagya",
    scheme_id="anna-bhagya",
    chunk_id="anna-1",
)


class TestEligibilitySignals(unittest.TestCase):
    def test_eligibility_query_detection(self):
        self.assertTrue(is_eligibility_focused_query("Who is eligible for PMSBY?"))
        self.assertTrue(is_eligibility_focused_query("A farmer asks about notified crop rules for PMFBY."))
        self.assertFalse(is_eligibility_focused_query("What is Shakti?"))

    def test_section_tags_from_content(self):
        tags = chunk_section_tags("Section: Eligibility\nAge 18 to 70 years. Notified crops only.")
        self.assertIn("eligibility", tags)
        self.assertIn("notified_crop", tags)

    def test_eligibility_boost_reorders(self):
        generic = _doc("Overview of PMSBY scheme purpose.", scheme="PMSBY", chunk_id="g", score=0.80)
        elig = _doc(
            "Eligibility: age 18-70, savings account required.",
            scheme="PMSBY",
            chunk_id="e",
            score=0.72,
        )
        boosted = boost_eligibility_ranked_docs("PMSBY eligibility age", [generic, elig])
        self.assertEqual(boosted[0]["chunk_id"], "e")
        self.assertTrue(boosted[0].get("eligibility_boost"))

    def test_split_rule_retrievable_via_neighbor(self):
        part_a = _doc(
            "PMFBY coverage applies to farmers.",
            scheme="PMFBY",
            scheme_id="pmfby",
            chunk_id="a",
            document_id="doc-1",
            chunk_index=0,
            score=0.9,
        )
        part_b_content = "Only notified crops grown in notified areas are covered."
        db = MagicMock()
        neighbor = MagicMock()
        neighbor.id = "b"
        neighbor.content = part_b_content
        neighbor.metadata_dict = {"scheme_id": "pmfby", "document_id": "doc-1", "chunk_index": 1}
        neighbor.document = MagicMock(title="PMFBY", scheme_name="PMFBY", source="https://gov.in/pmfby")
        db.query.return_value.filter.return_value.first.return_value = neighbor

        expanded = expand_adjacent_chunks(
            db,
            [part_a],
            query="PMFBY notified crop eligibility",
            max_additions=2,
        )
        self.assertEqual(len(expanded), 2)
        self.assertTrue(any("notified crops" in (d.get("content") or "") for d in expanded))


class TestSchemeFiltering(unittest.TestCase):
    def test_pmsby_vs_pmfby_isolation(self):
        kept = filter_evidence_by_scheme("Tell me about PMSBY eligibility", [PMSBY_DOC, PMFBY_DOC])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["scheme_id"], "pmsby")

    def test_pmfby_query_rejects_pmsby(self):
        kept = filter_evidence_by_scheme("PMFBY notified crop rules", [PMSBY_DOC, PMFBY_DOC])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["scheme_id"], "pmfby")

    def test_shakti_vs_gruha_lakshmi(self):
        kept = filter_evidence_by_scheme("Gruha Lakshmi head of family eligibility", [SHAKTI_DOC, GRUHA_DOC])
        self.assertEqual(len(kept), 1)
        self.assertIn("Gruha", kept[0]["scheme_name"])

    def test_anna_bhagya_vs_gruha_lakshmi(self):
        kept = filter_evidence_by_scheme("Anna Bhagya ration card eligibility", [ANNA_DOC, GRUHA_DOC])
        self.assertEqual(len(kept), 1)
        self.assertIn("Anna", kept[0]["scheme_name"])


class TestQuestionAwareEvidence(unittest.TestCase):
    def test_eligibility_chunks_preferred(self):
        overview = _doc("PMSBY is an accident insurance scheme.", scheme="PMSBY", chunk_id="o", score=0.99)
        elig = _doc(
            "Eligibility: Indian citizen aged 18-70 with savings bank account.",
            scheme="PMSBY",
            chunk_id="e",
            score=0.75,
            metadata={"section_tags": ["eligibility"]},
        )
        selected = select_question_aware_evidence("PMSBY eligibility age account", [overview, elig])
        self.assertEqual(selected[0]["chunk_id"], "e")

    def test_notified_crop_tag_preferred_for_eligibility(self):
        crop = _doc(
            "Coverage limited to notified crops in notified areas.",
            scheme="PMFBY",
            chunk_id="c",
            metadata={"section_tags": ["notified_crop"]},
        )
        other = _doc("PMFBY premium subsidy details.", scheme="PMFBY", chunk_id="o")
        selected = select_question_aware_evidence("PMFBY notified crop eligibility", [other, crop])
        self.assertEqual(selected[0]["chunk_id"], "c")


class TestGroundingAndDrift(unittest.TestCase):
    def test_mgnrega_drift_blocked(self):
        query = "What is the current MGNREGA daily wage in Karnataka?"
        docs = [_doc("MGNREGA provides rural employment guarantee.", scheme="MGNREGA")]
        answer = (
            "The current wage is not explicitly stated in the available evidence. "
            "However, MGNREGA provides 100 days of employment guarantee and workers receive wages per state notification."
        )
        result = check_answer_grounding(query, answer, docs)
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "answer_drift_after_insufficiency")

    def test_pmsby_negated_crop_answer_allowed(self):
        query = "Does PMSBY cover crop yield loss for farmers?"
        docs = [_doc("PMSBY accident insurance. Accidental death Rs 2 lakh.", scheme="PMSBY")]
        answer = "No, PMSBY does not cover crop yield loss. It covers accidental death and disability."
        result = check_answer_grounding(query, answer, docs)
        self.assertTrue(result.ok)

    def test_guard_blocks_drift(self):
        query = "What is the current MGNREGA daily wage in Karnataka?"
        docs = [_doc("MGNREGA employment programme.", scheme="MGNREGA")]
        answer = (
            "The wage is not explicitly stated. MGNREGA guarantees 100 days of paid employment per household."
        )
        grounded = apply_output_grounding_guard(query, answer, docs)
        self.assertFalse(grounded.validated)

    def test_supported_numeric_allowed(self):
        query = "What is the PMSBY accidental death benefit?"
        docs = [
            _doc(
                "Accidental death: Rs 2 lakh sum insured.",
                scheme="PMSBY",
                scheme_id="pmsby",
            )
        ]
        answer = "The accidental death benefit is Rs 2 lakh under PMSBY."
        result = check_answer_grounding(query, answer, docs)
        self.assertTrue(result.ok)

    def test_unsupported_numeric_blocked(self):
        query = "What is the current MGNREGA daily wage in Karnataka?"
        docs = [_doc("MGNREGA wages as notified.", scheme="MGNREGA", scheme_id="mgnrega")]
        answer = "The daily wage is Rs 331 per day."
        result = check_answer_grounding(query, answer, docs)
        self.assertFalse(result.ok)


class TestGenerationEvidenceGate(unittest.TestCase):
    """gsb1-0066 — generation evidence must support numeric claims, not only full retrieval set."""

    def test_pm_kisan_blocks_when_llm_subset_lacks_aligned_amounts(self):
        from app.services import rag as rag_service

        q = "How much money does PM-Kisan pay each installment?"
        weak = [
            _doc(
                "PM Kisan Samman Nidhi Scheme. Rs 6000 per year in three installments of Rs 2000 each.",
                scheme="PM-KISAN Samman Nidhi",
                scheme_id=None,
                chunk_id="w1",
            ),
            _doc(
                "r land holdings. Rs.6000 per annum payable in three equal installment",
                scheme="PM-KISAN",
                scheme_id="pm-kisan",
                chunk_id="w2",
            ),
        ]
        passing = [
            _doc(
                "Under PM-KISAN an amount of Rs 6000 per year is released in three installments.",
                scheme="PM-KISAN",
                scheme_id="pm-kisan",
                chunk_id="pass",
            ),
        ]
        retrieved = weak + passing

        def _no_expand(_db, docs, **_kwargs):
            return docs

        with patch(
            "app.services.multilingual_retrieval_service.multi_query_hybrid_retrieve",
            return_value=retrieved,
        ):
            with patch(
                "app.services.evidence_expansion.expand_adjacent_chunks",
                side_effect=_no_expand,
            ):
                with patch(
                    "app.services.evidence_expansion.boost_eligibility_ranked_docs",
                    side_effect=lambda _q, docs: docs,
                ):
                    with patch(
                        "app.services.myscheme_service.select_question_aware_evidence",
                        return_value=list(weak),
                    ):
                        with patch(
                            "app.services.rag._call_llm_after_validation",
                        ) as mock_llm:
                            mock_llm.return_value = {
                                "success": True,
                                "answer": "Rs 6000 and Rs 2000 per installment.",
                            }
                            out = rag_service.answer_with_evidence_gate(
                                MagicMock(),
                                q,
                                language="English",
                                enable_live_fallback=False,
                            )
        self.assertFalse(out.get("validated"))
        self.assertIn(
            out.get("reason"),
            ("unsupported_numeric_fact", "unsupported_claim", "answer_unsupported_amount"),
        )
        mock_llm.assert_not_called()


class TestEligibilityEvidenceMarkers(unittest.TestCase):
    def test_pmsby_age_chunk_detected(self):
        d = _doc("Eligible persons aged 18 to 70 years with savings bank account.", scheme="PMSBY")
        self.assertTrue(chunk_has_eligibility_signal(d))

    def test_gruha_head_of_family_detected(self):
        d = _doc("Woman head of the family resident of Karnataka.", scheme="Gruha Lakshmi")
        self.assertTrue(chunk_has_eligibility_signal(d))

    def test_pmfby_notified_crop_detected(self):
        d = _doc("Insurance for notified crops in notified areas only.", scheme="PMFBY")
        self.assertTrue(chunk_has_eligibility_signal(d))


if __name__ == "__main__":
    unittest.main()
