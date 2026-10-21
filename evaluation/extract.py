"""Extract structured scheme truth only from seed document text."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple

from evaluation.paths import EXCERPTS_PATH, REPO_ROOT, SCHEMES_PATH, SEED_DOCUMENTS

_SECTION_ALIASES = {
    "purpose": "purpose",
    "eligibility": "eligibility",
    "eligibility (public scheme description)": "eligibility",
    "eligibility (summary)": "eligibility",
    "who is eligible (summary)": "eligibility",
    "benefits": "benefits",
    "benefits (summary)": "benefits",
    "benefits / cover amount": "benefits",
    "monthly assistance amount": "benefits",
    "premium": "limits",
    "documents / information commonly required at enrollment": "documents",
    "documents commonly referenced": "documents",
    "documents commonly required": "documents",
    "how to use / apply": "procedure",
    "how to apply": "procedure",
    "enrolment / claim": "procedure",
    "important": "limits",
    "source / portals": "sources",
    "source note": "sources",
}

_LABEL_ALIASES = {
    "scheme name": "scheme_name",
    "scope": "scope",
    "ministry": "ministry",
    "ministry / department": "ministry",
    "department": "ministry",
    "state": "state",
    "level": "scope",
    "category": "category",
    "official portals": "portals",
    "official citizen portals": "portals",
}

_ELIGIBILITY_RULES: Dict[str, List[Dict[str, Any]]] = {
    "pmfby": [
        {"id": "farmer_notified", "all": ["is_farmer", "crop_notified", "area_notified"]},
        {"id": "loanee_ok", "note": "loanee and non-loanee farmers may enroll when other conditions hold"},
    ],
    "shakti": [
        {"id": "woman_karnataka", "all": ["is_woman", "state_karnataka"]},
        {"id": "men_excluded", "exclude_if": ["is_man"]},
    ],
    "anna-bhagya": [
        {"id": "ration_card", "all": ["has_karnataka_ration_card"]},
    ],
    "pmsby": [
        {"id": "age_bank", "all": ["age_in_common_band", "has_savings_bank", "auto_debit_consent"]},
    ],
    "gruha-lakshmi": [
        {
            "id": "woman_head_ka",
            "all": ["is_woman", "state_karnataka", "is_head_of_family", "aadhaar_linked_bank"],
            "exclude_if": ["another_woman_already_beneficiary"],
        }
    ],
}


def _norm_header(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip().rstrip(":").lower())


def _excerpt(lines: List[str], start: int, end: int) -> str:
    return "\n".join(lines[start - 1 : end]).strip()


def extract_facts_from_document(scheme_id: str, document_id: str, rel_path: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    path = REPO_ROOT / rel_path
    lines = path.read_text(encoding="utf-8").splitlines()
    facts: List[Dict[str, Any]] = []
    urls: List[str] = []
    current_field = "overview"
    section_start = 1
    bucket: List[str] = []

    def flush(end_line: int) -> None:
        nonlocal bucket, section_start
        text = "\n".join(bucket).strip()
        if text:
            facts.append(
                {
                    "id": f"{document_id}-{len(facts)+1:03d}",
                    "scheme_id": scheme_id,
                    "document_id": document_id,
                    "document_path": rel_path.replace("\\", "/"),
                    "field": current_field,
                    "section": current_field,
                    "kind": "paragraph",
                    "line_start": section_start,
                    "line_end": end_line,
                    "excerpt": text,
                    "source_url": None,
                }
            )
        bucket = []

    for idx, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        header = _norm_header(stripped)
        if header in _SECTION_ALIASES:
            flush(idx - 1)
            current_field = _SECTION_ALIASES[header]
            section_start = idx
            continue
        if ":" in stripped and not stripped.startswith("-"):
            label, value = stripped.split(":", 1)
            mapped = _LABEL_ALIASES.get(_norm_header(label))
            if mapped and value.strip():
                facts.append(
                    {
                        "id": f"{document_id}-{len(facts)+1:03d}",
                        "scheme_id": scheme_id,
                        "document_id": document_id,
                        "document_path": rel_path.replace("\\", "/"),
                        "field": mapped,
                        "section": mapped,
                        "kind": "label",
                        "line_start": idx,
                        "line_end": idx,
                        "excerpt": f"{label.strip()}: {value.strip()}",
                        "source_url": None,
                    }
                )
                if mapped == "portals":
                    urls.extend(re.findall(r"https?://[^\s]+", value))
                continue
        if stripped.startswith("- "):
            facts.append(
                {
                    "id": f"{document_id}-{len(facts)+1:03d}",
                    "scheme_id": scheme_id,
                    "document_id": document_id,
                    "document_path": rel_path.replace("\\", "/"),
                    "field": current_field,
                    "section": current_field,
                    "kind": "bullet",
                    "line_start": idx,
                    "line_end": idx,
                    "excerpt": stripped[2:].strip(),
                    "source_url": None,
                }
            )
            continue
        if facts and facts[-1].get("kind") == "bullet" and facts[-1]["field"] == current_field:
            facts[-1]["excerpt"] = f"{facts[-1]['excerpt']} {stripped}"
            facts[-1]["line_end"] = idx
            continue
        if current_field in ("purpose", "benefits", "eligibility", "limits", "procedure", "documents", "overview", "sources"):
            bucket.append(stripped)
    flush(len(lines))

    record = {
        "scheme_id": scheme_id,
        "document_id": document_id,
        "document_path": rel_path.replace("\\", "/"),
        "source_urls": [u.rstrip(".,") for u in urls],
        "fields": {},
        "eligibility_rules": _ELIGIBILITY_RULES.get(scheme_id, []),
    }
    for fact in facts:
        record["fields"].setdefault(fact["field"], []).append(fact["excerpt"])
        if not record.get("scheme_name") and fact["field"] == "scheme_name":
            record["scheme_name"] = fact["excerpt"]
    return facts, record


def build_structured_truth() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    excerpts: List[Dict[str, Any]] = []
    schemes: List[Dict[str, Any]] = []
    for spec in SEED_DOCUMENTS:
        facts, record = extract_facts_from_document(spec["scheme_id"], spec["id"], spec["path"])
        record.setdefault("scheme_name", spec["scheme_name"])
        record["purpose"] = record["fields"].get("purpose", [])
        record["benefits"] = record["fields"].get("benefits", [])
        record["eligibility_conditions"] = record["fields"].get("eligibility", [])
        record["exclusions"] = [
            text for text in record["fields"].get("eligibility", []) if re.search(r"\bnot eligible\b|\bmen are not\b", text, re.I)
        ]
        record["required_documents"] = record["fields"].get("documents", [])
        record["application_procedure"] = record["fields"].get("procedure", [])
        record["important_limits"] = record["fields"].get("limits", [])
        record["evidence_references"] = [f["id"] for f in facts]
        schemes.append(record)
        excerpts.extend(facts)

    EXCERPTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMES_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXCERPTS_PATH.write_text(json.dumps({"excerpts": excerpts}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    SCHEMES_PATH.write_text(json.dumps({"schemes": schemes}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return schemes, excerpts


def excerpt_index(excerpts: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {item["id"]: item for item in excerpts}


def evidence_from_ids(excerpts_by_id: Dict[str, Dict[str, Any]], ids: List[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for eid in ids:
        item = excerpts_by_id[eid]
        out.append(
            {
                "document_id": item["document_id"],
                "document_path": item["document_path"],
                "source_url": item.get("source_url"),
                "section": item.get("section"),
                "line_start": item.get("line_start"),
                "line_end": item.get("line_end"),
                "excerpt": item["excerpt"],
                "excerpt_id": item["id"],
            }
        )
    return out
