from __future__ import annotations

import json
import urllib.parse
from typing import Any, Dict, List

from app.services.myscheme_service import build_myscheme_scheme_url
from app.services.myscheme_karnataka_crawler.config import KARNATAKA_FILTER, PAGE_SIZE
from app.services.myscheme_karnataka_crawler.http_client import RespectfulHttpClient


def _parse_search_item(item: Dict[str, Any]) -> Dict[str, Any]:
    fields = item.get("fields") or {}
    slug = (fields.get("slug") or "").strip()
    scheme_name = (fields.get("schemeName") or fields.get("schemeShortTitle") or slug).strip()
    ministry = None
    nodal = fields.get("nodalDepartmentName") or fields.get("nodalMinistryName")
    if isinstance(nodal, dict):
        ministry = nodal.get("label")
    elif isinstance(nodal, str):
        ministry = nodal
    return {
        "scheme_id": slug,
        "scheme_name": scheme_name,
        "scheme_url": build_myscheme_scheme_url(slug) if slug else "",
        "slug": slug,
        "state": "Karnataka",
        "ministry": ministry,
        "source_url": build_myscheme_scheme_url(slug) if slug else "",
        "level": fields.get("level"),
        "status": "PENDING",
        "pdf_status": None,
        "candidate_pdfs": [],
        "canonical_pdf_url": None,
        "error": None,
    }


def discover_karnataka_schemes(client: RespectfulHttpClient) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Paginate myScheme search v6 with beneficiaryState=Karnataka filter."""
    filters = list(KARNATAKA_FILTER)
    q = urllib.parse.quote(json.dumps(filters, separators=(",", ":")))
    from_ = 0
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    pages_fetched = 0
    duplicate_ids_skipped = 0
    api_total_reported: int | None = None
    non_karnataka_rows = 0

    while True:
        path = (
            f"/search/v6/schemes?lang=en&q={q}&keyword=&sort=&from={from_}&size={PAGE_SIZE}"
        )
        url = f"https://api.myscheme.gov.in{path}"
        raw, _, _ = client.get_bytes(url, myscheme_api=True)
        data = json.loads(raw.decode("utf-8"))
        hits = (data.get("data") or {}).get("hits") or {}
        items = hits.get("items") or []
        if api_total_reported is None and hits.get("total") is not None:
            try:
                api_total_reported = int(hits.get("total"))
            except (TypeError, ValueError):
                api_total_reported = None
        if not items:
            break
        pages_fetched += 1
        for item in items:
            fields = item.get("fields") or {}
            states = fields.get("beneficiaryState") or []
            if states and "Karnataka" not in states:
                non_karnataka_rows += 1
            rec = _parse_search_item(item)
            sid = rec.get("scheme_id")
            if not sid:
                continue
            if sid in seen:
                duplicate_ids_skipped += 1
                continue
            seen.add(sid)
            out.append(rec)
        from_ += len(items)
        if len(items) < PAGE_SIZE:
            break
    meta = {
        "pagination_pages_fetched": pages_fetched,
        "duplicate_scheme_ids_skipped": duplicate_ids_skipped,
        "api_total_reported": api_total_reported,
        "non_karnataka_rows_seen": non_karnataka_rows,
    }
    return out, meta
