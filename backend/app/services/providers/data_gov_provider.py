"""Thin data.gov.in provider — dynamic dataset discovery via portal search.

Delegates acquisition, PDF handling, ingestion, identity, and sufficiency probing
to existing live_gov_retrieval_service mechanisms. Not every dataset is a scheme;
relevance and question-aware filtering apply before ingest.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus, urljoin, urlparse

from app.core.config import settings
from app.services.providers.base import (
    ExtractedEvidence,
    GovernmentInformationProvider,
    IdentityCheckResult,
    ProviderContext,
    ProviderPhaseStatus,
    ProviderRunResult,
    SchemeCandidate,
    extracted_evidence_is_usable,
    log_provider_event,
    merge_provider_ingested,
)
from app.services.providers.myscheme_provider import (
    _candidate_to_dict,
    _dict_to_candidate,
    _map_outcome,
)

_DATASET_PATH_RE = re.compile(r"/catalog/dataset/([a-zA-Z0-9\-_]+)", re.I)
_RESOURCE_PATH_RE = re.compile(r"/resource/([a-f0-9\-]{36})", re.I)


def is_data_gov_url(url: str) -> bool:
    host = (urlparse(url or "").hostname or "").lower()
    return host == "data.gov.in" or host.endswith(".data.gov.in")


def _normalize_search_terms(query: str) -> str:
    from app.services.live_gov_retrieval_service import expand_search_query

    q = (expand_search_query(query) or query or "").strip()
    q = re.sub(
        r"^(what is|tell me about|details about|information about|can i get details about)\s+",
        "",
        q,
        flags=re.I,
    ).strip()
    return q[:120]


def build_data_gov_seeds_for_query(
    query: str,
    *,
    verify_fn,
    already: Optional[List[str]] = None,
    limit: int = 4,
) -> List[Dict[str, Any]]:
    """Dynamic data.gov.in seeds: trusted registry base + catalog search."""
    from app.services.gov_source_registry import load_registry

    seen = set(already or [])
    seeds: List[Dict[str, Any]] = []
    search_q = _normalize_search_terms(query)

    def _add(seed: Dict[str, Any]) -> bool:
        url = seed.get("url") or ""
        if not url or url in seen or not verify_fn(url) or not is_data_gov_url(url):
            return False
        seen.add(url)
        seeds.append(seed)
        return True

    registry = load_registry()
    for src in registry.get("sources") or []:
        if (src.get("domain") or "").lower() != "data.gov.in":
            continue
        if not src.get("enabled", True):
            continue
        for url in src.get("base_urls") or []:
            if _add(
                {
                    "url": url,
                    "scheme_name": src.get("name") or "data.gov.in",
                    "link_text": src.get("name") or "Open Government Data",
                    "stage": "data_gov_registry",
                    "source": "data_gov",
                    "source_id": src.get("id"),
                }
            ) and len(seeds) >= limit:
                return seeds[:limit]

    if search_q and len(seeds) < limit:
        search_url = f"https://data.gov.in/catalog/datasets?search={quote_plus(search_q)}"
        _add(
            {
                "url": search_url,
                "scheme_name": "data.gov.in catalog search",
                "link_text": search_q,
                "kind": "search",
                "stage": "data_gov_search",
                "source": "data_gov",
            }
        )

    # CKAN-style search when the portal exposes JSON (fixtures / future API)
    if search_q and len(seeds) < limit:
        api_url = (
            f"https://data.gov.in/api/3/action/package_search"
            f"?q={quote_plus(search_q)}&rows={min(8, limit)}"
        )
        _add(
            {
                "url": api_url,
                "scheme_name": "data.gov.in dataset search",
                "link_text": search_q,
                "kind": "public_api",
                "stage": "data_gov_api_search",
                "source": "data_gov",
            }
        )

    return seeds[:limit]


def _decode_content(content: Any) -> str:
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="ignore")
    return str(content or "")


def _dataset_metadata_blob(record: Dict[str, Any]) -> str:
    parts = [
        record.get("title") or record.get("scheme_name") or "",
        record.get("notes") or record.get("description") or "",
        record.get("organization") or record.get("ministry") or "",
        record.get("department") or "",
        record.get("state") or "",
        record.get("category") or "",
        " ".join(record.get("tags") or []),
        record.get("resource_text") or "",
        record.get("fields_text") or "",
    ]
    return " ".join(p for p in parts if p).strip()


def _intent_markers_for_query(query: str) -> Tuple[str, ...]:
    from app.services.myscheme_service import _INTENT_MARKERS, query_citizen_intent

    intent = query_citizen_intent(query)
    if intent == "complete":
        merged: List[str] = []
        for markers in _INTENT_MARKERS.values():
            merged.extend(markers)
        return tuple(merged)
    return _INTENT_MARKERS.get(intent, _INTENT_MARKERS.get("overview", ()))


def _is_stats_only_for_intent(blob: str, query: str) -> bool:
    """Reject statistics-only datasets when citizen asked for scheme guidance."""
    from app.services.myscheme_service import query_citizen_intent

    intent = query_citizen_intent(query)
    if intent in ("benefits", "complete", "overview"):
        return False
    lower = (blob or "").lower()
    stats_markers = (
        "statistics",
        "statistical",
        "beneficiary count",
        "number of beneficiaries",
        "year-wise",
        "state-wise",
        "district-wise",
        "month-wise",
        "total beneficiaries",
    )
    # Substantive section markers only — generic words like "beneficiary" appear in stats titles.
    substantive_section = (
        "eligibility",
        "eligible",
        "who can",
        "criteria",
        "how to apply",
        "application process",
        "documents required",
        "required documents",
        "section:\neligibility",
        "enroll",
        "qualify",
    )
    has_section = any(m in lower for m in substantive_section)
    stats_heavy = sum(1 for m in stats_markers if m in lower) >= 2
    return stats_heavy and not has_section


def dataset_relevant_to_query(record: Dict[str, Any], query: str) -> Tuple[bool, str]:
    """Determine whether a dataset actually answers the citizen question."""
    from app.services.live_gov_retrieval_service import content_relevant_to_query
    from app.services.myscheme_service import (
        evidence_matches_requested_scheme,
        requested_scheme_identity,
        required_sections_for_query,
    )

    blob = _dataset_metadata_blob(record)
    if len(blob.strip()) < 80:
        return False, "empty_metadata"

    requested = requested_scheme_identity(query)
    if requested:
        row = {
            "scheme_name": record.get("title") or record.get("scheme_name"),
            "scheme_id": record.get("scheme_id"),
            "url": record.get("url") or "",
            "content": blob,
            "metadata": record.get("metadata") or {},
        }
        if not evidence_matches_requested_scheme(row, requested):
            return False, "SCHEME_IDENTITY_MISMATCH"

    if _is_stats_only_for_intent(blob, query):
        return False, "stats_only_not_question_relevant"

    if not content_relevant_to_query(blob, query):
        return False, "query_overlap_insufficient"

    lower = blob.lower()
    required = required_sections_for_query(query)
    section_hits = 0
    for section in required:
        markers = _intent_markers_for_query(query) if section == required[0] else ()
        if section == "eligibility" and any(
            m in lower for m in ("eligibility", "eligible", "criteria", "who can")
        ):
            section_hits += 1
        elif section == "benefits" and any(
            m in lower for m in ("benefit", "subsidy", "assistance", "amount")
        ):
            section_hits += 1
        elif section == "application" and any(
            m in lower for m in ("apply", "application", "registration", "procedure")
        ):
            section_hits += 1
        elif section == "documents" and any(
            m in lower for m in ("document", "documents required", "duly filled")
        ):
            section_hits += 1
        elif section == "details" and len(blob) >= 200:
            section_hits += 1
        elif markers and any(m in lower for m in markers):
            section_hits += 1

    if len(required) == 1 and section_hits == 0:
        return False, "missing_required_information"
    if len(required) > 1 and section_hits == 0 and len(blob) < 250:
        return False, "missing_required_information"

    return True, "relevant"


def package_data_gov_evidence(record: Dict[str, Any]) -> str:
    """Package structured dataset metadata into ingestible HTML evidence."""
    meta = record.get("metadata") or {}
    title = record.get("title") or record.get("scheme_name") or "Government dataset"
    lines = [
        f"<html><body><h1>{title}</h1>",
        f"<p><strong>Source:</strong> Open Government Data (data.gov.in)</p>",
    ]
    if record.get("url"):
        lines.append(f"<p><strong>Dataset URL:</strong> {record['url']}</p>")
    for key in ("organization", "ministry", "department", "state", "category"):
        val = record.get(key) or meta.get(key)
        if val:
            lines.append(f"<p><strong>{key.title()}:</strong> {val}</p>")
    if record.get("tags"):
        lines.append(f"<p><strong>Tags:</strong> {', '.join(record['tags'][:12])}</p>")
    if record.get("notes") or record.get("description"):
        lines.append(f"<h2>Overview</h2><p>{record.get('notes') or record.get('description')}</p>")
    if record.get("fields_text"):
        lines.append(f"<h2>Dataset fields</h2><pre>{record['fields_text']}</pre>")
    if record.get("resource_text"):
        lines.append(f"<h2>Structured records</h2><pre>{record['resource_text']}</pre>")
    for section, heading in (
        ("eligibility_text", "Eligibility"),
        ("benefits_text", "Benefits"),
        ("application_text", "Application procedure"),
        ("documents_text", "Documents required"),
    ):
        if record.get(section):
            lines.append(f"<h2>{heading}</h2><p>{record[section]}</p>")
    lines.append("</body></html>")
    return "".join(lines)


def _extract_dataset_links_from_html(
    html: str,
    base_url: str,
    *,
    verify_fn,
) -> List[Dict[str, Any]]:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    soup = BeautifulSoup(html or "", "html.parser")
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        absolute = urljoin(base_url, href).split("#")[0]
        if absolute in seen:
            continue
        if not is_data_gov_url(absolute):
            continue
        if not (_DATASET_PATH_RE.search(absolute) or _RESOURCE_PATH_RE.search(absolute)):
            continue
        if not verify_fn(absolute):
            continue
        seen.add(absolute)
        title = a.get_text(" ", strip=True) or ""
        out.append(
            {
                "url": absolute,
                "title": title,
                "link_text": title,
                "kind": "dataset_page",
                "source": "data_gov",
            }
        )
    return out


def _record_from_ckan_dataset(row: Dict[str, Any], *, base_url: str) -> Dict[str, Any]:
    org = row.get("organization") or {}
    org_title = org.get("title") if isinstance(org, dict) else str(org or "")
    tags = [
        (t.get("name") if isinstance(t, dict) else str(t))
        for t in (row.get("tags") or [])
    ]
    resources = row.get("resources") or []
    resource_text = ""
    resource_urls: List[str] = []
    for res in resources[:3]:
        if not isinstance(res, dict):
            continue
        rurl = str(res.get("url") or "")
        if rurl:
            resource_urls.append(rurl)
        desc = res.get("description") or res.get("name") or ""
        fmt = res.get("format") or ""
        if desc:
            resource_text += f"{fmt}: {desc}\n"
    slug = row.get("name") or ""
    url = f"https://data.gov.in/catalog/dataset/{slug}" if slug else base_url
    notes = row.get("notes") or row.get("title") or ""
    record = {
        "url": url,
        "title": row.get("title") or slug,
        "scheme_name": row.get("title") or slug,
        "notes": notes,
        "description": notes,
        "organization": org_title,
        "ministry": org_title,
        "tags": [t for t in tags if t],
        "resource_text": resource_text.strip(),
        "resource_urls": resource_urls,
        "metadata": {
            "dataset_id": slug,
            "organization": org_title,
            "tags": tags,
            "source": "data_gov",
        },
    }
    return record


def _candidates_from_ckan_json(
    content: bytes,
    search_q: str,
    *,
    verify_fn,
) -> List[Dict[str, Any]]:
    try:
        payload = json.loads(_decode_content(content))
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(payload, dict) or not payload.get("success"):
        return []
    result = payload.get("result") or {}
    rows = result.get("results") or []
    candidates: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        record = _record_from_ckan_dataset(row, base_url="https://data.gov.in/")
        ok, reason = dataset_relevant_to_query(record, search_q)
        if not ok:
            log_provider_event(
                "data_gov",
                "DATAGOV_CANDIDATE_REJECTED",
                reason=reason,
                url=(record.get("url") or "")[:160],
            )
            continue
        log_provider_event(
            "data_gov",
            "DATAGOV_RELEVANCE_PASS",
            url=(record.get("url") or "")[:160],
        )
        packed = package_data_gov_evidence(record)
        candidates.append(
            {
                "url": record["url"],
                "kind": "dataset",
                "content": packed.encode("utf-8"),
                "scheme_name": record.get("title"),
                "link_text": record.get("title") or "",
                "source": "data_gov",
                "metadata": record.get("metadata") or {},
            }
        )
    return candidates


def _parse_dataset_html_page(html: str, url: str) -> Dict[str, Any]:
    """Best-effort parse of a data.gov.in dataset/resource page."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        soup = None
    title = ""
    notes = ""
    org = ""
    tags: List[str] = []
    fields_text = ""
    if soup is not None:
        soup = BeautifulSoup(html or "", "html.parser")
        h1 = soup.find("h1")
        title = h1.get_text(" ", strip=True) if h1 else ""
        for meta_label in ("Description", "Notes", "About"):
            node = soup.find(string=re.compile(meta_label, re.I))
            if node and node.parent:
                notes = node.parent.get_text(" ", strip=True)
                break
        if not notes:
            para = soup.find("p")
            notes = para.get_text(" ", strip=True) if para else ""
        org_node = soup.find(string=re.compile(r"ministry|department|organization", re.I))
        if org_node and org_node.parent:
            org = org_node.parent.get_text(" ", strip=True)
        for tag in soup.select('[class*="tag"], .badge, .label'):
            t = tag.get_text(" ", strip=True)
            if t and len(t) < 60:
                tags.append(t)
        table = soup.find("table")
        if table:
            fields_text = table.get_text("\n", strip=True)[:4000]
    slug_m = _DATASET_PATH_RE.search(url)
    return {
        "url": url,
        "title": title or (slug_m.group(1).replace("-", " ") if slug_m else "Dataset"),
        "scheme_name": title,
        "notes": notes,
        "description": notes,
        "organization": org,
        "ministry": org,
        "tags": tags[:12],
        "fields_text": fields_text,
        "metadata": {"source": "data_gov", "dataset_url": url},
    }


def _looks_like_search_shell(url: str, content: Optional[bytes]) -> bool:
    if not content:
        return False
    text = _decode_content(content)
    blob = text.strip()
    if len(blob) < 80:
        return True
    lower = blob.lower()
    url_l = (url or "").lower()
    if blob.startswith("http") and len(blob.split()) <= 3:
        return True
    if "catalog/datasets" in url_l and "search=" in url_l:
        markers = (
            "search results",
            "no datasets found",
            "enter search",
            "refine your search",
        )
        if any(m in lower for m in markers) and len(blob) < 3000:
            if "/catalog/dataset/" not in lower:
                return True
    return False


def _filter_usable_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for cand in candidates or []:
        url = cand.get("url") or ""
        if not is_data_gov_url(url) and cand.get("source") != "data_gov":
            continue
        content = cand.get("content")
        if content is not None and _looks_like_search_shell(url, content):
            continue
        if content is not None and len(_decode_content(content).strip()) < 80:
            continue
        out.append(cand)
    return out


def discover_data_gov_candidates(
    service: Any,
    search_q: str,
    *,
    seeds: List[Dict[str, Any]],
    overall_deadline: float,
    live_request_id: str,
    verify_fn,
) -> List[Dict[str, Any]]:
    """Discover relevant data.gov.in dataset candidates for ingest."""
    from app.services.live_gov_retrieval_service import select_best_candidates

    if not service or not seeds:
        return []

    service._live_request_id = live_request_id  # noqa: SLF001
    service._live_query = search_q  # noqa: SLF001
    raw = service.discover_candidate_pages(
        search_q,
        overall_deadline=overall_deadline,
        seeds=seeds,
        max_pages=min(4, int(getattr(settings, "LIVE_GOV_MAX_PAGES", 6))),
    )

    expanded: List[Dict[str, Any]] = []
    for item in raw or []:
        url = item.get("url") or ""
        content = item.get("content")
        kind = (item.get("kind") or "").lower()

        if kind == "public_api" and content:
            expanded.extend(
                _candidates_from_ckan_json(content, search_q, verify_fn=verify_fn)
            )
            continue

        if not content:
            continue

        html = _decode_content(content)
        if _DATASET_PATH_RE.search(url) or _RESOURCE_PATH_RE.search(url):
            record = _parse_dataset_html_page(html, url)
            ok, reason = dataset_relevant_to_query(record, search_q)
            if ok:
                log_provider_event(
                    "data_gov",
                    "DATAGOV_RELEVANCE_PASS",
                    live_request_id=live_request_id,
                    url=url[:160],
                )
                packed = package_data_gov_evidence(record)
                expanded.append(
                    {
                        **item,
                        "url": url,
                        "kind": "dataset",
                        "content": packed.encode("utf-8"),
                        "scheme_name": record.get("title"),
                        "metadata": record.get("metadata") or {},
                    }
                )
            else:
                log_provider_event(
                    "data_gov",
                    "DATAGOV_RELEVANCE_FAIL",
                    live_request_id=live_request_id,
                    url=url[:160],
                    reason=reason,
                )
            continue

        for link in _extract_dataset_links_from_html(html, url, verify_fn=verify_fn):
            log_provider_event(
                "data_gov",
                "DATAGOV_CANDIDATE_FOUND",
                live_request_id=live_request_id,
                url=(link.get("url") or "")[:160],
            )
            expanded.append(
                {
                    **link,
                    "kind": "dataset_page",
                    "source": "data_gov",
                }
            )

    india_filtered = _filter_usable_candidates(expanded)
    ranked = select_best_candidates(
        india_filtered,
        search_q,
        limit=int(settings.LIVE_GOV_MAX_CANDIDATES),
    )
    return ranked


class DataGovProvider(GovernmentInformationProvider):
    """Adapter for data.gov.in Open Government Data datasets."""

    name = "data_gov"
    priority = 175

    def supports(self, query: str, *, context: ProviderContext) -> bool:
        from app.services.live_gov_retrieval_service import looks_like_gov_scheme_query

        if not getattr(settings, "DATAGOV_PROVIDER_ENABLED", True):
            return False
        q = (context.search_query or query or "").strip()
        return looks_like_gov_scheme_query(q)

    def resolve_identity(
        self,
        candidate: SchemeCandidate,
        query: str,
        *,
        context: ProviderContext,
        service: Any = None,
    ) -> IdentityCheckResult:
        from app.services.myscheme_service import request_accepts_candidate

        row = _candidate_to_dict(candidate)
        accepted = request_accepts_candidate(query, row)
        event = "DATAGOV_IDENTITY_PASS" if accepted else "DATAGOV_IDENTITY_FAIL"
        log_provider_event(
            self.name,
            event,
            live_request_id=context.live_request_id,
            url=(candidate.url or "")[:160],
        )
        if not accepted:
            log_provider_event(
                self.name,
                "DATAGOV_CANDIDATE_REJECTED",
                live_request_id=context.live_request_id,
                reason="SCHEME_IDENTITY_MISMATCH",
            )
        return IdentityCheckResult(
            accepted=accepted,
            reason=None if accepted else "SCHEME_IDENTITY_MISMATCH",
            requested_scheme=(context.search_query or query or "")[:120],
            candidate_scheme=candidate.scheme_name or candidate.scheme_id,
        )

    def discover(
        self,
        query: str,
        *,
        context: ProviderContext,
        service: Any = None,
    ) -> List[SchemeCandidate]:
        from app.services.live_gov_retrieval_service import expand_search_query, verify_source

        search_q = (context.search_query or expand_search_query(query)).strip()
        log_provider_event(
            self.name,
            "DATAGOV_SEARCH",
            live_request_id=context.live_request_id,
            query=search_q[:160],
        )
        seeds = build_data_gov_seeds_for_query(
            search_q,
            verify_fn=verify_source,
            already=context.tried_urls,
            limit=int(settings.LIVE_GOV_MAX_SOURCES),
        )
        if not service or not seeds:
            return [_dict_to_candidate(s) for s in seeds]

        ranked = discover_data_gov_candidates(
            service,
            search_q,
            seeds=seeds,
            overall_deadline=context.overall_deadline,
            live_request_id=context.live_request_id,
            verify_fn=verify_source,
        )
        return [_dict_to_candidate(c) for c in ranked]

    def extract(
        self,
        candidate: SchemeCandidate,
        *,
        query: str,
        context: ProviderContext,
        service: Any = None,
    ) -> ExtractedEvidence:
        row = _candidate_to_dict(candidate)
        content = row.get("content")
        text = _decode_content(content)
        meta = row.get("metadata") or {}
        record = {
            "url": row.get("url") or "",
            "title": row.get("scheme_name") or meta.get("title"),
            "notes": text,
            "metadata": meta,
        }
        ok, reason = dataset_relevant_to_query(record, query)
        if not ok:
            evidence = ExtractedEvidence(
                ok=False,
                content=text,
                source_url=row.get("url") or "",
                reason=reason,
            )
            return evidence
        if not text.strip() or _looks_like_search_shell(row.get("url") or "", content):
            evidence = ExtractedEvidence(
                ok=False,
                content=text,
                source_url=row.get("url") or "",
                reason="search_shell_or_empty",
            )
            return evidence
        evidence = ExtractedEvidence(
            ok=True,
            content=text,
            source_url=row.get("url") or "",
            scheme_name=row.get("scheme_name"),
            text_chars=len(text.strip()),
        )
        if not extracted_evidence_is_usable(evidence):
            evidence.ok = False
            evidence.reason = "insufficient_content"
        elif evidence.ok:
            log_provider_event(
                self.name,
                "DATAGOV_CONTENT_EXTRACTED",
                live_request_id=context.live_request_id,
                url=(evidence.source_url or "")[:160],
                chars=evidence.text_chars,
            )
        return evidence

    def discover_documents(
        self,
        candidate: SchemeCandidate,
        *,
        context: ProviderContext,
        service: Any = None,
    ) -> List[str]:
        if not service or not candidate.url:
            return []
        meta = candidate.meta or {}
        resource_urls = list(meta.get("resource_urls") or [])
        html = _decode_content(candidate.content)
        if html:
            for item in service.discover_pdf_links(candidate.url, html):
                url = str(item.get("url") or "")
                if url:
                    resource_urls.append(url)
                    log_provider_event(
                        self.name,
                        "DATAGOV_DOCUMENT_FOUND",
                        live_request_id=context.live_request_id,
                        url=url[:200],
                    )
        verified: List[str] = []
        from app.services.live_gov_retrieval_service import verify_source

        for url in resource_urls:
            if verify_source(url) and url not in verified:
                verified.append(url)
        return verified

    def run(self, context: ProviderContext, *, service: Any = None) -> ProviderRunResult:
        from app.services.live_gov_retrieval_service import expand_search_query, verify_source

        log_provider_event(
            self.name,
            "DATAGOV_PROVIDER_START",
            live_request_id=context.live_request_id,
        )
        context.extra["data_gov_attempted"] = True

        if service is None:
            return ProviderRunResult(
                provider=self.name,
                status=ProviderPhaseStatus.ERROR,
                failure_codes=["no_service"],
                meta={"outcome": "failed", "reason": "no_service"},
            )

        if time.time() >= context.overall_deadline:
            return ProviderRunResult(
                provider=self.name,
                status=ProviderPhaseStatus.INSUFFICIENT,
                failure_codes=["timeout"],
                meta={"outcome": "failed", "reason": "deadline_before_start"},
            )

        search_q = (context.search_query or expand_search_query(context.query)).strip()
        log_provider_event(
            self.name,
            "DATAGOV_SEARCH",
            live_request_id=context.live_request_id,
            query=search_q[:160],
        )

        ingested: List[Dict[str, Any]] = list(context.ingested or [])
        rejected_urls: List[str] = []
        failure_codes: List[str] = list(context.failure_codes or [])
        pdfs_used = int(context.extra.get("pdfs_used") or 0)
        max_pdfs = int(settings.LIVE_GOV_MAX_PDFS)
        per_source = float(context.per_source_timeout or settings.LIVE_GOV_TIMEOUT_SECONDS)

        seeds = build_data_gov_seeds_for_query(
            search_q,
            verify_fn=verify_source,
            already=context.tried_urls,
            limit=int(settings.LIVE_GOV_MAX_SOURCES),
        )
        if not seeds:
            log_provider_event(
                self.name,
                "DATAGOV_FAILED",
                live_request_id=context.live_request_id,
                reason="no_seeds",
            )
            status, meta = _map_outcome(
                evidence_ready=False,
                ingested=ingested,
                ranked_count=0,
                accepted_count=0,
            )
            return ProviderRunResult(
                provider=self.name,
                status=status,
                failure_codes=failure_codes,
                meta=meta,
            )

        try:
            ranked = discover_data_gov_candidates(
                service,
                search_q,
                seeds=seeds,
                overall_deadline=context.overall_deadline,
                live_request_id=context.live_request_id,
                verify_fn=verify_source,
            )
        except Exception as exc:  # noqa: BLE001
            log_provider_event(
                self.name,
                "DATAGOV_FAILED",
                live_request_id=context.live_request_id,
                reason=type(exc).__name__,
            )
            return ProviderRunResult(
                provider=self.name,
                status=ProviderPhaseStatus.ERROR,
                failure_codes=[type(exc).__name__],
                meta={"outcome": "failed", "reason": type(exc).__name__},
            )

        all_ranked: List[Dict[str, Any]] = list(context.extra.get("all_ranked") or [])
        all_ranked.extend(ranked)
        context.extra["all_ranked"] = all_ranked

        if not ranked:
            log_provider_event(
                self.name,
                "DATAGOV_FAILED",
                live_request_id=context.live_request_id,
                reason="no_candidates",
            )
            status, meta = _map_outcome(
                evidence_ready=False,
                ingested=ingested,
                ranked_count=0,
                accepted_count=0,
            )
            return ProviderRunResult(
                provider=self.name,
                status=status,
                failure_codes=failure_codes,
                meta=meta,
            )

        for row in ranked:
            log_provider_event(
                self.name,
                "DATAGOV_CANDIDATE_FOUND",
                live_request_id=context.live_request_id,
                url=(row.get("url") or "")[:160],
            )
            if (row.get("kind") or "").startswith("pdf") or str(row.get("url") or "").lower().endswith(".pdf"):
                log_provider_event(
                    self.name,
                    "DATAGOV_PDF_INGESTED",
                    live_request_id=context.live_request_id,
                    url=(row.get("url") or "")[:200],
                )

        phase_out = service._ingest_ranked_until_sufficient(  # noqa: SLF001
            ranked,
            search_q=search_q,
            rid=context.live_request_id,
            overall_deadline=context.overall_deadline,
            per_source=per_source,
            phase="data_gov",
            ingested=ingested,
            rejected_urls=rejected_urls,
            failure_codes=failure_codes,
            pdfs_used=pdfs_used,
            max_pdfs=max_pdfs,
        )

        merge_provider_ingested(context, ingested)
        context.failure_codes = failure_codes
        context.extra["pdfs_used"] = int(phase_out.get("pdfs_used") or pdfs_used)
        for url in (c.get("url") for c in ranked if c.get("url")):
            if url not in context.tried_urls:
                context.tried_urls.append(url)

        evidence_ready = bool(phase_out.get("evidence_ready"))
        accepted_url = phase_out.get("accepted_url")

        status, meta = _map_outcome(
            evidence_ready=evidence_ready,
            ingested=context.ingested,
            ranked_count=len(ranked),
            accepted_count=len(ranked),
        )
        meta.update(
            {
                "index_stats": phase_out.get("index_stats") or {},
                "candidates_tried": int(phase_out.get("candidates_tried") or 0),
            }
        )

        if evidence_ready:
            log_provider_event(
                self.name,
                "DATAGOV_SUFFICIENT",
                live_request_id=context.live_request_id,
                url=(accepted_url or "")[:160],
            )
        elif context.ingested:
            log_provider_event(
                self.name,
                "DATAGOV_PARTIAL",
                live_request_id=context.live_request_id,
                kept=len(context.ingested),
            )
        else:
            log_provider_event(
                self.name,
                "DATAGOV_FAILED",
                live_request_id=context.live_request_id,
                reason=meta.get("reason") or "no_usable",
            )

        return ProviderRunResult(
            provider=self.name,
            status=status,
            candidates_found=len(ranked),
            candidates_accepted=len(ranked),
            ingested_count=len(context.ingested),
            evidence_ready=evidence_ready,
            accepted_url=accepted_url,
            failure_codes=failure_codes,
            meta=meta,
        )
