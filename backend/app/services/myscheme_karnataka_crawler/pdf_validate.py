from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional, Tuple

from app.services.myscheme_karnataka_crawler.config import MAX_PDF_BYTES
from app.services.myscheme_karnataka_crawler.http_client import RespectfulHttpClient
from app.services.myscheme_karnataka_crawler.security import is_safe_http_url

PDF_MAGIC = b"%PDF"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_pdf_bytes(data: bytes, *, content_type: str = "") -> Tuple[bool, str, int]:
    if not data:
        return False, "empty", 0
    if len(data) > MAX_PDF_BYTES:
        return False, "too_large", 0
    if not data.startswith(PDF_MAGIC):
        return False, "invalid_magic", 0
    ct = (content_type or "").lower()
    if ct and "pdf" not in ct and "octet-stream" not in ct:
        return False, "invalid_content_type", 0
    try:
        import pypdf
        from io import BytesIO

        reader = pypdf.PdfReader(BytesIO(data))
        if len(reader.pages) < 1:
            return False, "no_pages", 0
        page_count = len(reader.pages)
    except Exception:
        return False, "corrupt_pdf", 0
    return True, "ok", page_count


def download_and_validate_pdf(
    client: RespectfulHttpClient,
    url: str,
) -> Dict[str, Any]:
    if not is_safe_http_url(url):
        return {"ok": False, "error": "unsafe_url"}
    try:
        data, ctype, status = client.get_bytes(url)
    except Exception as e:
        return {"ok": False, "error": f"download_failed:{e}"}
    ok, reason, pages = validate_pdf_bytes(data, content_type=ctype)
    if not ok:
        return {"ok": False, "error": reason, "http_status": status}
    digest = sha256_hex(data)
    return {
        "ok": True,
        "data": data,
        "sha256": digest,
        "size_bytes": len(data),
        "page_count": pages,
        "content_type": ctype,
        "http_status": status,
    }
