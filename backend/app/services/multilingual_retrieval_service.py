"""Multilingual retrieval bridge (adapter).

Generates retrieval representations for KN/HI/EN without replacing
FAISS / BM25 / CrossEncoder / Evidence Validator.

Citizen-visible text is never altered here — only retrieval/validation
queries are expanded.
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.core.config import settings
from app.services.language_service import detect_script_language, normalize_language_code

logger = logging.getLogger("gramsakhi.multilingual_retrieval")

# Deterministic Kn/Hi → English RETRIEVAL aliases only (never mutate display text).
_TERM_ALIASES: Tuple[Tuple[str, str], ...] = (
    # Kannada intents
    ("ಅರ್ಹತೆ", "eligibility"),
    ("ಅರ್ಹರು", "eligible"),
    ("ಅರ್ಹ", "eligible"),
    ("ಪ್ರಯೋಜನಗಳು", "benefits"),
    ("ಪ್ರಯೋಜನ", "benefits"),
    ("ಅರ್ಜಿ", "application"),
    ("ಅರ್ಜಿಸಿ", "apply"),
    ("ದಾಖಲೆಗಳು", "documents"),
    ("ದಾಖಲೆ", "documents"),
    ("ಕೊನೆಯ ದಿನಾಂಕ", "deadline"),
    ("ಮೊತ್ತ", "amount"),
    ("ಹಣ", "amount"),
    ("ರೈತರು", "farmers"),
    ("ರೈತ", "farmer"),
    ("ಮಹಿಳೆ", "women"),
    ("ಮಹಿಳೆಯರು", "women"),
    ("ವಯಸ್ಸು", "age"),
    ("ಭೂಮಿ", "land"),
    ("ದೂರು", "grievance"),
    ("ಸ್ಥಿತಿ", "status"),
    ("ಯೋಜನೆ", "scheme"),
    ("ಸರ್ಕಾರ", "government"),
    ("ಕರ್ನಾಟಕ", "Karnataka"),
    ("ಕೇಂದ್ರ", "central"),
    # Hindi intents
    ("पात्रता", "eligibility"),
    ("पात्र", "eligible"),
    ("लाभ", "benefits"),
    ("आवेदन", "application"),
    ("दस्तावेज़", "documents"),
    ("दस्तावेज", "documents"),
    ("अंतिम तिथि", "deadline"),
    ("राशि", "amount"),
    ("किसान", "farmer"),
    ("महिला", "women"),
    ("आयु", "age"),
    ("भूमि", "land"),
    ("शिकायत", "grievance"),
    ("स्थिति", "status"),
    ("योजना", "scheme"),
    ("सरकार", "government"),
    ("कर्नाटक", "Karnataka"),
)

_SCHEME_ALIASES: Tuple[Tuple[str, str], ...] = (
    ("pm-kisan", "PM-KISAN"),
    ("pm kisan", "PM-KISAN"),
    ("pmkisan", "PM-KISAN"),
    ("ಪಿಎಂ-ಕಿಸಾನ್", "PM-KISAN"),
    ("ಪಿಎಂ ಕಿಸಾನ್", "PM-KISAN"),
    ("ಪಿಎಂಕಿಸಾನ್", "PM-KISAN"),
    ("पीएम-किसान", "PM-KISAN"),
    ("पीएम किसान", "PM-KISAN"),
    ("पीएमकिसान", "PM-KISAN"),
    ('kisan samman nidhi', 'PM-KISAN'),
    ('udyogini scheme', 'Udyogini'),
    ('udyogini yojana', 'Udyogini'),
    ('udyogini yojane', 'Udyogini'),
    ('udyogini', 'Udyogini'),
    ('ಉದ್ಯೋಗಿನಿ ಯೋಜನೆ', 'Udyogini'),
    ('ಉದ್ಯೋಗಿನಿ', 'Udyogini'),
    ('उद्योगिनी योजना', 'Udyogini'),
    ('उद्योगिनी', 'Udyogini'),
    ('gruha lakshmi', 'Gruha Lakshmi'),
    ("gruhalakshmi", "Gruha Lakshmi"),
    ("guruha lakshmi", "Gruha Lakshmi"),
    ("ಗೃಹ ಲಕ್ಷ್ಮೀ", "Gruha Lakshmi"),
    ("ಗೃಹಲಕ್ಷ್ಮಿ", "Gruha Lakshmi"),
    ("ಗೃಹ ಲಕ್ಷ್ಮಿ", "Gruha Lakshmi"),
    ("गृह लक्ष्मी", "Gruha Lakshmi"),
    ("गृहलक्ष्मी", "Gruha Lakshmi"),
    ("gruha jyoti", "Gruha Jyoti"),
    ("gruhajyoti", "Gruha Jyoti"),
    ("guruha jyoti", "Gruha Jyoti"),
    ("guruha jyothi", "Gruha Jyoti"),
    ("gruha jyothi", "Gruha Jyoti"),
    ("ಗೃಹ ಜ್ಯೋತಿ", "Gruha Jyoti"),
    ("ಗೃಹಜ್ಯೋತಿ", "Gruha Jyoti"),
    ("anna bhagya", "Anna Bhagya"),
    ("ಅನ್ನ ಭಾಗ್ಯ", "Anna Bhagya"),
    ("ಅನ್ನಭಾಗ್ಯ", "Anna Bhagya"),
    ("अन्न भाग्य", "Anna Bhagya"),
    ("ayushman", "Ayushman Bharat PM-JAY"),
    ("ಆಯುಷ್ಮಾನ್", "Ayushman Bharat PM-JAY"),
    ("आयुष्मान", "Ayushman Bharat PM-JAY"),
    ("pmay-g", "PMAY-G"),
    ("pmfby", "PMFBY"),
    ("pradhan mantri fasal bima", "PMFBY"),
    ("fasal bima", "PMFBY"),
    ("mgnrega", "MGNREGA"),
    ("shakti scheme", "Shakti"),
    ("shakti yojana", "Shakti"),
    ("shakti", "Shakti"),
    ("ಶಕ್ತಿ ಯೋಜನೆ", "Shakti"),
    ("ಶಕ್ತಿ", "Shakti"),
    ("शक्ति योजना", "Shakti"),
    ("शक्ति", "Shakti"),
)

_INTENT_PATTERNS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("deadline", ("deadline", "last date", "closing date", "ಕೊನೆಯ ದಿನಾಂಕ", "ಅಂತಿಮ ದಿನಾಂಕ", "अंतिम तिथि")),
    (
        "eligibility",
        (
            "eligibility",
            "eligible",
            "who can apply",
            "who is eligible",
            "criteria",
            "qualification",
            "ಅರ್ಹ",
            "ಯಾರು ಅರ್ಹ",
            "पात्र",
            "पात्रता",
        ),
    ),
    ("amount", ("amount", "ಮೊತ್ತ", "राशि")),
    (
        "benefits",
        (
            "benefit",
            "subsidy",
            "assistance",
            "what do i get",
            "ಪ್ರಯೋಜನ",
            "लाभ",
        ),
    ),
    (
        "documents",
        (
            "document",
            "certificates",
            "required papers",
            "ದಾಖಲೆ",
            "दस्तावेज",
        ),
    ),
    (
        "application",
        (
            "how to apply",
            "how do i apply",
            "apply",
            "application",
            "registration",
            "ಅರ್ಜಿ",
            "आवेदन",
        ),
    ),
    ("grievance", ("grievance", "ದೂರು", "शिकायत")),
    ("status", ("status", "ಸ್ಥಿತಿ", "स्थिति")),
    (
        "overview",
        (
            "what is",
            "tell me about",
            "give me details",
            "complete details",
            "full details",
        ),
    ),
)

_CACHE: Dict[str, "RetrievalPlan"] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_MAX = 128


@dataclass
class RetrievalPlan:
    original_query: str
    normalized_query: str
    detected_language: str
    semantic_retrieval_query: str
    keyword_retrieval_queries: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    intent: Optional[str] = None
    multilingual_expansion_used: bool = False
    validation_query: str = ""
    live_search_query: str = ""
    retrieval_query_types: List[str] = field(default_factory=list)

    def all_retrieval_queries(self) -> List[str]:
        out: List[str] = []
        for q in (
            [self.original_query, self.normalized_query, self.semantic_retrieval_query]
            + list(self.keyword_retrieval_queries)
        ):
            qq = (q or "").strip()
            if qq and qq not in out:
                out.append(qq)
        return out

    def diagnostic_dict(self) -> Dict[str, Any]:
        return {
            "original_query": self.original_query[:240],
            "normalized_query": self.normalized_query[:240],
            "detected_language": self.detected_language,
            "semantic_retrieval_query": self.semantic_retrieval_query[:240],
            "keyword_retrieval_queries": [k[:160] for k in self.keyword_retrieval_queries[:6]],
            "entities": self.entities[:12],
            "intent": self.intent,
            "multilingual_expansion_used": self.multilingual_expansion_used,
            "retrieval_query_count": len(self.all_retrieval_queries()),
            "retrieval_query_types": list(self.retrieval_query_types),
            "validation_query": (self.validation_query or "")[:240],
            "live_search_query": (self.live_search_query or "")[:240],
        }


# Measured STT Latin artifacts → canonical spellings (retrieval normalize only).
# Do NOT replace KN/HI cue words (mahiti, heli, …) with English — that erases
# language evidence before the resolver runs on the original transcript.
_STT_SCHEME_FIXES: Tuple[Tuple[str, str], ...] = (
    (r"\bguruha\s+jyothi\b", "Gruha Jyoti"),
    (r"\bguruha\s+jyoti\b", "Gruha Jyoti"),
    (r"\bgruha\s+jyothi\b", "Gruha Jyoti"),
    (r"\bguruha\s+lakshmi\b", "Gruha Lakshmi"),
    (r"\bguruha\b", "Gruha"),
    (r"\barhru\b", "arharu"),
)


def normalize_query_text(text: str) -> str:
    """Conservative whitespace/punctuation normalize — no translation."""
    t = (text or "").replace("\u00a0", " ")
    t = re.sub(r"[\t\r\n]+", " ", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    # Collapse repeated punctuation
    t = re.sub(r"([?!।॥]){2,}", r"\1", t)
    return t


def normalize_stt_artifacts(text: str) -> str:
    """Fix common Whisper Latin misspellings of Karnataka scheme names."""
    t = normalize_query_text(text)
    for pat, repl in _STT_SCHEME_FIXES:
        t = re.sub(pat, repl, t, flags=re.IGNORECASE)
    return t


def normalize_transcript(text: str) -> Tuple[str, str]:
    """Return (original, normalized) for STT output."""
    original = text or ""
    return original, normalize_stt_artifacts(original)


def extract_entities(text: str) -> List[str]:
    found: List[str] = []
    raw = text or ""
    lowered = normalize_stt_artifacts(raw).lower()
    for alias, canonical in sorted(_SCHEME_ALIASES, key=lambda x: -len(x[0])):
        if alias in lowered or alias in raw:
            if canonical not in found:
                found.append(canonical)
    # Latin scheme tokens already in text
    for m in re.findall(r"\b(PM-?KISAN|PMFBY|PMAY-?[GU]|MGNREGA|PM-?JAY)\b", text or "", re.I):
        canon = m.upper().replace("PMKISAN", "PM-KISAN")
        if "KISAN" in canon:
            canon = "PM-KISAN"
        if canon not in found:
            found.append(canon)
    return found


def detect_intent(text: str) -> Optional[str]:
    raw = text or ""
    lower = raw.lower()
    for intent, keys in _INTENT_PATTERNS:
        for k in keys:
            if k.lower() in lower or k in raw:
                return intent
    return None


def _alias_english_terms(text: str) -> List[str]:
    extras: List[str] = []
    raw = text or ""
    lower = raw.lower()
    for src, eng in _TERM_ALIASES:
        if src in raw and eng not in extras:
            extras.append(eng)
        elif src.lower() in lower and eng not in extras and src.isascii():
            extras.append(eng)
    for alias, canonical in _SCHEME_ALIASES:
        if alias in raw or alias in lower:
            if canonical not in extras:
                extras.append(canonical)
    return extras


def build_retrieval_plan(
    query: str,
    *,
    language: Optional[str] = None,
    active_scheme: Optional[str] = None,
    nlu_intent: Optional[str] = None,
) -> RetrievalPlan:
    original = (query or "").strip()
    # Include measured STT scheme spelling fixes in the retrieval normalize path.
    normalized = normalize_stt_artifacts(original)
    # Query language from script/content — NOT from answer response_language.
    # (English retrieval queries with response_language=KN must stay on the EN path.)
    script = detect_script_language(normalized)
    has_non_latin = any(ord(c) > 127 for c in normalized)
    lang = script or ("EN" if not has_non_latin else (normalize_language_code(language) or "EN"))

    cache_key = hashlib.sha256(
        f"{normalized}|{lang}|{active_scheme or ''}|{nlu_intent or ''}".encode("utf-8")
    ).hexdigest()
    with _CACHE_LOCK:
        hit = _CACHE.get(cache_key)
        if hit is not None:
            return hit

    entities = extract_entities(normalized)
    if active_scheme and active_scheme not in entities:
        from app.services.query_rewriter import (
            _looks_like_followup,
            extract_scheme_mentions,
            is_standalone_query,
        )

        if (
            not extract_scheme_mentions(normalized)
            and not is_standalone_query(normalized)
            and _looks_like_followup(normalized)
        ):
            entities = [active_scheme] + entities
    intent = detect_intent(normalized)
    if nlu_intent:
        try:
            from app.services.human_language.intent_models import (
                HumanLanguageIntent,
                retrieval_intent_hint,
            )

            hint = retrieval_intent_hint(HumanLanguageIntent(nlu_intent))
            if hint:
                intent = hint
        except Exception:
            pass
    alias_terms = _alias_english_terms(normalized)

    # Expand when multilingual script, or short contextual follow-ups (NLU + scheme).
    needs_expansion = bool(script in ("KN", "HI")) or has_non_latin
    if nlu_intent and active_scheme and len(normalized.split()) <= 4:
        needs_expansion = True
    if nlu_intent and active_scheme and active_scheme not in entities:
        entities = [active_scheme] + entities

    semantic_parts: List[str] = []
    for e in entities:
        semantic_parts.append(e)
    if intent:
        semantic_parts.append(intent)
        if intent == "eligibility":
            semantic_parts.extend(["eligible", "criteria"])
        elif intent == "benefits":
            semantic_parts.extend(["benefit", "assistance"])
        elif intent == "amount":
            semantic_parts.extend(["amount", "financial assistance", "benefit amount"])
        elif intent == "application":
            semantic_parts.extend(["apply", "application process", "registration"])
        elif intent == "documents":
            semantic_parts.extend(["required documents", "certificates"])
        elif intent == "status":
            semantic_parts.extend(["application status", "track application"])
    for t in alias_terms:
        if t not in semantic_parts:
            semantic_parts.append(t)
    # Keep Latin tokens from original (numbers, scheme codes)
    for tok in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-]{1,}", normalized):
        if tok.lower() not in {p.lower() for p in semantic_parts}:
            semantic_parts.append(tok)

    if needs_expansion and semantic_parts:
        semantic = " ".join(semantic_parts)
        multilingual = True
    else:
        semantic = normalized
        multilingual = False

    keyword_queries: List[str] = []
    if multilingual:
        if entities and intent:
            keyword_queries.append(f"{entities[0]} {intent}")
        if entities:
            keyword_queries.append(" ".join(entities[:2]))
        if alias_terms:
            keyword_queries.append(" ".join(dict.fromkeys(alias_terms)))

    validation = semantic if multilingual else normalized
    live_q = semantic if multilingual else normalized

    types = ["original"]
    if normalized != original:
        types.append("normalized")
    if multilingual:
        types.extend(["semantic_en", "keyword_en"])

    plan = RetrievalPlan(
        original_query=original,
        normalized_query=normalized,
        detected_language=lang if lang in ("EN", "KN", "HI") else (script or "EN"),
        semantic_retrieval_query=semantic,
        keyword_retrieval_queries=keyword_queries,
        entities=entities,
        intent=intent,
        multilingual_expansion_used=multilingual,
        validation_query=validation,
        live_search_query=live_q,
        retrieval_query_types=types,
    )

    with _CACHE_LOCK:
        _CACHE[cache_key] = plan
        while len(_CACHE) > _CACHE_MAX:
            _CACHE.pop(next(iter(_CACHE)))

    logger.info(
        "multilingual_plan lang=%s expansion=%s intent=%s entities=%s semantic=%r",
        plan.detected_language,
        plan.multilingual_expansion_used,
        plan.intent,
        plan.entities[:4],
        plan.semantic_retrieval_query[:160],
    )
    return plan


def multi_query_hybrid_retrieve(
    db: Any,
    plan: RetrievalPlan,
    *,
    top_k: Optional[int] = None,
    use_rerank: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """
    Run existing hybrid_retrieve over multiple query representations and merge.
    CrossEncoder rerank uses semantic (EN) query when expansion was used,
    preserving original as a secondary score blend when practical.
    """
    from app.services.rag import hybrid_retrieve

    top_k = int(top_k if top_k is not None else settings.HYBRID_TOP_K)
    use_rerank = settings.HYBRID_RERANK_ENABLED if use_rerank is None else bool(use_rerank)

    queries = plan.all_retrieval_queries()
    if not plan.multilingual_expansion_used or len(queries) <= 1:
        return hybrid_retrieve(
            db,
            plan.normalized_query or plan.original_query,
            top_k=top_k,
            use_rerank=use_rerank,
        )

    # Cap query fan-out for latency
    queries = queries[:4]
    merged: Dict[str, Dict[str, Any]] = {}
    for rq in queries:
        try:
            hits = hybrid_retrieve(db, rq, top_k=top_k, use_rerank=False)
        except Exception as e:  # noqa: BLE001
            logger.warning("multi_query retrieve failed q=%r err=%s", rq[:80], type(e).__name__)
            continue
        for h in hits:
            cid = str(h.get("chunk_id") or "")
            if not cid:
                continue
            score = float(h.get("similarity_score") or h.get("hybrid_score") or 0.0)
            prev = merged.get(cid)
            if prev is None or score > float(prev.get("similarity_score") or 0.0):
                row = dict(h)
                row["similarity_score"] = score
                row["_retrieval_queries"] = list(
                    dict.fromkeys((prev or {}).get("_retrieval_queries", []) + [rq[:120]])
                )
                merged[cid] = row

    docs = sorted(
        merged.values(),
        key=lambda d: float(d.get("similarity_score") or 0.0),
        reverse=True,
    )
    if not docs:
        # Fallback: original only
        return hybrid_retrieve(
            db,
            plan.original_query,
            top_k=top_k,
            use_rerank=use_rerank,
        )

    if use_rerank and docs:
        try:
            from app.services.cross_encoder import get_reranker

            reranker = get_reranker(settings.CROSS_ENCODER_MODEL)
            ce_query = plan.semantic_retrieval_query or plan.normalized_query
            pool = docs[: max(top_k * 3, top_k)]
            scored = reranker.rerank(ce_query, pool, top_k=max(top_k, min(len(pool), top_k * 3)))
            # Optional blend with original-language CE when scripts differ
            if plan.original_query != ce_query and any(
                ord(c) > 127 for c in plan.original_query
            ):
                try:
                    scored_orig = reranker.rerank(
                        plan.original_query, pool, top_k=len(pool)
                    )
                    by_id = {str(r.get("chunk_id")): r for r in scored_orig}
                    for r in scored:
                        o = by_id.get(str(r.get("chunk_id")))
                        if o and o.get("ce_score") is not None and r.get("ce_score") is not None:
                            r["ce_score"] = 0.65 * float(r["ce_score"]) + 0.35 * float(
                                o["ce_score"]
                            )
                    scored.sort(key=lambda x: float(x.get("ce_score") or 0.0), reverse=True)
                except Exception:
                    pass
            for r in scored:
                r["similarity_score"] = float(r.get("ce_score", r.get("hybrid_score", 0.0)))
            from app.services.rag import _prefer_source_aligned

            return _prefer_source_aligned(ce_query, scored, docs, top_k)
        except Exception as e:  # noqa: BLE001
            logger.warning("multi_query CE blend failed: %s", type(e).__name__)

    return docs[:top_k]


def expand_for_live_search(query: str, *, language: Optional[str] = None) -> str:
    """English-oriented discovery string for live government search."""
    plan = build_retrieval_plan(query, language=language)
    return plan.live_search_query or query


def log_retrieval_diagnostics(
    plan: RetrievalPlan,
    *,
    evidence_passed: Optional[bool] = None,
    live_fallback_used: Optional[bool] = None,
    faiss_n: Optional[int] = None,
    bm25_n: Optional[int] = None,
    merged_n: Optional[int] = None,
    failure_category: Optional[str] = None,
) -> None:
    """Internal-only diagnostics — never send to citizens."""
    payload = plan.diagnostic_dict()
    payload.update(
        {
            "evidence_passed": evidence_passed,
            "live_fallback_used": live_fallback_used,
            "faiss_candidates": faiss_n,
            "bm25_candidates": bm25_n,
            "merged_candidates": merged_n,
            "failure_category": failure_category,
        }
    )
    logger.info("multilingual_diag %s", payload)
