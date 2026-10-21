from __future__ import annotations

from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}
BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def is_safe_http_url(url: str) -> bool:
    try:
        parsed = urlparse((url or "").strip())
    except Exception:
        return False
    if parsed.scheme not in ALLOWED_SCHEMES:
        return False
    host = (parsed.hostname or "").lower()
    if not host or host in BLOCKED_HOSTS:
        return False
    if host.endswith(".local") or host.endswith(".internal"):
        return False
    return True


def is_trusted_document_host(url: str) -> bool:
    """Document linked from myScheme detail (gov.in / myscheme CDN / nic.in)."""
    if not is_safe_http_url(url):
        return False
    host = (urlparse(url).hostname or "").lower()
    if host.endswith(".myscheme.gov.in") or host.endswith(".myscheme.in"):
        return True
    if host.endswith(".gov.in") or host.endswith(".nic.in"):
        return True
    return False
