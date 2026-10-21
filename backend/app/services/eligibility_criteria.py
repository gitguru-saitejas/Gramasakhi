"""Stage 6B-1 — structured eligibility criteria extraction from validated evidence.

Operates on evidence that already passed the Evidence Validator gate.
Does not fetch, rank, or invent criteria. No eligibility decisions.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

logger_name = "gramsakhi.eligibility_criteria"


class CriterionType(str, Enum):
    AGE = "age"
    GENDER = "gender"
    STATE = "state"
    DISTRICT = "district"
    RESIDENCE = "residence"
    OCCUPATION = "occupation"
    EMPLOYMENT = "employment"
    INCOME = "income"
    LANDHOLDING = "landholding"
    SOCIAL_CATEGORY = "social_category"
    EDUCATION = "education"
    MARITAL_STATUS = "marital_status"
    BENEFICIARY_STATUS = "beneficiary_status"
    OWNERSHIP = "ownership"
    SCHEME_SPECIFIC = "scheme_specific"
    OTHER = "other"


class CriterionConfidence(str, Enum):
    EXPLICIT = "explicit"
    UNSTRUCTURED = "unstructured"
    NOT_SPECIFIED = "not_specified"


# Evidence section marker from myScheme / provider packaging.
_ELIGIBILITY_SECTION = re.compile(
    r"SECTION:\s*Eligibility\s*\n+\s*CONTENT:\s*(.*?)(?=\n\nSECTION:|\Z)",
    re.I | re.S,
)

_AGE_RANGE = re.compile(
    r"(?:age\s*(?:group\s*)?(?:of\s*)?|aged?\s+)"
    r"(?:between\s+)?(\d{1,3})\s*(?:to|-|and)\s*(\d{1,3})\s*(?:years?|yrs?|year\s+old)",
    re.I,
)
_AGE_MIN = re.compile(
    r"(?:at\s+least|minimum\s+age|min\.?\s+age|not\s+less\s+than|above)\s*"
    r"(?:of\s*)?(\d{1,3})\s*(?:years?|yrs?)",
    re.I,
)
_AGE_MAX = re.compile(
    r"(?:maximum\s+age|max\.?\s+age|not\s+(?:more\s+than|exceed(?:ing)?)|up\s+to)\s*"
    r"(?:of\s*)?(\d{1,3})\s*(?:years?|yrs?)",
    re.I,
)
_AGE_YEARS = re.compile(
    r"(\d{1,3})\s*(?:years?\s+old|years?|yrs?)(?:\s+of\s+age)?",
    re.I,
)
_AGE_BAND = re.compile(
    r"(?:commonly|eligible\s+age\s+band|age\s+band).*?(?:commonly\s+)?"
    r"(\d{1,3})\s*(?:to|-|and)\s*(\d{1,3})\s*(?:years?|yrs?)?",
    re.I,
)
_AGE_COMMONLY_PAREN = re.compile(
    r"\(\s*commonly\s+(\d{1,3})\s*(?:to|-|and)\s*(\d{1,3})\s*years?\s*\)",
    re.I,
)
_AGE_HYPHEN_BAND = re.compile(
    r"\b(\d{1,3})\s*-\s*(\d{1,3})\s*(?:years?|yrs?|band)?\b",
    re.I,
)
_AGE_BAND_SIMPLE = re.compile(
    r"\b(\d{1,3})\s*(?:to|-|and)\s*(\d{1,3})\s*(?:years?|yrs?)\b",
    re.I,
)

_INCOME_MAX = re.compile(
    r"(?:income|family\s+income|annual\s+income|household\s+income)"
    r"(?:\s+should\s+not\s+exceed|\s+below|\s+under|\s+not\s+exceed(?:ing)?|\s+upto|\s+up\s+to|\s+<=)"
    r"\s*(?:₹|rs\.?|inr)?\s*([\d]+(?:\.\d+)?)\s*(lakh|lac|crore|cr|thousand|k)?",
    re.I,
)
_INCOME_BELOW = re.compile(
    r"(?:income|family\s+income)\s+(?:below|under|less\s+than)\s+"
    r"(?:₹|rs\.?|inr)?\s*([\d]+(?:\.\d+)?)\s*(lakh|lac|crore|cr)?",
    re.I,
)

_GENDER_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (r"\bwomen\b|\bfemale\b|\bwoman\b|\bಮಹಿಳ|\bमहिल", "female"),
    (r"\bmen\b|\bmale\b|\bman\b|\bಪುರುಷ|\bपुरुष", "male"),
    (r"\btransgender\b", "transgender"),
)

_STATE_NAMES = (
    "andhra pradesh",
    "arunachal pradesh",
    "assam",
    "bihar",
    "chhattisgarh",
    "goa",
    "gujarat",
    "haryana",
    "himachal pradesh",
    "jharkhand",
    "karnataka",
    "kerala",
    "madhya pradesh",
    "maharashtra",
    "manipur",
    "meghalaya",
    "mizoram",
    "nagaland",
    "odisha",
    "punjab",
    "rajasthan",
    "sikkim",
    "tamil nadu",
    "telangana",
    "tripura",
    "uttar pradesh",
    "uttarakhand",
    "west bengal",
    "delhi",
    "jammu and kashmir",
    "ladakh",
)

_OCCUPATION_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (r"\bfarmers?\b|\bಕೃಷಿಕ|\bकिसान", "farmer"),
    (r"\bentrepreneurs?\b|\bwomen entrepreneurs\b", "entrepreneur"),
    (r"\bstudents?\b|\bವಿದ್ಯಾರ್ಥ|\bछात्र", "student"),
    (r"\bunemployed\b|\bನಿರುದ್ಯೋಗ|\bबेरोज", "unemployed"),
    (r"\bself[- ]?employed\b", "self_employed"),
    (r"\bworkers?\b|\blabou?rers?\b", "worker"),
)

_AMBIGUOUS_PHRASES = (
    "young applicants",
    "young beneficiary",
    "low income",
    "low-income",
    "economically weaker",
    "eligible beneficiaries",
    "specified beneficiary group",
    "as notified",
    "as prescribed",
)

_OR_SPLIT = re.compile(r"\s+(?:or|either)\s+", re.I)
_AND_SPLIT = re.compile(r"\s+and\s+", re.I)


@dataclass
class EligibilityCriterion:
    criterion_type: str
    statement: str
    operator: Optional[str] = None
    value: Optional[Any] = None
    value_max: Optional[Any] = None
    unit: Optional[str] = None
    currency: Optional[str] = None
    logical_connector: Optional[str] = None
    explicitly_stated: bool = True
    confidence: str = CriterionConfidence.EXPLICIT.value
    source_url: Optional[str] = None
    document_url: Optional[str] = None
    document_id: Optional[str] = None
    evidence_ref: Optional[str] = None
    scheme_name: Optional[str] = None
    scheme_id: Optional[str] = None
    retrieval_timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EligibilityCriteriaResult:
    scheme_name: Optional[str] = None
    scheme_id: Optional[str] = None
    criteria: List[EligibilityCriterion] = field(default_factory=list)
    unstructured_statements: List[str] = field(default_factory=list)
    rejected: bool = False
    rejection_reason: Optional[str] = None
    extraction_status: str = "ok"
    makes_eligibility_decision: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scheme_name": self.scheme_name,
            "scheme_id": self.scheme_id,
            "criteria": [c.to_dict() for c in self.criteria],
            "unstructured_statements": list(self.unstructured_statements),
            "rejected": self.rejected,
            "rejection_reason": self.rejection_reason,
            "extraction_status": self.extraction_status,
            "makes_eligibility_decision": self.makes_eligibility_decision,
            "required_information_types": self.required_information_types(),
        }

    def required_information_types(self) -> List[str]:
        """Information types implied by extracted criteria (foundation for 6B-2)."""
        mapping = {
            CriterionType.AGE.value: "age",
            CriterionType.GENDER.value: "gender",
            CriterionType.STATE.value: "state",
            CriterionType.DISTRICT.value: "district",
            CriterionType.RESIDENCE.value: "residence",
            CriterionType.OCCUPATION.value: "occupation",
            CriterionType.EMPLOYMENT.value: "employment",
            CriterionType.INCOME.value: "income",
            CriterionType.LANDHOLDING.value: "landholding",
            CriterionType.SOCIAL_CATEGORY.value: "social_category",
            CriterionType.EDUCATION.value: "education",
            CriterionType.MARITAL_STATUS.value: "marital_status",
            CriterionType.BENEFICIARY_STATUS.value: "beneficiary_status",
            CriterionType.OWNERSHIP.value: "ownership",
            CriterionType.SCHEME_SPECIFIC.value: "scheme_specific",
        }
        out: List[str] = []
        for c in self.criteria:
            key = mapping.get(c.criterion_type)
            if key and key not in out:
                out.append(key)
        return out


def _normalize_evidence(evidence: Any) -> List[Dict[str, Any]]:
    if evidence is None:
        return []
    if isinstance(evidence, dict):
        return [evidence]
    return [d for d in evidence if isinstance(d, dict)]


def _doc_meta(doc: Dict[str, Any], *keys: str) -> Any:
    meta = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    for key in keys:
        val = doc.get(key)
        if val not in (None, ""):
            return val
        if meta:
            val = meta.get(key)
            if val not in (None, ""):
                return val
    return None


def _doc_source_urls(doc: Dict[str, Any]) -> Tuple[str, str]:
    source = str(
        _doc_meta(doc, "source", "url", "canonical_url", "document_url") or ""
    ).strip()
    document_url = source
    dtype = str(_doc_meta(doc, "document_type") or "").upper()
    src_l = source.lower()
    is_pdf = bool(doc.get("is_pdf")) or "PDF" in dtype or src_l.endswith(".pdf") or "/pdf" in src_l
    if is_pdf and source:
        document_url = source
    return source, document_url


def _extract_eligibility_blobs(content: str) -> List[str]:
    text = (content or "").strip()
    if not text:
        return []
    blobs: List[str] = []
    for match in _ELIGIBILITY_SECTION.finditer(text):
        body = (match.group(1) or "").strip()
        if len(body) >= 15:
            blobs.append(body)
    if blobs:
        return blobs
    # Plain heading fallback (HTML-normalized evidence).
    for match in re.finditer(
        r"(?i)(?:^|\n)\s*eligibility\s*[:\-]?\s*\n+(.*?)(?=\n\s*(?:benefits|documents|application|faq)\s*[:\-]|\Z)",
        text,
        re.S,
    ):
        body = (match.group(1) or "").strip()
        if len(body) >= 15:
            blobs.append(body)
    if blobs:
        return blobs
    low = text.lower()
    if any(k in low for k in ("eligib", "who can apply", "who is eligible", "criteria")):
        # Use whole chunk when clearly eligibility-focused and no section split found.
        if "section:" not in low or "eligibility" in low:
            return [text[:4000]]
    if re.search(
        r"\b(?:commonly|age\s+band).*?\d{1,3}\s*(?:to|-|and)\s*\d{1,3}\s*years?\b",
        low,
    ):
        return [text[:4000]]
    if re.search(r"growing notified crops in notified areas|coverage applies only for crops", low):
        return [text[:4000]]
    return []


def _parse_indian_amount(num: str, unit: Optional[str]) -> Optional[int]:
    try:
        val = float(num)
    except ValueError:
        return None
    u = (unit or "").lower()
    if u in ("lakh", "lac"):
        return int(val * 100_000)
    if u in ("crore", "cr"):
        return int(val * 10_000_000)
    if u in ("thousand", "k"):
        return int(val * 1_000)
    return int(val)


def _is_ambiguous(statement: str) -> bool:
    low = statement.lower()
    return any(p in low for p in _AMBIGUOUS_PHRASES)


def _split_logical_clauses(sentence: str) -> List[Tuple[str, Optional[str]]]:
    """Return (clause, connector_to_next) preserving OR before AND."""
    s = re.sub(r"\s+", " ", (sentence or "").strip())
    if not s:
        return []
    if re.search(r"\beither\b|\bor\b", s, re.I):
        parts = _OR_SPLIT.split(s)
        out: List[Tuple[str, Optional[str]]] = []
        for i, part in enumerate(parts):
            out.append((part.strip(), "OR" if i < len(parts) - 1 else None))
        return out
    if re.search(r"\band\b", s, re.I):
        parts = _AND_SPLIT.split(s)
        out = []
        for i, part in enumerate(parts):
            out.append((part.strip(), "AND" if i < len(parts) - 1 else None))
        return out
    return [(s, None)]


def _parse_age_criteria(clause: str, *, connector: Optional[str], base: Dict[str, Any]) -> List[EligibilityCriterion]:
    m_paren = _AGE_COMMONLY_PAREN.search(clause)
    m_notified_band = _AGE_BAND.search(clause)
    if m_paren or m_notified_band:
        m = m_paren or m_notified_band
        lo, hi = int(m.group(1)), int(m.group(2))
        if lo > hi:
            lo, hi = hi, lo
        return [
            EligibilityCriterion(
                criterion_type=CriterionType.AGE.value,
                statement=clause.strip(),
                operator=">=",
                value=lo,
                unit="years",
                logical_connector="AND",
                confidence=CriterionConfidence.EXPLICIT.value,
                **base,
            ),
            EligibilityCriterion(
                criterion_type=CriterionType.AGE.value,
                statement=clause.strip(),
                operator="<=",
                value=hi,
                unit="years",
                logical_connector=connector,
                confidence=CriterionConfidence.EXPLICIT.value,
                **base,
            ),
        ]
    m_band = _AGE_BAND_SIMPLE.search(clause) if re.search(r"\bage\b", clause, re.I) else None
    if m_band:
        return [
            EligibilityCriterion(
                criterion_type=CriterionType.AGE.value,
                statement=clause.strip(),
                operator="between",
                value=int(m_band.group(1)),
                value_max=int(m_band.group(2)),
                unit="years",
                logical_connector=connector,
                confidence=CriterionConfidence.EXPLICIT.value,
                **base,
            )
        ]
    if _is_ambiguous(clause):
        return []
    out: List[EligibilityCriterion] = []
    m = _AGE_RANGE.search(clause)
    if m:
        out.append(
            EligibilityCriterion(
                criterion_type=CriterionType.AGE.value,
                statement=clause.strip(),
                operator="between",
                value=int(m.group(1)),
                value_max=int(m.group(2)),
                unit="years",
                logical_connector=connector,
                confidence=CriterionConfidence.EXPLICIT.value,
                **base,
            )
        )
        return out
    m_min = _AGE_MIN.search(clause)
    m_max = _AGE_MAX.search(clause)
    if m_min:
        out.append(
            EligibilityCriterion(
                criterion_type=CriterionType.AGE.value,
                statement=clause.strip(),
                operator=">=",
                value=int(m_min.group(1)),
                unit="years",
                logical_connector=connector,
                confidence=CriterionConfidence.EXPLICIT.value,
                **base,
            )
        )
    if m_max:
        out.append(
            EligibilityCriterion(
                criterion_type=CriterionType.AGE.value,
                statement=clause.strip(),
                operator="<=",
                value=int(m_max.group(1)),
                unit="years",
                logical_connector=connector,
                confidence=CriterionConfidence.EXPLICIT.value,
                **base,
            )
        )
    if out:
        return out
    m_hyphen = _AGE_HYPHEN_BAND.search(clause) if re.search(r"\bage\b|band\b", clause, re.I) else None
    if m_hyphen:
        lo, hi = int(m_hyphen.group(1)), int(m_hyphen.group(2))
        if lo > hi:
            lo, hi = hi, lo
        return [
            EligibilityCriterion(
                criterion_type=CriterionType.AGE.value,
                statement=clause.strip(),
                operator=">=",
                value=lo,
                unit="years",
                logical_connector="AND",
                confidence=CriterionConfidence.EXPLICIT.value,
                **base,
            ),
            EligibilityCriterion(
                criterion_type=CriterionType.AGE.value,
                statement=clause.strip(),
                operator="<=",
                value=hi,
                unit="years",
                logical_connector=connector,
                confidence=CriterionConfidence.EXPLICIT.value,
                **base,
            ),
        ]
    # Single explicit age mention only when clearly numeric eligibility (not vague).
    m_years = _AGE_YEARS.search(clause)
    if m_years and re.search(r"\bage\b", clause, re.I):
        out.append(
            EligibilityCriterion(
                criterion_type=CriterionType.AGE.value,
                statement=clause.strip(),
                operator=">=",
                value=int(m_years.group(1)),
                unit="years",
                logical_connector=connector,
                confidence=CriterionConfidence.EXPLICIT.value,
                **base,
            )
        )
    return out


def _parse_income_criteria(clause: str, *, connector: Optional[str], base: Dict[str, Any]) -> List[EligibilityCriterion]:
    if _is_ambiguous(clause):
        return []
    for pattern in (_INCOME_MAX, _INCOME_BELOW):
        m = pattern.search(clause)
        if m:
            amount = _parse_indian_amount(m.group(1), m.group(2) if m.lastindex and m.lastindex >= 2 else None)
            if amount is not None:
                return [
                    EligibilityCriterion(
                        criterion_type=CriterionType.INCOME.value,
                        statement=clause.strip(),
                        operator="<=",
                        value=amount,
                        currency="INR",
                        logical_connector=connector,
                        confidence=CriterionConfidence.EXPLICIT.value,
                        **base,
                    )
                ]
    return []


def _parse_gender_criteria(clause: str, *, connector: Optional[str], base: Dict[str, Any]) -> List[EligibilityCriterion]:
    low = clause.lower()
    if re.search(r"\bmen\s+are\s+not\s+eligible\b|\bnot\s+eligible\s+for\s+men\b", low):
        return [
            EligibilityCriterion(
                criterion_type=CriterionType.GENDER.value,
                statement=clause.strip(),
                operator="!=",
                value="male",
                logical_connector=connector,
                confidence=CriterionConfidence.EXPLICIT.value,
                **base,
            )
        ]
    if re.search(
        r"\beligible\s+woman\b|\bwoman\s+head\s+of\s+(?:the\s+)?family\b|\bwomen\s+citizens\b",
        low,
    ):
        return [
            EligibilityCriterion(
                criterion_type=CriterionType.GENDER.value,
                statement=clause.strip(),
                operator="=",
                value="female",
                logical_connector=connector,
                confidence=CriterionConfidence.EXPLICIT.value,
                **base,
            )
        ]
    for pattern, gender in _GENDER_PATTERNS:
        if re.search(pattern, clause, re.I):
            return [
                EligibilityCriterion(
                    criterion_type=CriterionType.GENDER.value,
                    statement=clause.strip(),
                    operator="=",
                    value=gender,
                    logical_connector=connector,
                    confidence=CriterionConfidence.EXPLICIT.value,
                    **base,
                )
            ]
    return []


def _parse_beneficiary_criteria(clause: str, *, connector: Optional[str], base: Dict[str, Any]) -> List[EligibilityCriterion]:
    low = clause.lower()
    if re.search(r"\bwoman\s+head\s+of\s+(?:the\s+)?family\b|\beligible\s+woman\s+head\b", low):
        return [
            EligibilityCriterion(
                criterion_type=CriterionType.BENEFICIARY_STATUS.value,
                statement=clause.strip(),
                operator="=",
                value="female_head",
                logical_connector=connector,
                confidence=CriterionConfidence.EXPLICIT.value,
                **base,
            )
        ]
    if re.search(r"\bhead\s+of\s+(?:the\s+)?family\b|\bhead\s+of\s+household\b", low):
        return [
            EligibilityCriterion(
                criterion_type=CriterionType.BENEFICIARY_STATUS.value,
                statement=clause.strip(),
                operator="=",
                value="head_of_family",
                logical_connector=connector,
                confidence=CriterionConfidence.EXPLICIT.value,
                **base,
            )
        ]
    return []


def _parse_document_requirement_criteria(
    clause: str, *, connector: Optional[str], base: Dict[str, Any]
) -> List[EligibilityCriterion]:
    low = clause.lower()
    if re.search(
        r"\bmust\s+have\s+a\s+savings\s+bank\s+account\b|\bmust\s+have\s+a\s+savings\s+account\b"
        r"|\bhave\s+a\s+savings\s+bank\s+account\b",
        low,
    ):
        return [
            EligibilityCriterion(
                criterion_type=CriterionType.BENEFICIARY_STATUS.value,
                statement=clause.strip(),
                operator="=",
                value="has_savings_account",
                logical_connector=connector,
                confidence=CriterionConfidence.EXPLICIT.value,
                **base,
            )
        ]
    if re.search(r"\baadhaar[- ]linked\s+bank\s+account\b", low):
        return [
            EligibilityCriterion(
                criterion_type=CriterionType.BENEFICIARY_STATUS.value,
                statement=clause.strip(),
                operator="=",
                value="aadhaar_bank_account",
                logical_connector=connector,
                confidence=CriterionConfidence.EXPLICIT.value,
                **base,
            )
        ]
    if re.search(r"\bvalid\s+karnataka\s+ration\s+card\b|\bmust\s+hold\s+a\s+valid\s+karnataka\s+ration\s+card\b", low):
        return [
            EligibilityCriterion(
                criterion_type=CriterionType.BENEFICIARY_STATUS.value,
                statement=clause.strip(),
                operator="=",
                value="karnataka_ration_card",
                logical_connector=connector,
                confidence=CriterionConfidence.EXPLICIT.value,
                **base,
            )
        ]
    if re.search(r"\bonly\s+one\s+woman\s+per\s+family\b", low):
        return [
            EligibilityCriterion(
                criterion_type=CriterionType.SCHEME_SPECIFIC.value,
                statement=clause.strip(),
                operator="=",
                value="one_woman_per_family",
                logical_connector=connector,
                confidence=CriterionConfidence.EXPLICIT.value,
                **base,
            )
        ]
    if re.search(
        r"growing\s+notified\s+crops?\s+in\s+notified\s+areas?"
        r"|coverage\s+applies\s+only\s+for\s+crops?\s+and\s+areas?\s+notified",
        low,
    ):
        return [
            EligibilityCriterion(
                criterion_type=CriterionType.SCHEME_SPECIFIC.value,
                statement=clause.strip(),
                operator="=",
                value="notified_crop_area",
                logical_connector=connector,
                confidence=CriterionConfidence.EXPLICIT.value,
                **base,
            )
        ]
    if re.search(r"\bnotified\s+crop\b|\bnotified\s+area\b", low) and re.search(
        r"\benroll|eligible|coverage|apply|can\s+enroll\b", low
    ):
        return [
            EligibilityCriterion(
                criterion_type=CriterionType.SCHEME_SPECIFIC.value,
                statement=clause.strip(),
                operator="=",
                value="notified_crop_area",
                logical_connector=connector,
                confidence=CriterionConfidence.EXPLICIT.value,
                **base,
            )
        ]
    return []


def _parse_state_criteria(clause: str, *, connector: Optional[str], base: Dict[str, Any]) -> List[EligibilityCriterion]:
    low = clause.lower()
    for state in _STATE_NAMES:
        if state in low:
            return [
                EligibilityCriterion(
                    criterion_type=CriterionType.STATE.value,
                    statement=clause.strip(),
                    operator="=",
                    value=state.title(),
                    logical_connector=connector,
                    confidence=CriterionConfidence.EXPLICIT.value,
                    **base,
                )
            ]
    m = re.search(
        r"(?:residents? of|belong(?:ing)? to|implemented (?:for|in)|beneficiaries of)\s+([A-Za-z\s]+?)"
        r"(?:\.|,|\s+may|\s+who|\s+with|\s+and|\Z)",
        clause,
        re.I,
    )
    if m:
        val = m.group(1).strip()
        low_val = val.lower()
        if (
            len(val) >= 4
            and low_val not in ("the", "specified")
            and not _is_ambiguous(val)
            and "beneficiary group" not in low_val
        ):
            return [
                EligibilityCriterion(
                    criterion_type=CriterionType.RESIDENCE.value,
                    statement=clause.strip(),
                    operator="=",
                    value=val,
                    logical_connector=connector,
                    confidence=CriterionConfidence.EXPLICIT.value,
                    **base,
                )
            ]
    return []


def _parse_occupation_criteria(clause: str, *, connector: Optional[str], base: Dict[str, Any]) -> List[EligibilityCriterion]:
    for pattern, occ in _OCCUPATION_PATTERNS:
        if re.search(pattern, clause, re.I):
            return [
                EligibilityCriterion(
                    criterion_type=CriterionType.OCCUPATION.value,
                    statement=clause.strip(),
                    operator="=",
                    value=occ,
                    logical_connector=connector,
                    confidence=CriterionConfidence.EXPLICIT.value,
                    **base,
                )
            ]
    return []


def _parse_clause(clause: str, *, connector: Optional[str], base: Dict[str, Any]) -> List[EligibilityCriterion]:
    parsers = (
        _parse_age_criteria,
        _parse_income_criteria,
        _parse_beneficiary_criteria,
        _parse_document_requirement_criteria,
        _parse_gender_criteria,
        _parse_state_criteria,
        _parse_occupation_criteria,
    )
    found: List[EligibilityCriterion] = []
    for parser in parsers:
        found.extend(parser(clause, connector=connector, base=base))
    if found:
        return found
    if len(clause.strip()) >= 20 and not _is_ambiguous(clause):
        return [
            EligibilityCriterion(
                criterion_type=CriterionType.OTHER.value,
                statement=clause.strip(),
                logical_connector=connector,
                confidence=CriterionConfidence.UNSTRUCTURED.value,
                **base,
            )
        ]
    if _is_ambiguous(clause) and len(clause.strip()) >= 15:
        return [
            EligibilityCriterion(
                criterion_type=CriterionType.OTHER.value,
                statement=clause.strip(),
                logical_connector=connector,
                confidence=CriterionConfidence.UNSTRUCTURED.value,
                explicitly_stated=True,
                **base,
            )
        ]
    return []


def _parse_eligibility_text(
    text: str,
    *,
    scheme_name: str,
    scheme_id: str,
    source_url: str,
    document_url: str,
    document_id: Optional[str],
    evidence_ref: str,
    retrieval_timestamp: Optional[str],
) -> List[EligibilityCriterion]:
    base = {
        "scheme_name": scheme_name or None,
        "scheme_id": scheme_id or None,
        "source_url": source_url or None,
        "document_url": document_url or None,
        "document_id": document_id,
        "evidence_ref": evidence_ref,
        "retrieval_timestamp": retrieval_timestamp,
    }
    criteria: List[EligibilityCriterion] = []
    seen: Set[str] = set()
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    for sentence in sentences:
        if len(sentence.strip()) < 12:
            continue
        for clause, connector in _split_logical_clauses(sentence):
            for crit in _parse_clause(clause, connector=connector, base=base):
                key = f"{crit.criterion_type}|{crit.statement}|{crit.value}|{crit.value_max}"
                if key in seen:
                    continue
                seen.add(key)
                criteria.append(crit)
    return criteria


def _resolve_scheme_identity(
    scheme_identity: Optional[Dict[str, str]],
    evidence: Sequence[Dict[str, Any]],
) -> Dict[str, str]:
    if scheme_identity and (
        scheme_identity.get("scheme_name") or scheme_identity.get("normalized_key")
    ):
        return scheme_identity
    for doc in evidence or []:
        name = str(_doc_meta(doc, "scheme_name", "document_title") or "").strip()
        sid = str(_doc_meta(doc, "scheme_id") or "").strip()
        if name:
            try:
                from app.services.myscheme_service import normalize_scheme_key

                return {
                    "scheme_name": name,
                    "scheme_id": sid,
                    "normalized_key": normalize_scheme_key(name),
                }
            except Exception:
                return {"scheme_name": name, "scheme_id": sid, "normalized_key": name.lower()}
    return scheme_identity or {}


def _filter_evidence_by_scheme(
    evidence: Sequence[Dict[str, Any]],
    scheme_identity: Dict[str, str],
) -> Tuple[List[Dict[str, Any]], bool]:
    """Return scheme-compatible docs. rejected=True when explicit request mismatches all docs."""
    if not scheme_identity.get("normalized_key") and not scheme_identity.get("scheme_id"):
        return list(evidence or []), False
    try:
        from app.services.myscheme_service import evidence_matches_requested_scheme
    except Exception:
        return list(evidence or []), False

    kept: List[Dict[str, Any]] = []
    for doc in evidence or []:
        if evidence_matches_requested_scheme(doc, scheme_identity):
            kept.append(doc)
    if evidence and not kept:
        return [], True
    return kept, False


def extract_eligibility_criteria(
    evidence: Sequence[Dict[str, Any]],
    *,
    scheme_identity: Optional[Dict[str, str]] = None,
    query: Optional[str] = None,
    language: Optional[str] = None,
) -> EligibilityCriteriaResult:
    """Extract structured eligibility criteria from validated evidence only."""
    _ = language  # reserved — representation is language-neutral; statements preserved
    evidence = _normalize_evidence(evidence)
    if query and not scheme_identity:
        try:
            from app.services.myscheme_service import requested_scheme_identity

            scheme_identity = requested_scheme_identity(query)
        except Exception:
            scheme_identity = None

    resolved = _resolve_scheme_identity(scheme_identity, evidence)
    scheme_name = (resolved.get("scheme_name") or "").strip()
    scheme_id = (resolved.get("scheme_id") or "").strip()

    if not evidence:
        return EligibilityCriteriaResult(
            scheme_name=scheme_name or None,
            scheme_id=scheme_id or None,
            extraction_status="no_evidence",
            makes_eligibility_decision=False,
        )

    filtered, rejected = _filter_evidence_by_scheme(evidence, resolved)
    if rejected:
        return EligibilityCriteriaResult(
            scheme_name=scheme_name or None,
            scheme_id=scheme_id or None,
            rejected=True,
            rejection_reason="scheme_identity_mismatch",
            extraction_status="scheme_mismatch",
            makes_eligibility_decision=False,
        )

    all_criteria: List[EligibilityCriterion] = []
    unstructured: List[str] = []
    global_seen: Set[str] = set()

    for idx, doc in enumerate(filtered, start=1):
        content = str(doc.get("content") or doc.get("text") or "")
        source_url, document_url = _doc_source_urls(doc)
        doc_scheme = str(_doc_meta(doc, "scheme_name", "document_title") or scheme_name)
        doc_sid = str(_doc_meta(doc, "scheme_id") or scheme_id)
        doc_id = _doc_meta(doc, "document_id", "id")
        ts = _doc_meta(doc, "retrieval_timestamp", "fetched_at", "created_at")
        evidence_ref = f"evidence_{idx}"

        for blob in _extract_eligibility_blobs(content):
            parsed = _parse_eligibility_text(
                blob,
                scheme_name=doc_scheme,
                scheme_id=doc_sid,
                source_url=source_url,
                document_url=document_url,
                document_id=str(doc_id) if doc_id is not None else None,
                evidence_ref=evidence_ref,
                retrieval_timestamp=str(ts) if ts is not None else None,
            )
            for crit in parsed:
                key = f"{crit.criterion_type}|{crit.statement}|{crit.value}|{crit.value_max}"
                if key in global_seen:
                    continue
                global_seen.add(key)
                all_criteria.append(crit)
                if crit.confidence == CriterionConfidence.UNSTRUCTURED.value:
                    unstructured.append(crit.statement)

    if not all_criteria:
        return EligibilityCriteriaResult(
            scheme_name=scheme_name or doc_scheme if filtered else scheme_name or None,
            scheme_id=scheme_id or None,
            extraction_status="no_eligibility_text",
            makes_eligibility_decision=False,
        )

    return EligibilityCriteriaResult(
        scheme_name=scheme_name or (all_criteria[0].scheme_name if all_criteria else None),
        scheme_id=scheme_id or (all_criteria[0].scheme_id if all_criteria else None),
        criteria=all_criteria,
        unstructured_statements=unstructured,
        extraction_status="ok",
        makes_eligibility_decision=False,
    )


def enrich_assistance_fields_from_criteria(
    criteria: EligibilityCriteriaResult,
) -> Tuple[List[str], List[str], List[str]]:
    """Map extracted criteria to required/known/missing information (6B-1 foundation)."""
    required = criteria.required_information_types()
    return required, [], list(required)
