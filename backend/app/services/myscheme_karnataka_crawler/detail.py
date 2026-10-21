from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple
from urllib.parse import urljoin, urlparse

from app.services.myscheme_karnataka_crawler.http_client import RespectfulHttpClient
from app.services.myscheme_karnataka_crawler.security import is_trusted_document_host
from bs4 import BeautifulSoup

_PDF_RE = re.compile(r"\.pdf(\?|$|#)", re.I)


def _collect_from_references(refs: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for ref in refs or []:
        url = (ref.get("url") or "").strip()
        title = (ref.get("title") or "").strip()
        if not url or not _PDF_RE.search(url):
            continue
        if not is_trusted_document_host(url):
            continue
        out.append({"url": url, "title": title, "origin": "myscheme_api_reference"})
    return out


def fetch_scheme_detail(
    client: RespectfulHttpClient,
    slug: str,
) -> Tuple[Dict[str, Any], List[Dict[str, str]], bool]:
    """Return (detail_json, pdf_candidates, html_has_substantive_text)."""
    url = f"https://api.myscheme.gov.in/schemes/v6/public/schemes?slug={slug}&lang=en"
    raw, _, _ = client.get_bytes(url, myscheme_api=True)
    import json

    payload = json.loads(raw.decode("utf-8"))
    data = payload.get("data") or {}
    en = data.get("en") or {}
    content = en.get("schemeContent") or {}
    refs = content.get("references") or []
    candidates = _collect_from_references(refs)

    # HTML detail page (same links may appear in DOM)
    page_url = f"https://www.myscheme.gov.in/schemes/{slug}"
    html = ""
    try:
        body, _, _ = client.get_bytes(page_url)
        html = body.decode("utf-8", "ignore")
    except Exception:
        html = ""

    html_has_text = len(re.sub(r"<[^>]+>", " ", html)) > 800
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if not href:
                continue
            absolute = urljoin(page_url, href).split("#")[0]
            if not _PDF_RE.search(absolute):
                continue
            if not is_trusted_document_host(absolute):
                continue
            if any(c["url"] == absolute for c in candidates):
                continue
            candidates.append(
                {
                    "url": absolute,
                    "title": (a.get_text(" ", strip=True) or "")[:200],
                    "origin": "myscheme_html_link",
                }
            )

    basic = en.get("basicDetails") or {}
    ministry = basic.get("nodalDepartmentName") or basic.get("nodalMinistryName")
    if isinstance(ministry, dict):
        ministry = ministry.get("label")
    detail = {
        "scheme_name": basic.get("schemeName") or slug,
        "ministry": ministry,
        "brief_description": content.get("briefDescription"),
    }
    return detail, candidates, html_has_text and not candidates
