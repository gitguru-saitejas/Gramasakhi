"""
Evidence Sufficiency Validator — hard gate before LLM generation.

Combines relevance, coverage, and agreement. Fails closed on uncertainty.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Set

from app.core.config import settings

logger = logging.getLogger("gramsakhi.evidence_validator")

SAFE_FALLBACK_ANSWER = (
    "I don't have enough reliable information to answer that."
)

# Minimum extracted body length for evidence to count as substantive (not URL/metadata only).
MIN_SUBSTANTIVE_CONTENT_CHARS = 40


def has_substantive_content(doc: Dict[str, Any]) -> bool:
    """True when a chunk carries enough extracted body text to ground an answer."""
    body = str(doc.get("content") or doc.get("text") or "").strip()
    return len(body) >= MIN_SUBSTANTIVE_CONTENT_CHARS

_SAFE_FALLBACK_BY_LANG = {
    "EN": SAFE_FALLBACK_ANSWER,
    "KN": "ಈ ಪ್ರಶ್ನೆಗೆ ನನ್ನ ಬಳಿ ಸಾಕಷ್ಟು ವಿಶ್ವಾಸಾರ್ಹ ಮಾಹಿತಿ ಇಲ್ಲ.",
    "HI": "इस प्रश्न का उत्तर देने के लिए मेरे पास पर्याप्त विश्वसनीय जानकारी नहीं है।",
}


def safe_fallback_answer(language: Optional[str] = None) -> str:
    """Citizen-facing insufficient-evidence message in the response language."""
    code = (language or "EN").strip().upper()[:2]
    return _SAFE_FALLBACK_BY_LANG.get(code, SAFE_FALLBACK_ANSWER)

# Intent / domain stopwords — not used as coverage requirements
_STOPWORDS: Set[str] = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "of",
    "in",
    "on",
    "at",
    "to",
    "for",
    "from",
    "by",
    "with",
    "about",
    "as",
    "into",
    "through",
    "during",
    "and",
    "or",
    "but",
    "if",
    "then",
    "than",
    "so",
    "such",
    "what",
    "which",
    "who",
    "whom",
    "whose",
    "how",
    "when",
    "where",
    "why",
    "do",
    "does",
    "did",
    "can",
    "could",
    "should",
    "would",
    "will",
    "shall",
    "may",
    "might",
    "must",
    "i",
    "me",
    "my",
    "we",
    "our",
    "you",
    "your",
    "it",
    "its",
    "this",
    "that",
    "these",
    "those",
    "please",
    "tell",
    "give",
    "list",
    "explain",
    "describe",
    "scheme",
    "schemes",
    "program",
    "programme",
    "government",
    "india",
}

# Light intent expansion so coverage catches related phrasing
_INTENT_EXPAND: Dict[str, Set[str]] = {
    "eligibility": {"eligible", "qualify", "qualification", "criteria", "who", "aadhaar"},
    "eligible": {"eligibility", "qualify", "criteria"},
    "benefits": {"benefit", "amount", "installment", "payment", "income", "support"},
    "benefit": {"benefits", "amount", "payment"},
    "penalties": {"penalty", "fine", "punishment", "sanction", "violation"},
    "penalty": {"penalties", "fine", "sanction"},
    "apply": {"application", "register", "registration", "how"},
    "loan": {"credit", "subsidy", "interest"},
    "housing": {"house", "pmay", "rural"},
    # Official circulars often say "return/reverse" instead of "refund"
    "refund": {"return", "reverse", "repay", "reimbursement", "bharatkosh"},
    "mechanism": {"process", "procedure", "method", "portal"},
    "wrongly": {"incorrect", "wrong", "erroneous", "non-beneficiaries", "nonbeneficiaries"},
    "amounts": {"amount", "money", "funds"},
}


@dataclass
class ValidationResult:
    ok: bool
    confidence: str  # "high" | "medium" | "low"
    reason: str
    signals: Dict[str, Any] = field(default_factory=dict)
    # Chunks that survived pruning — the only evidence the LLM may see.
    evidence: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "confidence": self.confidence,
            "reason": self.reason,
            "signals": self.signals,
        }


def extract_keywords(query: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9]+", (query or "").lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


def _doc_text(doc: Dict[str, Any]) -> str:
    meta = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    parts = [
        str(doc.get("content") or doc.get("text") or ""),
        str(doc.get("scheme_name") or ""),
        str(doc.get("document_title") or ""),
        str(doc.get("source") or ""),
        str((meta or {}).get("source") or ""),
        str((meta or {}).get("url") or ""),
    ]
    return " ".join(parts).lower()


def _sigmoid(x: float) -> float:
    # Numerically stable
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _doc_relevance_score(doc: Dict[str, Any]) -> float:
    """Pick best available score and map into ~[0, 1]."""
    if "ce_score" in doc and doc["ce_score"] is not None:
        # CrossEncoder logits → probability-like
        return float(_sigmoid(float(doc["ce_score"])))
    for key in ("similarity_score", "hybrid_score", "faiss_norm", "score"):
        if doc.get(key) is not None:
            try:
                return max(0.0, min(1.0, float(doc[key])))
            except (TypeError, ValueError):
                continue
    return 0.0


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        fx, fy = float(x), float(y)
        dot += fx * fy
        na += fx * fx
        nb += fy * fy
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _mean(vals: Sequence[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _variance(vals: Sequence[float]) -> float:
    if len(vals) < 2:
        return 0.0
    m = _mean(vals)
    return sum((v - m) ** 2 for v in vals) / len(vals)


class EvidenceValidator:
    """
    Hard gate: relevance AND coverage AND agreement must all pass.
    Fails closed on empty docs, short queries, or signal errors.
    """

    def __init__(
        self,
        *,
        relevance_threshold: Optional[float] = None,
        coverage_threshold: Optional[float] = None,
        agreement_threshold: Optional[float] = None,
        agreement_variance_max: Optional[float] = None,
        min_query_terms: Optional[int] = None,
        doc_floor: Optional[float] = None,
        embed_fn: Optional[Callable[[str], List[float]]] = None,
    ):
        self.doc_floor = float(
            doc_floor if doc_floor is not None else settings.EVIDENCE_DOC_FLOOR
        )
        self.relevance_threshold = float(
            relevance_threshold
            if relevance_threshold is not None
            else settings.EVIDENCE_RELEVANCE_THRESHOLD
        )
        self.coverage_threshold = float(
            coverage_threshold
            if coverage_threshold is not None
            else settings.EVIDENCE_COVERAGE_THRESHOLD
        )
        self.agreement_threshold = float(
            agreement_threshold
            if agreement_threshold is not None
            else settings.EVIDENCE_AGREEMENT_THRESHOLD
        )
        self.agreement_variance_max = float(
            agreement_variance_max
            if agreement_variance_max is not None
            else settings.EVIDENCE_AGREEMENT_VARIANCE_MAX
        )
        self.min_query_terms = int(
            min_query_terms
            if min_query_terms is not None
            else settings.EVIDENCE_MIN_QUERY_TERMS
        )
        self.embed_fn = embed_fn

    def prune_weak(self, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Keep only chunks the reranker considers relevant. A single strong chunk is
        valid evidence; padding it with weak ones only dilutes every signal.
        """
        ranked = [d for d in docs if _doc_relevance_score(d) >= self.doc_floor]
        return [d for d in ranked if has_substantive_content(d)]

    def check_relevance(self, docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not docs:
            return {"ok": False, "score": 0.0, "detail": "no_documents"}
        scores = [_doc_relevance_score(d) for d in docs]
        avg = _mean(scores)
        return {
            "ok": avg >= self.relevance_threshold,
            "score": avg,
            "per_doc": scores,
            "threshold": self.relevance_threshold,
        }

    def check_coverage(self, query: str, docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        key_terms = extract_keywords(query)
        if not key_terms:
            return {
                "ok": False,
                "score": 0.0,
                "detail": "no_query_terms",
                "terms": [],
                "matched": [],
            }

        corpus = " ".join(_doc_text(d) for d in docs)
        corpus_tokens = set(re.findall(r"[a-z0-9]+", corpus))

        matched: List[str] = []
        for term in key_terms:
            variants = {term} | _INTENT_EXPAND.get(term, set())
            if any(v in corpus_tokens or v in corpus for v in variants):
                matched.append(term)

        ratio = len(matched) / max(len(key_terms), 1)
        missing = [t for t in key_terms if t not in matched]

        # Intent-bearing terms (eligibility, penalties, benefits, …) must be covered.
        # Entity-only overlap (e.g. "PM Kisan") is not enough if the asked aspect is absent.
        intent_terms = [t for t in key_terms if t in _INTENT_EXPAND]
        missing_intent = [t for t in intent_terms if t not in matched]
        intent_ok = len(missing_intent) == 0

        ok = ratio >= self.coverage_threshold and intent_ok
        detail = "ok"
        if missing_intent:
            detail = "missing_intent_terms"
        elif not ok:
            detail = "low_match_ratio"

        return {
            "ok": ok,
            "score": ratio,
            "terms": key_terms,
            "matched": matched,
            "missing": missing,
            "missing_intent": missing_intent,
            "threshold": self.coverage_threshold,
            "detail": detail,
        }

    def check_claim_support(self, query: str, docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fourth gate — specific factual claims must be supported by evidence."""
        try:
            from app.services.claim_alignment import check_claim_support

            result = check_claim_support(query, docs)
            return {
                "ok": result.ok,
                "reason": result.reason,
                "detail": result.detail,
                "signals": result.signals,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("claim_support_check_failed err=%s", type(exc).__name__)
            return {"ok": False, "reason": "claim_support_error", "detail": type(exc).__name__}

    def check_agreement(self, docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not docs:
            return {"ok": False, "score": 0.0, "detail": "no_documents"}
        if len(docs) == 1:
            # Single source: agreement vacuously holds (coverage/relevance still gate)
            return {"ok": True, "score": 1.0, "detail": "single_document", "pairwise": []}

        # Chunks from the same official URL/document cannot "conflict" with each other
        # (common with multi-page OCR). Compare across distinct sources only.
        by_source: Dict[str, List[Dict[str, Any]]] = {}
        for d in docs:
            key = str(
                d.get("source")
                or d.get("document_id")
                or (d.get("metadata") or {}).get("source")
                or d.get("chunk_id")
                or id(d)
            )
            by_source.setdefault(key, []).append(d)
        if len(by_source) == 1:
            return {
                "ok": True,
                "score": 1.0,
                "detail": "single_source",
                "pairwise": [],
                "sources": list(by_source.keys()),
            }
        docs = [
            max(group, key=lambda x: float(x.get("similarity_score") or 0.0))
            for group in by_source.values()
        ]
        if len(docs) == 1:
            return {"ok": True, "score": 1.0, "detail": "single_source", "pairwise": []}

        embeddings: List[List[float]] = []
        embed = self.embed_fn
        reused = 0

        for d in docs:
            stored = d.get("_embedding") or d.get("embedding")
            if stored and self.embed_fn is None:
                embeddings.append([float(x) for x in stored])
                reused += 1
                continue

            if embed is None:
                try:
                    from app.services.rag import get_embeddings

                    embed = get_embeddings
                except Exception as e:
                    logger.warning("Agreement embed unavailable: %s", e)
                    # Fail closed — cannot verify agreement
                    return {"ok": False, "score": 0.0, "detail": "embed_unavailable"}

            text = (_doc_text(d) or "")[:2000]
            try:
                embeddings.append(embed(text))
            except Exception as e:
                logger.warning("Failed to embed doc for agreement: %s", e)
                return {"ok": False, "score": 0.0, "detail": "embed_failed"}

        if len({len(e) for e in embeddings}) > 1:
            return {"ok": False, "score": 0.0, "detail": "embedding_dim_mismatch"}

        pairwise: List[float] = []
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                pairwise.append(_cosine(embeddings[i], embeddings[j]))

        mean_sim = _mean(pairwise)
        var = _variance(pairwise)
        ok = mean_sim >= self.agreement_threshold and var <= self.agreement_variance_max
        return {
            "ok": ok,
            "score": mean_sim,
            "variance": var,
            "pairwise": pairwise,
            "threshold": self.agreement_threshold,
            "variance_max": self.agreement_variance_max,
            "reused_embeddings": reused,
            "detail": "ok" if ok else "conflict_or_low_agreement",
        }

    def validate(self, query: str, docs: List[Dict[str, Any]]) -> ValidationResult:
        q = (query or "").strip()
        if not q:
            return ValidationResult(
                ok=False,
                confidence="low",
                reason="empty_query",
                signals={},
            )

        key_terms = extract_keywords(q)
        if len(key_terms) < self.min_query_terms:
            return ValidationResult(
                ok=False,
                confidence="low",
                reason="query_too_short",
                signals={"terms": key_terms},
            )

        if not docs:
            return ValidationResult(
                ok=False,
                confidence="low",
                reason="no_evidence",
                signals={},
            )

        evidence = self.prune_weak(docs)
        if not evidence:
            had_ranked = any(_doc_relevance_score(d) >= self.doc_floor for d in docs)
            reason = "no_substantive_evidence" if had_ranked else "no_relevant_evidence"
            return ValidationResult(
                ok=False,
                confidence="low",
                reason=reason,
                signals={
                    "pruning": {
                        "retrieved": len(docs),
                        "kept": 0,
                        "floor": self.doc_floor,
                        "best_score": max(
                            (_doc_relevance_score(d) for d in docs), default=0.0
                        ),
                    }
                },
            )

        # Hard scheme identity gate — similarity must never override wrong scheme.
        try:
            from app.services.myscheme_service import filter_evidence_by_scheme

            before = len(evidence)
            evidence = filter_evidence_by_scheme(q, evidence)
            if before and not evidence:
                return ValidationResult(
                    ok=False,
                    confidence="low",
                    reason="wrong_scheme_evidence",
                    signals={
                        "pruning": {
                            "retrieved": len(docs),
                            "kept": 0,
                            "floor": self.doc_floor,
                            "scheme_rejected": before,
                        }
                    },
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("scheme_filter_failed err=%s", type(exc).__name__)
            return ValidationResult(
                ok=False,
                confidence="low",
                reason="scheme_filter_error",
                signals={"error": type(exc).__name__},
            )

        relevance = self.check_relevance(evidence)
        coverage = self.check_coverage(q, evidence)
        agreement = self.check_agreement(evidence)
        claim_support = self.check_claim_support(q, evidence)

        signals = {
            "relevance": relevance,
            "coverage": coverage,
            "agreement": agreement,
            "claim_support": claim_support,
            "pruning": {
                "retrieved": len(docs),
                "kept": len(evidence),
                "floor": self.doc_floor,
            },
        }

        failures = []
        if not relevance.get("ok"):
            failures.append("insufficient_relevance")
        if not coverage.get("ok"):
            failures.append("insufficient_coverage")
        if not agreement.get("ok"):
            failures.append("insufficient_agreement")
        if not claim_support.get("ok"):
            failures.append("unsupported_claim")

        if failures:
            # Prefer most informative primary reason
            reason = failures[0]
            if "insufficient_coverage" in failures and coverage.get("missing"):
                reason = "insufficient_coverage"
            elif "insufficient_agreement" in failures:
                reason = "conflicting_evidence"
            elif "unsupported_claim" in failures:
                reason = str(claim_support.get("reason") or "unsupported_claim")
            return ValidationResult(
                ok=False,
                confidence="low",
                reason=reason,
                signals=signals,
                evidence=[],
            )

        # All passed — confidence from weakest signal
        scores = [
            float(relevance.get("score") or 0),
            float(coverage.get("score") or 0),
            float(agreement.get("score") or 0),
        ]
        weakest = min(scores)
        confidence = "high" if weakest >= 0.85 else "medium"
        return ValidationResult(
            ok=True,
            confidence=confidence,
            reason="evidence_sufficient",
            signals=signals,
            evidence=evidence,
        )
