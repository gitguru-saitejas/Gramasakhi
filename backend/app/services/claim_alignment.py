"""Claim intent and domain alignment for evidence gating (Phase 2).

Uses scheme catalog / seed keywords only — no hand-built rule database.
Evidence remains the source of truth; this module detects obvious mismatches
and unsupported specific factual claims before and after LLM generation.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger("gramsakhi.claim_alignment")

_CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "scheme_catalog.json"

# Minimal domain hints derived from catalog keywords + seed document themes.
_DOMAIN_HINTS: Dict[str, Dict[str, Any]] = {
    "pmsby": {
        "positive": {"accident", "suraksha", "disability", "death", "insurance", "bima"},
        "conflicting_topics": {"crop", "yield", "harvest", "fasal", "farmer", "agriculture"},
    },
    "pmfby": {
        "positive": {"crop", "yield", "fasal", "bima", "farmer", "insurance"},
        "conflicting_topics": {"accident", "suraksha", "disability"},
    },
    "shakti": {
        "positive": {"bus", "travel", "ksrtc", "transport", "fare"},
        "scope_sensitive": True,
    },
    "mgnrega": {
        "positive": {"wage", "employment", "nrega", "mgnrega", "job"},
        "numeric_sensitive": True,
    },
    "pmjjby": {
        "positive": {"life", "jeevan", "death", "insurance", "bima"},
        "conflicting_topics": {"crop", "yield", "accident", "suraksha"},
    },
}

_NUMERIC_FACT_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:current|latest|what\s+is\s+the)\s+(?:daily\s+)?wage\b",
        re.I,
    ),
    re.compile(r"\bdaily\s+wage\b", re.I),
    re.compile(r"\bwage\s+(?:in|for)\b", re.I),
    re.compile(r"\b(?:how\s+much|what\s+amount|benefit\s+amount)\b", re.I),
    re.compile(r"\bhow\s+much\s+money\b", re.I),
    re.compile(r"\b(?:pay|pays|paid)\s+(?:each|per)\s+installment\b", re.I),
    re.compile(r"\binstallment\b", re.I),
    re.compile(r"\b(?:rs\.?|₹|inr)\s*\d", re.I),
    re.compile(r"\b(?:monthly|daily)\s+(?:cash\s+)?grant\b", re.I),
)

_QUERY_SEEKS_AMOUNT = re.compile(
    r"\b(?:how\s+much|what\s+amount|what\s+is\s+the\s+amount|benefit\s+amount|"
    r"daily\s+wage|installment|how\s+many\s+rupees|monthly\s+cash\s+grant|"
    r"pay\s+each|pays?\s+each)\b",
    re.I,
)

_PROCEDURAL_DRIFT = re.compile(
    r"\bdeposited\b|\bbank\s+account\b|\bpost\s+office\s+account\b|\bweekly\s+basis\b|"
    r"\bpaid\s+within\s+a\s+week\b|\bwithin\s+a\s+week\b",
    re.I,
)

_WORD_AMOUNTS: Tuple[Tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"\b(?:two|2)\s+thousand\b", re.I), 2000),
    (re.compile(r"\b(?:six|6)\s+thousand\b", re.I), 6000),
    (re.compile(r"\b(?:two|2)\s+lakh\b", re.I), 200000),
)

_UNIVERSAL_SCOPE_QUERY = re.compile(
    r"\b(?:all|every|any)\s+(?:(?:\w+\s+){0,3})?(?:bus|buses|vehicle)\b",
    re.I,
)

_CURRENCY_IN_TEXT = re.compile(
    r"(?:rs\.?|₹|inr)\s*([\d,]+(?:\.\d+)?)|\b(\d{2,6})\s*(?:rupees?|rs\.?)\b",
    re.I,
)

_AFFIRMATIVE_COVERAGE = re.compile(
    r"\b(?:yes|covers?|includes?|available\s+on|applies?\s+to)\b.*\b(?:all|every)\b",
    re.I,
)
_DEFINITIVE_YES = re.compile(
    r"^\s*(?:yes|indeed|certainly|absolutely)\b",
    re.I,
)
_DEFINITIVE_NO = re.compile(
    r"^\s*(?:no|not)\b",
    re.I,
)

_INSUFFICIENCY_OPENING = re.compile(
    r"\b(?:not explicitly stated|not stated|does not contain|does not specify|"
    r"does not provide the specific|does not provide\s+the\s+specific|"
    r"insufficient|cannot determine|cannot be determined|no specific|not mentioned|"
    r"not available in the (?:supplied|provided|available) evidence)\b",
    re.I,
)

_FActual_EXPANSION = re.compile(
    r"\b(?:provides|offers|guarantees|covers|includes|workers receive|beneficiaries get|"
    r"employment guarantee|days of employment|per day|daily wage)\b",
    re.I,
)


@dataclass
class ClaimAnalysis:
    scheme_id: Optional[str] = None
    scheme_name: Optional[str] = None
    is_numeric_fact: bool = False
    is_scope_question: bool = False
    is_domain_topic_query: bool = False
    query_topics: Set[str] = field(default_factory=set)
    signals: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClaimSupportResult:
    ok: bool
    reason: str = "ok"
    detail: str = ""
    signals: Dict[str, Any] = field(default_factory=dict)


@lru_cache(maxsize=1)
def _load_catalog_schemes() -> Dict[str, Dict[str, Any]]:
    try:
        raw = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("claim_alignment catalog load failed: %s", exc)
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for item in raw.get("schemes") or []:
        sid = str(item.get("id") or "").strip().lower()
        if sid:
            out[sid] = item
    return out


def _tokenize(text: str) -> Set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _doc_corpus(docs: Sequence[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for doc in docs or []:
        parts.append(str(doc.get("content") or doc.get("text") or ""))
        meta = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
        parts.extend(
            [
                str(doc.get("scheme_name") or ""),
                str(doc.get("document_title") or ""),
                str(doc.get("source") or ""),
                str(meta.get("source") or ""),
            ]
        )
    return " ".join(parts).lower()


def _catalog_id_for_label(label: str) -> Optional[str]:
    needle = (label or "").strip().lower()
    if not needle:
        return None
    for sid, item in _load_catalog_schemes().items():
        name = str(item.get("name") or "").lower()
        if needle == name or needle in name or name in needle:
            return sid
    return None


def _resolve_scheme(query: str) -> Tuple[Optional[str], Optional[str]]:
    try:
        from app.services.myscheme_service import requested_scheme_identity, slug_hint_from_query

        identity = requested_scheme_identity(query)
        if identity:
            sid = str(identity.get("scheme_id") or "").strip().lower()
            name = str(identity.get("scheme_name") or "").strip()
            if sid or name:
                resolved = sid or slug_hint_from_query(name)
                if not resolved and name:
                    resolved = _catalog_id_for_label(name)
                return resolved, name or None
    except Exception:  # noqa: BLE001
        pass
    q = (query or "").lower()
    for sid, item in _load_catalog_schemes().items():
        keywords = [str(k).lower() for k in (item.get("keywords") or [])]
        name = str(item.get("name") or "").lower()
        if name and name in q:
            return sid, str(item.get("name") or "")
        if sid.replace("-", " ") in q or sid in q:
            return sid, str(item.get("name") or "")
        for kw in keywords:
            if kw and kw in q:
                return sid, str(item.get("name") or "")
    return None, None


def analyze_claim(query: str, *, scheme_id: Optional[str] = None) -> ClaimAnalysis:
    q = (query or "").strip()
    sid, sname = _resolve_scheme(q)
    sid = (scheme_id or sid or "").strip().lower() or None
    tokens = _tokenize(q)
    analysis = ClaimAnalysis(
        scheme_id=sid,
        scheme_name=sname,
        query_topics=tokens,
    )
    analysis.is_numeric_fact = query_requests_specific_amount(q)
    analysis.is_scope_question = bool(_UNIVERSAL_SCOPE_QUERY.search(q))

    hints = _DOMAIN_HINTS.get(sid or "", {})
    conflicting = hints.get("conflicting_topics") or set()
    positive = hints.get("positive") or set()
    if conflicting and tokens & conflicting:
        analysis.is_domain_topic_query = True
        analysis.signals["conflicting_topics"] = sorted(tokens & conflicting)
    if positive and tokens & positive:
        analysis.signals["domain_topics"] = sorted(tokens & positive)
    return analysis


def _domain_mismatch(query: str, scheme_id: Optional[str]) -> Optional[str]:
    sid = (scheme_id or "").strip().lower()
    hints = _DOMAIN_HINTS.get(sid)
    if not hints:
        return None
    tokens = _tokenize(query)
    conflicting = hints.get("conflicting_topics") or set()
    overlap = tokens & conflicting
    if overlap:
        return f"domain_topic_mismatch:{sid}:{'/'.join(sorted(overlap))}"
    return None


def _has_affirmative_coverage(text: str) -> bool:
    """True when cover/include is used affirmatively, not in negation ('does not cover')."""
    low = (text or "").lower()
    for m in re.finditer(r"\b(?:covers?|includes?)\b", low):
        start = max(0, m.start() - 40)
        prefix = low[start : m.start()]
        if re.search(r"\b(?:not|no|never|doesn't|don't|cannot|can't|without)\s+\w*\s*$", prefix):
            continue
        return True
    return False


def _affirms_topic_coverage(text: str, topics: Set[str]) -> bool:
    """True when text affirmatively claims coverage for a conflicting topic (not negated)."""
    low = (text or "").lower()
    for term in topics:
        idx = low.find(term)
        if idx < 0:
            continue
        window = low[max(0, idx - 55) : idx + len(term) + 35]
        if re.search(
            r"\b(?:not|no|never|doesn't|don't|exclude|outside scope|not covered)\b",
            window,
        ):
            continue
        if re.search(r"\b(?:covers?|includes?|pays for|provides)\b", window):
            return True
        if _DEFINITIVE_YES.search(window):
            return True
    return False


def _topics_negated_in_text(text: str, topics: Set[str]) -> bool:
    """True when every conflicting topic mention is explicitly negated in the answer."""
    if not topics:
        return False
    low = (text or "").lower()
    for topic in topics:
        idx = low.find(topic)
        if idx < 0:
            continue
        window = low[max(0, idx - 55) : idx + len(topic) + 35]
        if not re.search(
            r"\b(?:does not|do not|doesn't|don't|not|no|never|cannot|can't|exclude|outside scope)\b",
            window,
        ):
            return False
    mentioned = [t for t in topics if t in low]
    return bool(mentioned)


def _answer_drifts_after_insufficiency(
    answer: str,
    corpus: str,
    *,
    scheme_id: Optional[str] = None,
    query: str = "",
) -> bool:
    """Detect cautious opening followed by unsupported factual expansion (e.g. MGNREGA drift)."""
    a = (answer or "").strip()
    if not a or not _INSUFFICIENCY_OPENING.search(a):
        return False
    hints = _DOMAIN_HINTS.get((scheme_id or "").lower(), {})
    conflicting = hints.get("conflicting_topics") or set()
    q_tokens = _tokenize(query)
    if conflicting and _topics_negated_in_text(a, conflicting & (q_tokens | _tokenize(a))):
        return False
    parts = re.split(r"(?<=[.!?])\s+", a, maxsplit=1)
    if len(parts) < 2:
        return False
    body = parts[1].strip()
    if len(body) < 40:
        return False
    wage_query = bool(re.search(r"\bwage\b|\bdaily\b", query, re.I))
    if hints.get("numeric_sensitive") or wage_query:
        if _unsupported_amounts_in_answer(query, body, corpus):
            return True
        if re.search(r"\b\d+\s*(?:days|rupees|rs|₹|percent|%)\b", body, re.I):
            if not _evidence_has_numeric_amount(corpus):
                return True
    if wage_query and _PROCEDURAL_DRIFT.search(body):
        return True
    if _FActual_EXPANSION.search(body):
        body_tokens = _tokenize(body)
        corpus_tokens = _tokenize(corpus)
        stop = {
            "the", "a", "an", "is", "are", "was", "for", "to", "in", "of", "and", "or",
            "this", "that", "scheme", "program", "programme", "under", "also", "may",
            "pmsby", "pmfby", "mgnrega", "shakti", "farmers", "citizen", "citizens",
        }
        if body_tokens:
            supported_ratio = len(body_tokens & corpus_tokens) / float(len(body_tokens))
            if supported_ratio >= 0.55:
                return False
        novel = body_tokens - corpus_tokens - stop
        if len(novel) >= 6:
            return True
    return False


def _evidence_has_numeric_amount(corpus: str) -> bool:
    return bool(_extract_amount_values(corpus))


_AMOUNT_CONTEXT_WINDOW = 120

_INSTALLMENT_CONTEXT = re.compile(
    r"\b(?:installment|equal\s+installment|per\s+annum|per\s+year|"
    r"payable\s+in|income\s+support|financial\s+benefit|benefit\s+amount|"
    r"each[,]?\s+every)\b",
    re.I,
)
_WAGE_CONTEXT = re.compile(
    r"\b(?:daily\s+wage|wage\s+rate|wage\s+for|minimum\s+wage|"
    r"notified\s+wage|per\s+day|wage\s+amount)\b",
    re.I,
)
_GENERAL_BENEFIT_CONTEXT = re.compile(
    r"\b(?:benefit|subsidy|grant|premium|sum\s+insured|coverage\s+amount|"
    r"financial\s+assistance|assistance\s+of)\b",
    re.I,
)
_ADMIN_EXPENSE_CONTEXT = re.compile(
    r"\b(?:reimburs(?:e|ed|ement)|district\s+level\s+function|block\s+level|"
    r"state\s+level\s+function|expenditure\s+incurred)\b",
    re.I,
)
_INSTALLMENT_QUERY = re.compile(r"\b(?:installment|instalment|pay\s+each)\b", re.I)
_INSTALLMENT_AMOUNT_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?:installment|instalment)s?\s*(?:of|is|:)?\s*(?:rs\.?|₹|inr)?\s*([\d,]+)",
        re.I,
    ),
    re.compile(
        r"(?:rs\.?|₹|inr)?\s*([\d,]+)\s*(?:per|each)\s*(?:equal\s+)?installment",
        re.I,
    ),
    re.compile(
        r"(?:three|3)\s+equal\s+installments?\s+(?:of\s+)?(?:rs\.?|₹|inr)?\s*([\d,]+)",
        re.I,
    ),
    re.compile(
        r"installment\s+amount\s*(?:rs\.?|₹|inr)?\s*([\d,]+)",
        re.I,
    ),
)


def _is_fragmentary_evidence_chunk(text: str) -> bool:
    """True for OCR/noise snippets that must not ground specific numeric claims."""
    chunk = (text or "").strip()
    if not chunk:
        return True
    if len(chunk) < 32:
        return True
    # Mid-word clippings such as "r land holdings. What are..."
    if re.match(r"^[a-z]{1,2}\s+[a-z]", chunk):
        return True
    return False


def _docs_for_numeric_grounding(
    query: str,
    docs: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Scheme-aligned, non-fragment evidence usable for installment/wage amounts."""
    analysis = analyze_claim(query)
    sid = (analysis.scheme_id or "").strip().lower()
    eligible: List[Dict[str, Any]] = []
    for doc in docs or ():
        content = str(doc.get("content") or doc.get("text") or "")
        if _is_fragmentary_evidence_chunk(content):
            continue
        if sid:
            meta = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
            doc_sid = str(doc.get("scheme_id") or meta.get("scheme_id") or "").strip().lower()
            if doc_sid != sid:
                continue
        eligible.append(doc)
    return eligible


def _amount_context_ok(window: str, query: str) -> bool:
    w = (window or "").lower()
    if _ADMIN_EXPENSE_CONTEXT.search(w) and not _INSTALLMENT_CONTEXT.search(w):
        return False
    if re.search(r"\binstallment\b|\bpay\s+each\b|\bpays?\s+each\b", query, re.I):
        return bool(_INSTALLMENT_CONTEXT.search(w))
    if re.search(r"\bwage\b|\bdaily\b", query, re.I):
        return bool(_WAGE_CONTEXT.search(w))
    return bool(_GENERAL_BENEFIT_CONTEXT.search(w) or _INSTALLMENT_CONTEXT.search(w))


def _supported_installment_amounts(
    query: str,
    docs: Sequence[Dict[str, Any]],
) -> Set[int]:
    """Per-installment figures only (not annual totals without an installment breakdown)."""
    if not _INSTALLMENT_QUERY.search(query or ""):
        return set()
    supported: Set[int] = set()
    for doc in _docs_for_numeric_grounding(query, docs):
        chunk = str(doc.get("content") or "")
        if not chunk.strip():
            continue
        for pat in _INSTALLMENT_AMOUNT_PATTERNS:
            for m in pat.finditer(chunk):
                raw = (m.group(1) or "").replace(",", "")
                try:
                    val = int(float(raw))
                except (TypeError, ValueError):
                    continue
                if val >= 100:
                    supported.add(val)
    return supported


def _supported_amounts_for_query(
    query: str,
    docs: Sequence[Dict[str, Any]],
) -> Set[int]:
    """Amounts that appear in evidence near benefit/installment/wage context for this query."""
    supported: Set[int] = set()
    for doc in _docs_for_numeric_grounding(query, docs):
        chunk = str(doc.get("content") or "")
        if not chunk.strip():
            continue
        low = chunk.lower()
        for m in _CURRENCY_IN_TEXT.finditer(chunk):
            raw = (m.group(1) or m.group(2) or "").replace(",", "")
            try:
                val = int(float(raw))
            except (TypeError, ValueError):
                continue
            if val < 100:
                continue
            window = low[
                max(0, m.start() - _AMOUNT_CONTEXT_WINDOW) : m.end() + _AMOUNT_CONTEXT_WINDOW
            ]
            if _amount_context_ok(window, query):
                supported.add(val)
        for pat, val in _WORD_AMOUNTS:
            for wm in pat.finditer(low):
                window = low[
                    max(0, wm.start() - _AMOUNT_CONTEXT_WINDOW) : wm.end() + _AMOUNT_CONTEXT_WINDOW
                ]
                if _amount_context_ok(window, query):
                    supported.add(val)
    return supported


def _evidence_has_query_relevant_amount(
    query: str,
    docs: Sequence[Dict[str, Any]],
    *,
    corpus: str = "",
) -> bool:
    aligned = _docs_for_numeric_grounding(query, docs)
    if aligned:
        return bool(_supported_amounts_for_query(query, aligned))
    if docs:
        return False
    return _evidence_has_numeric_amount(corpus)


def query_requests_specific_amount(query: str) -> bool:
    q = (query or "").strip()
    if not q:
        return False
    if _QUERY_SEEKS_AMOUNT.search(q):
        return True
    return any(p.search(q) for p in _NUMERIC_FACT_PATTERNS)


def _extract_amount_values(text: str) -> Set[int]:
    """Normalize currency / common word amounts for grounding checks."""
    values: Set[int] = set()
    blob = (text or "").lower()
    for m in _CURRENCY_IN_TEXT.finditer(text or ""):
        raw = (m.group(1) or m.group(2) or "").replace(",", "")
        try:
            val = int(float(raw))
            if val >= 100:
                values.add(val)
        except (TypeError, ValueError):
            continue
    for pat, val in _WORD_AMOUNTS:
        if pat.search(blob):
            values.add(val)
    for m in re.finditer(r"\b(\d{3,6})\b", blob):
        try:
            val = int(m.group(1))
            if val >= 100:
                values.add(val)
        except ValueError:
            continue
    return values


def _amount_negated_in_answer(answer: str, amount: int) -> bool:
    """True when the amount appears only in an explicit negation/refusal window."""
    low = (answer or "").lower()
    amt_str = str(amount)
    for token in (amt_str, f"{amount:,}", f"{amount // 1000},000" if amount >= 1000 else amt_str):
        idx = low.find(token.replace(",", "")) if token else -1
        if idx < 0 and "," in token:
            idx = low.find(token.lower())
        if idx < 0:
            continue
        window = low[max(0, idx - 90) : idx + len(token) + 40]
        if re.search(
            r"\b(?:does not|do not|doesn't|don't|not|no|never|cannot|can't|"
            r"insufficient|not establish|not confirm|not contain|not state|not provide)\b",
            window,
        ):
            return True
    return False


def _unsupported_amounts_in_answer(
    query: str,
    answer: str,
    corpus: str,
    *,
    docs: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[int]:
    """Amounts in the answer that the query seeks but corpus does not support."""
    if not query_requests_specific_amount(query):
        return []
    if docs:
        if _INSTALLMENT_QUERY.search(query):
            corpus_amounts = _supported_installment_amounts(query, docs)
        else:
            corpus_amounts = _supported_amounts_for_query(query, docs)
    else:
        corpus_amounts = _extract_amount_values(corpus)
    leaked: List[int] = []
    for amt in sorted(_extract_amount_values(answer)):
        if amt in corpus_amounts:
            continue
        if _amount_negated_in_answer(answer, amt):
            continue
        leaked.append(amt)
    return leaked


def _evidence_supports_universal_scope(corpus: str) -> bool:
    low = corpus.lower()
    if re.search(r"\ball\b.*\b(?:bus|buses|private)\b", low):
        return True
    if re.search(r"\bevery\b.*\b(?:bus|buses)\b", low):
        return True
    return False


def _evidence_supports_topic(corpus: str, topics: Set[str]) -> bool:
    if not topics:
        return True
    tokens = _tokenize(corpus)
    return bool(tokens & topics)


def check_claim_support(
    query: str,
    docs: Sequence[Dict[str, Any]],
    *,
    claim: Optional[ClaimAnalysis] = None,
) -> ClaimSupportResult:
    """Pre-LLM gate: fail closed on obvious unsupported specific factual claims."""
    q = (query or "").strip()
    if not q:
        return ClaimSupportResult(ok=True, reason="empty_query")

    analysis = claim or analyze_claim(q)
    corpus = _doc_corpus(docs)
    if not corpus.strip():
        return ClaimSupportResult(ok=False, reason="no_evidence_corpus")

    mismatch = _domain_mismatch(q, analysis.scheme_id)
    if mismatch:
        conflicting = (_DOMAIN_HINTS.get(analysis.scheme_id or "") or {}).get("conflicting_topics") or set()
        query_conflict = analysis.query_topics & conflicting
        if query_conflict and not _evidence_supports_topic(corpus, query_conflict):
            return ClaimSupportResult(
                ok=False,
                reason="domain_mismatch",
                detail=mismatch,
                signals={
                    "scheme_id": analysis.scheme_id,
                    "conflicting_topics": sorted(query_conflict),
                },
            )

    hints = _DOMAIN_HINTS.get(analysis.scheme_id or "", {})
    if analysis.is_numeric_fact or hints.get("numeric_sensitive"):
        if analysis.is_numeric_fact and _INSTALLMENT_QUERY.search(q):
            if not _supported_installment_amounts(q, docs):
                return ClaimSupportResult(
                    ok=False,
                    reason="unsupported_numeric_fact",
                    detail="installment_amount_not_in_evidence",
                    signals={"scheme_id": analysis.scheme_id},
                )
        if analysis.is_numeric_fact and not _evidence_has_query_relevant_amount(
            q, docs, corpus=corpus
        ):
            wage_context = bool(re.search(r"\bwage\b|\bdaily\b|\brate\b", q, re.I))
            corpus_wage = bool(re.search(r"\bwage\b|\bdaily\b|\brate\b", corpus, re.I))
            if wage_context and not corpus_wage:
                return ClaimSupportResult(
                    ok=False,
                    reason="unsupported_numeric_fact",
                    detail="wage_amount_not_in_evidence",
                    signals={"scheme_id": analysis.scheme_id},
                )
            if analysis.is_numeric_fact and not _evidence_has_query_relevant_amount(
                q, docs, corpus=corpus
            ):
                return ClaimSupportResult(
                    ok=False,
                    reason="unsupported_numeric_fact",
                    detail="amount_not_in_evidence",
                    signals={"scheme_id": analysis.scheme_id},
                )

    if analysis.is_scope_question and hints.get("scope_sensitive"):
        if not _evidence_supports_universal_scope(corpus):
            return ClaimSupportResult(
                ok=False,
                reason="unsupported_scope_claim",
                detail="universal_scope_not_in_evidence",
                signals={"scheme_id": analysis.scheme_id},
            )

    return ClaimSupportResult(ok=True, reason="claim_supported")


def check_answer_grounding(
    query: str,
    answer: str,
    docs: Sequence[Dict[str, Any]],
    *,
    claim: Optional[ClaimAnalysis] = None,
) -> ClaimSupportResult:
    """Post-LLM guard: reject hallucinated specifics leaking into the answer."""
    q = (query or "").strip()
    a = (answer or "").strip()
    if not a:
        return ClaimSupportResult(ok=True, reason="empty_answer")

    analysis = claim or analyze_claim(q)
    corpus = _doc_corpus(docs)

    mismatch = _domain_mismatch(q, analysis.scheme_id)
    if mismatch:
        conflicting = (_DOMAIN_HINTS.get(analysis.scheme_id or "") or {}).get("conflicting_topics") or set()
        answer_tokens = _tokenize(a)
        answer_conflict = answer_tokens & conflicting
        if answer_conflict and not _evidence_supports_topic(corpus, answer_conflict):
            if not _topics_negated_in_text(a, answer_conflict):
                return ClaimSupportResult(
                    ok=False,
                    reason="answer_domain_mismatch",
                    detail=mismatch,
                )

    if analysis.scheme_id == "pmsby" and re.search(r"\b(?:crop|yield|harvest|fasal)\b", a, re.I):
        if not re.search(r"\b(?:crop|yield|harvest|fasal)\b", corpus, re.I):
            crop_topics = {"crop", "yield", "harvest", "fasal"} & _tokenize(a)
            if _affirms_topic_coverage(a, crop_topics):
                return ClaimSupportResult(
                    ok=False,
                    reason="answer_domain_mismatch",
                    detail="pmsby_crop_claim_without_evidence",
                )

    if _answer_drifts_after_insufficiency(a, corpus, scheme_id=analysis.scheme_id, query=q):
        return ClaimSupportResult(
            ok=False,
            reason="answer_drift_after_insufficiency",
            detail="unsupported_expansion_after_limitation",
        )

    leaked_amounts = _unsupported_amounts_in_answer(q, a, corpus, docs=docs)
    if leaked_amounts:
        return ClaimSupportResult(
            ok=False,
            reason="answer_unsupported_amount",
            detail=f"amounts_not_in_evidence:{','.join(str(x) for x in leaked_amounts[:5])}",
            signals={"leaked_amounts": leaked_amounts},
        )

    if analysis.is_scope_question and (_AFFIRMATIVE_COVERAGE.search(a) or _DEFINITIVE_YES.search(a)):
        hints = _DOMAIN_HINTS.get(analysis.scheme_id or "", {})
        if hints.get("scope_sensitive") and not _evidence_supports_universal_scope(corpus):
            if not re.search(r"\b(?:not|no|never|doesn't|don't)\b", a[:120], re.I):
                return ClaimSupportResult(
                    ok=False,
                    reason="answer_unsupported_scope",
                    detail="universal_scope_affirmed_without_evidence",
                )

    return ClaimSupportResult(ok=True, reason="answer_grounded")
