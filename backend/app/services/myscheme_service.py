"""myScheme.gov.in — universal scheme discovery + canonical page acquisition.

Does NOT redesign RAG. Seeds and extracted content flow through the existing
live acquisition → ingest_raw_bytes → Evidence Validator pipeline.

Priority (scheme-related live fallback only):
  local KB FAIL → myScheme FIRST → Evidence Validator sufficiency
  → if insufficient/unavailable → existing trusted registry sources
  (verified myScheme evidence is retained and combined).

Discovery surfaces (additive):
  - https://www.myscheme.gov.in/search
  - https://www.myscheme.gov.in/external/search
  - https://rules.myscheme.gov.in/  (catalogue / eligibility index)
  - https://www.myscheme.gov.in/schemes/{scheme_id}  (canonical; ID resolved dynamically)

Rules:
- myscheme.gov.in (+ rules subdomain) is trusted (registry).
- Linked domains do NOT inherit trust — verify_source / registry only.
- No login/CAPTCHA/OTP bypass — access blocks stop that path.
- HTTP 200 alone is not success — SPA/shell pages must escalate to Playwright.
- Read-only public information only.
"""

from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse

logger = logging.getLogger("gramsakhi.myscheme")

# Discovery metadata only (not RAG evidence). Refreshed when schemes resolve.
_DISCOVERY_CACHE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "myscheme_discovery_cache.json"
)
_DISCOVERY_CACHE_TTL_SECONDS = 30 * 24 * 3600

MYSCHEME_HOSTS = frozenset(
    {
        "myscheme.gov.in",
        "www.myscheme.gov.in",
        "rules.myscheme.gov.in",
        "www.rules.myscheme.gov.in",
    }
)
MYSCHEME_HOME = "https://www.myscheme.gov.in/"
MYSCHEME_SEARCH = "https://www.myscheme.gov.in/search"
MYSCHEME_EXTERNAL_SEARCH = "https://www.myscheme.gov.in/external/search"
MYSCHEME_RULES_HOME = "https://rules.myscheme.gov.in/"

# Known aliases → myScheme path slug when already observed. Unknown schemes must
# be resolved dynamically from search/catalogue HTML (never invent IDs).
_SCHEME_SLUGS: Dict[str, str] = {
    "pm-kisan": "pm-kisan",
    "pmkisan": "pm-kisan",
    "pmjjby": "pmjjby",
    "pmsby": "pmsby",
    "pm-sby": "pmsby",
    "pm sby": "pmsby",
    "pm sby yojana": "pmsby",
    "pmfby": "pmfby",
    "mgnrega": "mgnrega",
    "ab-pmjay": "ab-pmjay",
    "ayushman": "ab-pmjay",
    "pmjay": "ab-pmjay",
    "pmay-g": "pmayg",
    "pmayg": "pmayg",
    # Observed on myScheme (fixtures + live /schemes/us) — not invented.
    "udyogini": "us",
    "udyogini scheme": "us",
}

# Name-only aliases for matching (NOT hard-coded scheme IDs).
_NAME_ALIASES: Dict[str, Tuple[str, ...]] = {
    "udyogini": ("udyogini", "udyogini scheme", "udyogini yojane", "udyogini yojana"),
    "shakti": ("shakti", "shakti scheme", "shakti yojana"),
    "gruha lakshmi": ("gruha lakshmi", "gruhalakshmi"),
    "pm-kisan": ("pm-kisan", "pm kisan", "pmkisan", "pradhan mantri kisan"),
    "mukhyamantri prakhand parivahan": (
        "mukhyamantri prakhand parivahan",
        "prakhand parivahan yojana",
        "mukhyamantri prakhand parivahan yojana",
    ),
}

# Script / transliteration → English discovery name (response language unchanged).
_SCRIPT_NAME_MAP: Tuple[Tuple[str, str], ...] = (
    ("ಉದ್ಯೋಗಿನಿ", "Udyogini"),
    ("उद्योगिनी", "Udyogini"),
    ("ಪಿಎಂ ಕಿಸಾನ್", "PM-KISAN"),
    ("पीएम किसान", "PM-KISAN"),
)

_STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "about",
        "details",
        "detail",
        "scheme",
        "yojana",
        "yojan",
        "what",
        "who",
        "how",
        "tell",
        "me",
        "please",
        "eligibility",
        "benefit",
        "benefits",
        "document",
        "documents",
        "information",
        "info",
        "karnataka",
        "india",
        "government",
        "govt",
        "official",
        "everything",
        "required",
        "apply",
        "application",
    }
)

_SECTION_PATTERNS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("details", ("details", "overview", "about the scheme", "scheme details", "description")),
    ("benefits", ("benefits", "benefit", "financial assistance", "assistance")),
    (
        "eligibility",
        ("eligibility", "eligible", "who can apply", "who is eligible", "criteria"),
    ),
    (
        "application",
        (
            "application process",
            "application",
            "how to apply",
            "apply online",
            "procedure",
        ),
    ),
    (
        "documents",
        ("documents required", "documents", "required documents", "document checklist"),
    ),
    ("faqs", ("frequently asked questions", "faqs", "faq", "common questions")),
    ("sources", ("sources and references", "sources", "references", "official sources")),
)

_SHELL_MARKERS = (
    "something went wrong",
    "please try again later",
    "network error",
    "loading...",
    "loading…",
    "enable javascript",
    "javascript is required",
    "this app requires javascript",
)


def is_myscheme_host(host: str) -> bool:
    h = (host or "").lower().strip(".")
    return h in MYSCHEME_HOSTS or h.endswith(".myscheme.gov.in")


def is_myscheme_url(url: str) -> bool:
    try:
        return is_myscheme_host(urlparse(url).hostname or "")
    except Exception:
        return False


def log_myscheme(event: str, **fields: Any) -> None:
    parts = [f"{k}={fields[k]!r}" for k in sorted(fields) if fields[k] is not None]
    line = f"{event} " + " ".join(parts)
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        print(line.encode("ascii", "backslashreplace").decode("ascii"), flush=True)
    logger.info("%s %s", event, " ".join(parts))


def verify_linked_url(url: str, *, verify_fn: Callable[[str], bool]) -> bool:
    """Linked domains from myScheme must pass registry independently."""
    if not url or not isinstance(url, str):
        return False
    if not verify_fn(url):
        return False
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    if host.endswith((".gov.in", ".nic.in")) or is_myscheme_host(host):
        return True
    return bool(verify_fn(url))


def normalize_scheme_key(name: str) -> str:
    """Normalize scheme names for matching (case/space/punct/Unicode)."""
    t = unicodedata.normalize("NFKC", name or "")
    t = t.lower()
    t = t.replace("–", "-").replace("—", "-")
    t = re.sub(r"[^\w\s\-]", " ", t, flags=re.UNICODE)
    t = re.sub(r"[\s_\-]+", " ", t).strip()
    t = re.sub(r"\b(scheme|yojana|yojna)\b", " ", t).strip()
    t = re.sub(r"\s+", " ", t).strip()
    # Collapse PM KISAN / PM-KISAN / PMKISAN
    t = t.replace("pm kisan", "pmkisan").replace("pm-kisan", "pmkisan")
    t = t.replace("pm sby", "pmsby")
    return t


def _query_tokens(query: str) -> List[str]:
    return [
        t
        for t in re.findall(r"[a-zA-Z0-9\-]{3,}", (query or "").lower())
        if t not in _STOP
    ]


_CONVERSATIONAL_PREFIX = re.compile(
    r"^(?:"
    r"can\s+i\s+get(?:\s+the)?(?:\s+details?)?(?:\s+about)?|"
    r"can\s+you(?:\s+please)?(?:\s+tell\s+me)?(?:\s+about)?|"
    r"could\s+(?:i|you)(?:\s+please)?(?:\s+get|tell\s+me)?(?:\s+details?)?(?:\s+about)?|"
    r"please\s+(?:tell\s+me|explain|give|share|provide)|"
    r"(?:please\s+)?(?:give|share|provide)\s+(?:me\s+)?(?:the\s+)?(?:details?|information|info)(?:\s+(?:about|on|of))?|"
    r"tell\s+me(?:\s+more)?(?:\s+about)?|"
    r"what\s+(?:is|are)|"
    r"details?\s+(?:about|of|on)|"
    r"information\s+(?:about|on|of)|"
    r"explain(?:\s+to\s+me)?|"
    r"i\s+want\s+(?:to\s+know\s+)?(?:about)?|"
    r"do\s+you\s+have(?:\s+(?:any\s+)?details?)?(?:\s+about)?|"
    r"how\s+(?:do\s+i|to)\s+apply\s+for|"
    r"get\s+(?:me\s+)?(?:details?|information)(?:\s+about)?"
    r")\s+",
    re.IGNORECASE,
)


def extract_scheme_name_hint(query: str) -> str:
    """Best-effort scheme name phrase from a citizen question (original preserved elsewhere)."""
    raw = (query or "").strip()
    if not raw:
        return ""
    # Map known Kn/Hi scheme names to English discovery strings first.
    for src, eng in _SCRIPT_NAME_MAP:
        if src in raw:
            raw = raw.replace(src, eng)
    t = _CONVERSATIONAL_PREFIX.sub("", raw).strip()
    # Kannada/Hindi question wrappers (best-effort)
    t = re.sub(r"(ಯಾವುದು|ಏನು|ಬಗ್ಗೆ|ಕುರಿತು|ಹೇಳಿ|ಮಾಹಿತಿ)", " ", t)
    t = re.sub(r"(क्या|है|के बारे में|बताओ|जानकारी|विवरण)", " ", t)
    # Drop trailing politeness / ask wrappers
    t = re.sub(r"\b(please|thanks|thank you)\b", " ", t, flags=re.I)
    t = re.sub(
        r"\b(details|eligibility|benefits?|documents?|application|process|"
        r"required|complete details|full details)\b",
        " ",
        t,
        flags=re.I,
    )
    # Keep state as optional boost token in variants, not in core name
    if re.search(r"\bin\s+karnataka\b", t, flags=re.I) or re.search(
        r"\bkarnataka\b", t, flags=re.I
    ):
        t = re.sub(r"\bin\s+karnataka\b", " ", t, flags=re.I)
        t = re.sub(r"\bkarnataka\b", " ", t, flags=re.I)
    t = re.sub(r"[?!.]+$", "", t).strip()
    # Drop leftover glue words after section stripping ("PMJJBY and")
    t = re.sub(r"\b(and|or|the|a|an|of|for|to|in|on|with)\b", " ", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip(" -,:")
    # Transliteration / alias cleanup → stable English discovery label
    t_key = normalize_scheme_key(t)
    _display = {
        "udyogini": "Udyogini",
        "pm-kisan": "PM-KISAN",
        "shakti": "Shakti",
        "gruha lakshmi": "Gruha Lakshmi",
        "mukhyamantri prakhand parivahan": "Mukhyamantri Prakhand Parivahan Yojana",
    }
    for canon, aliases in _NAME_ALIASES.items():
        if t_key == normalize_scheme_key(canon) or any(
            t_key == normalize_scheme_key(a) for a in aliases
        ):
            return _display.get(canon, canon.upper() if len(canon) <= 8 else canon.title())
    return t[:120]


def normalize_myscheme_search_query(query: str) -> str:
    """Authoritative short search string — never the raw conversational sentence."""
    hint = extract_scheme_name_hint(query)
    if hint:
        # Title-ish cleanup: collapse spaces
        return re.sub(r"\s+", " ", hint).strip()[:100]
    tokens = _query_tokens(query)
    return " ".join(tokens[:8])[:100]


def scheme_query_variants(query: str) -> List[str]:
    """Search variations for myScheme discovery (English + normalized)."""
    base = normalize_myscheme_search_query(query)
    if not base:
        return []
    prefer_ka = bool(re.search(r"\bkarnataka\b", query or "", flags=re.I))
    variants: List[str] = []
    parts = base.split()
    shortened = " ".join(parts[:4]) if len(parts) > 4 else ""
    for v in (
        base,
        f"{base} Scheme" if "scheme" not in base.lower() and "yojana" not in base.lower() else "",
        f"{base} Karnataka" if prefer_ka and "karnataka" not in base.lower() else "",
        f"{base} Scheme Karnataka" if prefer_ka else "",
        shortened,
        # Drop leading honorific / mukhyamantri shortening for long state schemes
        re.sub(r"^(mukhyamantri|pradhan\s+mantri)\s+", "", base, flags=re.I).strip(),
    ):
        v = (v or "").strip()
        if v and v.lower() not in {x.lower() for x in variants}:
            variants.append(v[:100])
    log_myscheme(
        "MYSCHEME_QUERY_NORMALIZED",
        original=(query or "")[:160],
        normalized=base,
        variants=variants[:4],
    )
    return variants[:6]


def slug_hint_from_query(query: str) -> Optional[str]:
    """Map query aliases to a myScheme /schemes/{slug} when known."""
    q = (query or "").lower()
    key = normalize_scheme_key(query)
    for alias, slug in sorted(_SCHEME_SLUGS.items(), key=lambda x: -len(x[0])):
        if alias in q or normalize_scheme_key(alias) == key:
            return slug
    if "jeevan jyoti" in q or "jeevan jyothi" in q:
        return "pmjjby"
    if "suraksha bima" in q or "pm-sby" in q or "pm sby" in q:
        return "pmsby"
    if "fasal bima" in q:
        return "pmfby"
    if "pm-kisan" in q or "pm kisan" in q or "pmkisan" in q:
        return "pm-kisan"
    return None


def build_myscheme_scheme_url(slug: str) -> str:
    slug = (slug or "").strip().strip("/")
    return f"https://www.myscheme.gov.in/schemes/{slug}"


def build_myscheme_search_url(query: str) -> str:
    q = normalize_myscheme_search_query(query) or (query or "").strip()[:80]
    return f"{MYSCHEME_SEARCH}?q={quote_plus(q)}"


def build_myscheme_external_search_url(query: str) -> str:
    q = normalize_myscheme_search_query(query) or (query or "").strip()[:80]
    return f"{MYSCHEME_EXTERNAL_SEARCH}?q={quote_plus(q)}"


_RESERVED_SCHEME_IDS = frozenset(
    {
        "search",
        "list",
        "all",
        "index",
        "public",
        "api",
        "v1",
        "v2",
        "v3",
        "v4",
        "v5",
        "v6",
        "v7",
        "v8",
        "v9",
    }
)


def extract_scheme_id_from_url(url: str) -> Optional[str]:
    """Canonical myScheme slug from a page or public API URL.

    API paths like /schemes/v6/public/schemes?slug=us must resolve to ``us``,
    never the version segment ``v6``.
    """
    try:
        parsed = urlparse(url or "")
    except Exception:
        return None
    qs = parse_qs(parsed.query or "")
    for key in ("slug", "schemeId", "scheme_id", "schemeid"):
        raw = (qs.get(key) or [""])[0].strip().strip("/")
        if raw and raw.lower() not in _RESERVED_SCHEME_IDS:
            return raw
    path = parsed.path or ""
    m = re.search(r"/schemes/([A-Za-z0-9][A-Za-z0-9\-_]{0,80})/?", path)
    if not m:
        return None
    sid = m.group(1).strip().strip("/")
    if sid.lower() in _RESERVED_SCHEME_IDS:
        return None
    return sid


def canonical_myscheme_page_url(url: str, scheme_id: Optional[str] = None) -> str:
    """Prefer www.myscheme.gov.in/schemes/{id} over API/versioned paths."""
    sid = (scheme_id or extract_scheme_id_from_url(url) or "").strip()
    if sid:
        return build_myscheme_scheme_url(sid)
    return url or ""


def _looks_like_scheme_query(query: str) -> bool:
    q = (query or "").lower()
    if not q.strip():
        return False
    if slug_hint_from_query(q):
        return True
    markers = (
        "scheme",
        "yojana",
        "yojan",
        "eligibility",
        "benefit",
        "pm-",
        "pradhan mantri",
        "ಯೋಜನೆ",
        "ಯೋಜನಾ",
        "योजना",
    )
    if any(m in q for m in markers):
        return True
    # Known citizen scheme-name aliases (not arbitrary English sentences)
    q_key = normalize_scheme_key(extract_scheme_name_hint(query) or query)
    for canon, aliases in _NAME_ALIASES.items():
        if q_key == normalize_scheme_key(canon) or any(
            q_key == normalize_scheme_key(a) for a in aliases
        ):
            return True
    return False


def is_myscheme_shell_html(
    html: str,
    *,
    rendered_text: str = "",
) -> Tuple[bool, str]:
    """True when HTTP body is an SPA/shell/error page — not usable scheme evidence.

    HTTP 200 alone must never count as successful acquisition.
    """
    raw = html or ""
    rendered = (rendered_text or "").strip()
    # Always derive text from HTML too — short tab labels must not hide rich body.
    stripped = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", raw)
    stripped = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", stripped)
    stripped = re.sub(r"(?is)<[^>]+>", " ", stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    text = rendered if len(rendered) >= len(stripped) else stripped
    if rendered and stripped:
        # Prefer the longer signal; keep both for marker scan
        text = rendered if len(rendered) >= 200 or len(rendered) >= len(stripped) else stripped
        if len(stripped) > len(text):
            text = stripped

    low = f"{rendered}\n{stripped}\n{raw}".lower()
    marker_hit = ""
    for marker in _SHELL_MARKERS:
        if marker in low:
            marker_hit = (
                "NETWORK_ERROR"
                if "network" in marker or "went wrong" in marker
                else "STATIC_SHELL"
            )
            break

    alpha = sum(1 for ch in text if ch.isalpha())
    has_scheme_path = bool(re.search(r"/schemes/[A-Za-z0-9\-_]{1,80}", raw, re.I))
    has_section = any(
        k in text.lower()
        for k in ("eligibility", "benefits", "documents", "application process", "faq")
    )

    # myScheme often keeps an error toast in the DOM even after content hydrates.
    # Marker alone is fatal only when no scheme sections are present.
    if marker_hit and not has_section:
        return True, marker_hit

    if alpha < 80 and not has_scheme_path and not has_section:
        return True, "CONTENT_EMPTY"
    if alpha < 160 and ("id=\"root\"" in raw.lower() or "id='root'" in raw.lower()) and not has_section:
        return True, "STATIC_SHELL"
    # Footer / chrome only
    chrome = ("copyright", "government of india", "privacy policy", "terms of use", "skip to")
    chrome_hits = sum(1 for c in chrome if c in text.lower())
    if alpha < 220 and chrome_hits >= 2 and not has_section and not has_scheme_path:
        return True, "STATIC_SHELL"
    return False, "CONTENT_OK"


def assess_myscheme_content_quality(
    html: str,
    *,
    rendered_text: str = "",
) -> Dict[str, Any]:
    shell, reason = is_myscheme_shell_html(html, rendered_text=rendered_text)
    sections = (
        extract_scheme_sections(html, rendered_text=rendered_text) if not shell else {}
    )
    text = rendered_text or ""
    if not text and html:
        text = re.sub(r"(?is)<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
    return {
        "is_shell": shell,
        "failure_class": reason if shell else (
            "CONTENT_SUFFICIENT" if len(sections) >= 2 or len(text) >= 400 else "CONTENT_PARTIAL"
        ),
        "sections": list(sections.keys()),
        "section_count": len(sections),
        "text_chars": len(text),
        "sufficient": (not shell) and (len(sections) >= 2 or len(text) >= 500),
    }


def _match_section_key(label: str) -> Optional[str]:
    lab = (label or "").strip().lower()
    if not lab or len(lab) > 90:
        return None
    for key, aliases in _SECTION_PATTERNS:
        if any(a == lab or lab.startswith(a) or a in lab for a in aliases):
            return key
    return None


def extract_sections_from_plain_text(text: str) -> Dict[str, str]:
    """Split rendered text on Details/Benefits/… headings (SPA-friendly)."""
    raw = re.sub(r"\s+", " ", (text or "").strip())
    if len(raw) < 40:
        return {}
    # Build alternation of section aliases (longest first)
    aliases: List[Tuple[str, str]] = []
    for key, names in _SECTION_PATTERNS:
        for a in names:
            aliases.append((a, key))
    aliases.sort(key=lambda x: -len(x[0]))
    pattern = "|".join(re.escape(a) for a, _ in aliases)
    if not pattern:
        return {}
    parts = re.split(rf"(?i)\b({pattern})\b", raw)
    if len(parts) < 3:
        # No clear headings — treat whole blob as details when scheme-like
        low = raw.lower()
        if any(k in low for k in ("eligib", "benefit", "scheme", "yojana", "document")):
            return {"details": raw[:4000]}
        return {}
    found: Dict[str, str] = {}
    # parts: [preamble, heading, body, heading, body, ...]
    preamble = (parts[0] or "").strip()
    if len(preamble) >= 60 and "details" not in found:
        found["details"] = preamble[:4000]
    i = 1
    while i + 1 < len(parts):
        heading = parts[i]
        body = (parts[i + 1] or "").strip()
        key = _match_section_key(heading)
        if key and body and key not in found and len(body) >= 20:
            found[key] = body[:4000]
            log_myscheme("MYSCHEME_SECTION_EXTRACTED", section=key, chars=len(body), via="text")
        i += 2
    return found


def extract_scheme_sections(
    html: str,
    *,
    rendered_text: str = "",
) -> Dict[str, str]:
    """Extract Details/Benefits/Eligibility/Application/Documents/FAQ blocks."""
    found: Dict[str, str] = {}
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        BeautifulSoup = None  # type: ignore

    if BeautifulSoup is not None and html:
        soup = BeautifulSoup(html or "", "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        nodes = soup.find_all(re.compile(r"^h[1-6]$"))
        nodes.extend(soup.find_all(["strong", "button", "a"]))
        # SPA panels often label sections on div/span tabs
        for node in soup.find_all(["div", "span"], limit=200):
            label = (node.get_text(" ", strip=True) or "")
            if label and len(label) <= 60 and _match_section_key(label):
                nodes.append(node)

        seen_ids = set()
        for node in nodes:
            nid = id(node)
            if nid in seen_ids:
                continue
            seen_ids.add(nid)
            label = (node.get_text(" ", strip=True) or "").lower()
            section_key = _match_section_key(label)
            if not section_key or section_key in found:
                continue
            chunks: List[str] = [node.get_text(" ", strip=True)]
            for sib in node.find_all_next(
                ["p", "li", "td", "div", "span", "h2", "h3", "h4"], limit=60
            ):
                if sib.name in ("h2", "h3", "h4", "button") and sib is not node:
                    sib_label = (sib.get_text(" ", strip=True) or "").lower()
                    if _match_section_key(sib_label):
                        break
                # Skip pure nav chrome
                txt = sib.get_text(" ", strip=True)
                if not txt or len(txt) < 2:
                    continue
                if txt.lower() in {"back", "home", "skip to main content"}:
                    continue
                chunks.append(txt)
                if sum(len(c) for c in chunks) > 2500:
                    break
            body = "\n".join(chunks).strip()
            if len(body) >= 40:
                found[section_key] = body[:4000]
                log_myscheme(
                    "MYSCHEME_SECTION_EXTRACTED",
                    section=section_key,
                    chars=len(body),
                    via="html",
                )

    # Merge plain-text extraction (covers hydrated SPA / accordion dumps)
    for key, body in extract_sections_from_plain_text(rendered_text).items():
        if key not in found or len(body) > len(found.get(key) or ""):
            found[key] = body
    if not found and html and not rendered_text:
        # Last resort: strip tags and split
        stripped = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
        stripped = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", stripped)
        stripped = re.sub(r"(?is)<[^>]+>", " ", stripped)
        found = extract_sections_from_plain_text(stripped)
    return found


def sections_as_evidence_text(
    sections: Dict[str, str],
    *,
    scheme_name: str = "",
    scheme_id: str = "",
    canonical_url: str = "",
) -> str:
    """Format extracted sections as ingestible evidence text (not URL-only)."""
    parts: List[str] = []
    if scheme_name:
        parts.append(f"SCHEME:\n{scheme_name}")
    if scheme_id:
        parts.append(f"SCHEME_ID:\n{scheme_id}")
    parts.append("SOURCE:\nmyScheme")
    if canonical_url:
        parts.append(f"CANONICAL URL:\n{canonical_url}")
    label = {
        "details": "Details",
        "benefits": "Benefits",
        "eligibility": "Eligibility",
        "application": "Application Process",
        "documents": "Documents Required",
        "faqs": "Frequently Asked Questions",
        "sources": "Sources and References",
    }
    for key in ("details", "benefits", "eligibility", "application", "documents", "faqs", "sources"):
        if key in sections and sections[key]:
            parts.append(
                f"SECTION:\n{label.get(key, key.title())}\n\nCONTENT:\n{sections[key]}"
            )
    return "\n\n".join(parts).strip()


_GENERIC_IDENTITY_TOKENS = {
    "scheme",
    "yojana",
    "yojane",
    "yojna",
    "details",
    "information",
    "info",
    "benefit",
    "benefits",
    "eligibility",
    "eligible",
    "financial",
    "help",
    "farmer",
    "farmers",
    "about",
    "complete",
    "full",
    "please",
    "tell",
    "document",
    "documents",
    "application",
    "apply",
    "process",
}

_SCHEME_PHRASE = re.compile(
    r"(?:\b(?:scheme|yojana|yojane|yojna)\b|ಯೋಜನೆ|योजना)",
    re.IGNORECASE,
)


def _distinctive_identity_tokens(key: str) -> List[str]:
    return [
        t
        for t in (key or "").split()
        if len(t) >= 4 and t not in _GENERIC_IDENTITY_TOKENS
    ]


def _collapse_scheme_slug(value: str) -> str:
    """pm-kisan / pmkisan / pm-sby / pmsby → comparable slug token."""
    t = (value or "").strip().lower().replace("_", "-")
    t = t.replace("-", "").replace(" ", "")
    return t


def _usable_scheme_slug(value: str) -> str:
    """Drop API version/path junk so it cannot impersonate a scheme id."""
    collapsed = _collapse_scheme_slug(value)
    reserved = {s.replace("-", "") for s in _RESERVED_SCHEME_IDS}
    if not collapsed or collapsed in reserved:
        return ""
    return collapsed


def requested_scheme_identity(query: str) -> Optional[Dict[str, str]]:
    """Identify an explicit scheme in the citizen question (if any).

    Hard isolation applies when the user named a scheme — including schemes
    not yet in the local alias catalog (e.g. KSCSTE Emeritus Scientist Scheme).
    Generic topical questions must not trigger wrong-scheme rejection.
    """
    mentions: List[str] = []
    try:
        from app.services.query_rewriter import extract_scheme_mentions

        mentions = extract_scheme_mentions(query)
    except Exception:
        mentions = []

    hint = ""
    if mentions:
        hint = mentions[0]
    else:
        hint = extract_scheme_name_hint(query) or ""

    if not hint:
        sid_only = slug_hint_from_query(query) or ""
        if sid_only:
            return {
                "scheme_name": sid_only,
                "scheme_id": sid_only,
                "normalized_key": normalize_scheme_key(sid_only),
            }
        return None

    key = normalize_scheme_key(hint)
    if not key or len(key) < 3:
        return None
    if key in {
        "scheme",
        "yojana",
        "details",
        "information",
        "benefit",
        "eligibility",
        "financial help",
        "farmers",
    }:
        return None

    sid = slug_hint_from_query(hint) or slug_hint_from_query(query) or ""
    known = set(_known_scheme_keys())
    known_hit = bool(
        sid
        or mentions
        or key in known
        or any(
            key == k or (len(k) >= 4 and (key in k or k in key))
            for k in known
        )
    )
    distinctive = _distinctive_identity_tokens(key)
    named = known_hit or (
        bool(distinctive)
        and (
            bool(_SCHEME_PHRASE.search(query or ""))
            or len(distinctive) >= 2
        )
    )
    if not named:
        return None

    return {
        "scheme_name": hint.strip()[:120],
        "scheme_id": sid,
        "normalized_key": key,
    }


def _known_scheme_keys() -> List[str]:
    keys = set()
    for alias in _SCHEME_SLUGS:
        keys.add(normalize_scheme_key(alias))
    for canon, aliases in _NAME_ALIASES.items():
        keys.add(normalize_scheme_key(canon))
        for a in aliases:
            keys.add(normalize_scheme_key(a))
    try:
        from app.services.query_rewriter import _SCHEME_ALIASES

        for alias, canonical in _SCHEME_ALIASES:
            keys.add(normalize_scheme_key(alias))
            keys.add(normalize_scheme_key(canonical))
    except Exception:
        pass
    return sorted((k for k in keys if len(k) >= 3), key=len, reverse=True)


def detect_scheme_keys_in_text(text: str) -> List[str]:
    """Normalized scheme keys mentioned in chunk/doc text."""
    blob = normalize_scheme_key(text or "")
    if not blob:
        return []
    found: List[str] = []
    for key in _known_scheme_keys():
        if key in blob and key not in found:
            found.append(key)
    return found


def evidence_matches_requested_scheme(
    doc: Dict[str, Any],
    requested: Dict[str, str],
) -> bool:
    """Hard scheme-identity check — similarity alone is insufficient."""
    req_key = (requested.get("normalized_key") or "").strip()
    req_sid = (requested.get("scheme_id") or "").strip().lower()
    if not req_key and not req_sid:
        return True

    meta = doc.get("metadata") or {}
    if not isinstance(meta, dict):
        meta = {}
    name = str(
        doc.get("scheme_name")
        or meta.get("scheme_name")
        or doc.get("document_title")
        or doc.get("link_text")
        or ""
    )
    sid = str(
        doc.get("scheme_id")
        or meta.get("scheme_id")
        or extract_scheme_id_from_url(
            str(
                doc.get("source")
                or doc.get("url")
                or meta.get("source")
                or meta.get("canonical_url")
                or ""
            )
        )
        or ""
    ).lower()
    content = str(doc.get("content") or doc.get("rendered_text") or "")
    source = str(
        doc.get("source")
        or doc.get("url")
        or meta.get("source")
        or meta.get("canonical_url")
        or ""
    )
    blob = f"{name} {sid} {content} {source}"
    blob_key = normalize_scheme_key(blob)

    req_slug = _usable_scheme_slug(
        req_sid or slug_hint_from_query(requested.get("scheme_name") or "") or ""
    )
    cand_slug = _usable_scheme_slug(sid or slug_hint_from_query(name) or "")
    if req_slug and cand_slug:
        if req_slug == cand_slug:
            return True
        return False

    # Positive match: requested key/id present
    if req_sid and (sid == req_sid or f"/schemes/{req_sid}" in (blob or "").lower()):
        return True
    if req_key and len(req_key) >= 4 and req_key in blob_key:
        return True
    if req_key and normalize_scheme_key(name) == req_key:
        return True
    req_tokens = _distinctive_identity_tokens(req_key)
    if req_tokens:
        hits = sum(1 for t in req_tokens if t in blob_key)
        if hits >= max(1, (len(req_tokens) + 1) // 2):
            return True

    # Hard reject: document clearly about a different known scheme
    found = detect_scheme_keys_in_text(blob)
    if found and req_key:
        if any(req_key == f or req_key in f or f in req_key for f in found):
            return True
        other = [f for f in found if not (req_key == f or req_key in f or f in req_key)]
        if other:
            return False
    # Explicit request with no positive identity overlap → reject
    if req_key and len(req_key) >= 4:
        return False
    return True


def _candidate_scheme_label(doc: Dict[str, Any]) -> str:
    meta = doc.get("metadata") or {}
    if not isinstance(meta, dict):
        meta = {}
    name = str(
        doc.get("scheme_name")
        or meta.get("scheme_name")
        or doc.get("document_title")
        or doc.get("link_text")
        or ""
    ).strip()
    sid = str(
        doc.get("scheme_id")
        or meta.get("scheme_id")
        or extract_scheme_id_from_url(
            str(doc.get("source") or doc.get("url") or meta.get("canonical_url") or "")
        )
        or ""
    ).strip()
    return name or sid


def _log_identity_decision(
    requested: Dict[str, str],
    doc: Dict[str, Any],
    *,
    accepted: bool,
) -> None:
    url = str(
        doc.get("source")
        or doc.get("url")
        or (doc.get("metadata") or {}).get("source")
        or ""
    )[:160]
    cand = _candidate_scheme_label(doc)
    log_myscheme(
        "MYSCHEME_IDENTITY_CHECK",
        requested_scheme=requested.get("scheme_name") or "",
        candidate_scheme=cand,
        url=url or None,
        result="PASS" if accepted else "REJECT",
    )
    if accepted:
        log_myscheme(
            "MYSCHEME_CANDIDATE_ACCEPTED",
            requested_scheme=requested.get("scheme_name") or "",
            candidate_scheme=cand,
            url=url or None,
        )
    else:
        log_myscheme(
            "MYSCHEME_CANDIDATE_REJECTED",
            reason="SCHEME_IDENTITY_MISMATCH",
            requested_scheme=requested.get("scheme_name") or "",
            candidate_scheme=cand,
            url=url or None,
        )


def request_accepts_candidate(query: str, candidate: Dict[str, Any]) -> bool:
    """Request-level identity gate for live myScheme candidates.

    Search/catalogue URLs (no scheme slug) are discovery surfaces, not evidence.
    """
    requested = requested_scheme_identity(query)
    if not requested:
        return True
    url = str(candidate.get("url") or candidate.get("source") or "")
    sid = str(
        candidate.get("scheme_id") or extract_scheme_id_from_url(url) or ""
    ).strip()
    kind = str(candidate.get("kind") or "").lower()
    if not sid and "/schemes/" not in url.lower():
        if kind in ("search", "catalogue", "listing", "search_shell", "catalog"):
            _log_identity_decision(requested, candidate, accepted=False)
            return False
        ok = evidence_matches_requested_scheme(candidate, requested)
        _log_identity_decision(requested, candidate, accepted=ok)
        return ok
    ok = evidence_matches_requested_scheme(candidate, requested)
    _log_identity_decision(requested, candidate, accepted=ok)
    return ok


def filter_evidence_by_scheme(
    query: str,
    docs: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Keep only scheme-compatible evidence for explicit scheme questions."""
    requested = requested_scheme_identity(query)
    if not requested:
        return list(docs or [])
    kept: List[Dict[str, Any]] = []
    logged_urls: Set[str] = set()
    for d in docs or []:
        ok = evidence_matches_requested_scheme(d, requested)
        url = str(d.get("source") or d.get("url") or "")[:160]
        log_key = url or str(id(d))
        if log_key not in logged_urls:
            logged_urls.add(log_key)
            _log_identity_decision(requested, d, accepted=ok)
        if ok:
            kept.append(d)
        else:
            log_myscheme(
                "WRONG_SCHEME_EVIDENCE_REJECTED",
                requested_scheme=requested.get("scheme_name"),
                requested_scheme_id=requested.get("scheme_id") or None,
                retrieved_scheme=d.get("scheme_name")
                or (d.get("metadata") or {}).get("scheme_name"),
                retrieved_scheme_id=d.get("scheme_id")
                or (d.get("metadata") or {}).get("scheme_id"),
                source_url=url or None,
            )
    log_myscheme(
        "SCHEME_IDENTITY_CHECK",
        requested_scheme=requested.get("scheme_name"),
        scheme_id=requested.get("scheme_id") or None,
        retrieved=len(docs or []),
        kept=len(kept),
    )
    return kept


def required_sections_for_query(query: str) -> List[str]:
    """Question-aware section needs for acquisition sufficiency (EV remains final gate)."""
    q = (query or "").lower()
    if any(t in q for t in ("benefit", "benefits", "ಪ್ರಯೋಜನ", "लाभ")):
        return ["benefits"]
    if any(t in q for t in ("eligib", "who can", "criteria", "ಅರ್ಹ", "पात्र")):
        return ["eligibility"]
    if any(t in q for t in ("how to apply", "application", "apply", "ಅರ್ಜಿ", "आवेदन")):
        return ["application"]
    if any(t in q for t in ("document", "documents", "ದಾಖಲೆ", "दस्तावेज")):
        return ["documents"]
    if any(t in q for t in ("faq", "frequently asked")):
        return ["faqs"]
    if any(
        t in q
        for t in (
            "deadline",
            "last date",
            "closing date",
            "ಅಂತಿಮ ದಿನಾಂಕ",
            "ಕೊನೆಯ ದಿನಾಂಕ",
            "अंतिम तिथि",
        )
    ):
        return ["details", "application"]
    # Broad / details questions — any substantive section helps; prefer several
    if any(
        t in q
        for t in (
            "detail",
            "details",
            "what is",
            "tell me",
            "information",
            "about",
            "ವಿವರ",
            "जानकारी",
        )
    ):
        return ["details", "benefits", "eligibility", "application", "documents"]
    return ["details", "benefits", "eligibility"]


def sections_meet_query_need(sections: Dict[str, str], query: str) -> bool:
    """True when acquired sections cover the citizen's question focus."""
    if not sections:
        return False
    required = required_sections_for_query(query)
    present = [k for k in required if (sections.get(k) or "").strip()]
    if len(required) == 1:
        return bool(present)
    # Broad query: need identity-ish content + at least 2 sections OR 1 long section
    if len(present) >= 2:
        return True
    if present and len(sections.get(present[0]) or "") >= 200:
        return True
    # Fallback: any 2 extracted sections
    return sum(1 for v in sections.values() if v and len(v) >= 40) >= 2


_INTENT_MARKERS: Dict[str, Tuple[str, ...]] = {
    "eligibility": (
        "eligibility",
        "eligible",
        "who can",
        "criteria",
        "beneficiary",
        "conditions",
        "head of family",
        "head of the family",
        "notified crop",
        "notified area",
        "notified crops",
        "age band",
        "savings bank account",
        "savings account",
        "resident of",
        "section:\neligibility",
    ),
    "benefits": (
        "benefits",
        "benefit",
        "subsidy",
        "assistance",
        "section:\nbenefits",
    ),
    "application": (
        "application process",
        "how to apply",
        "how do i apply",
        "section:\napplication",
    ),
    "documents": (
        "documents required",
        "required documents",
        "section:\ndocuments",
    ),
    "deadline": ("deadline", "last date", "closing date"),
    "faqs": ("frequently asked", "section:\nfaqs", "faq"),
    "overview": ("section:\ndetails", "overview", "scheme:"),
}


def query_citizen_intent(query: str) -> str:
    """Citizen question focus for generation (not a new retrieval architecture)."""
    q = (query or "").lower()
    if any(t in q for t in ("complete details", "full details", "all details", "everything about")):
        return "complete"
    try:
        from app.services.multilingual_retrieval_service import detect_intent

        intent = detect_intent(query)
        if intent == "amount":
            return "benefits"
        if intent and intent != "overview":
            return intent
        if intent == "overview":
            if any(t in q for t in ("details about", "get details", "information about")):
                return "complete"
            return "overview"
    except Exception:
        pass
    if any(t in q for t in ("details about", "get details", "information about")):
        return "complete"
    required = required_sections_for_query(query)
    if len(required) == 1:
        return required[0]
    return "overview"


def select_question_aware_evidence(
    query: str,
    docs: Sequence[Dict[str, Any]],
    *,
    max_chunks: int = 4,
) -> List[Dict[str, Any]]:
    """Prefer chunks matching the asked aspect. Never drop all validated evidence."""
    items = list(docs or [])
    if not items:
        return []
    intent = query_citizen_intent(query)
    if intent == "complete":
        return items[: max(max_chunks, 8)]
    if intent == "eligibility":
        max_chunks = max(max_chunks, 5)
    markers = _INTENT_MARKERS.get(intent) or ()
    if not markers:
        return items[:max_chunks]
    preferred: List[Dict[str, Any]] = []
    rest: List[Dict[str, Any]] = []
    for d in items:
        blob = f"{d.get('content') or ''} {d.get('scheme_name') or ''}".lower()
        meta = d.get("metadata") if isinstance(d.get("metadata"), dict) else {}
        tags = meta.get("section_tags") or []
        if isinstance(tags, str):
            tags = [tags]
        tag_hit = intent in tags or (intent == "eligibility" and "notified_crop" in tags)
        if tag_hit or any(m in blob for m in markers):
            preferred.append(d)
        else:
            rest.append(d)
    if not preferred:
        return items[:max_chunks]
    out = preferred[:max_chunks]

    def _is_pdf_doc(d: Dict[str, Any]) -> bool:
        src = str(d.get("source") or d.get("document_url") or d.get("url") or "").lower()
        dtype = str(d.get("document_type") or "").lower()
        return "pdf" in dtype or src.endswith(".pdf") or "/pdf" in src or bool(d.get("is_pdf"))

    rest_pdf = [d for d in rest if _is_pdf_doc(d)]
    rest_other = [d for d in rest if not _is_pdf_doc(d)]
    for extra in rest_pdf + rest_other:
        if len(out) >= max_chunks:
            break
        out.append(extra)
    return out


def package_myscheme_evidence(
    *,
    html: str = "",
    rendered_text: str = "",
    scheme_name: str = "",
    source_url: str = "",
    query: str = "",
    json_blobs: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Turn acquired myScheme page bytes/text into ingestible evidence.

    Discovering a URL is NOT success — this requires real section/factual text.
    """
    # Mine public JSON first — empty DOM + JSON detail is still success
    sections: Dict[str, str] = {}
    for blob in json_blobs or []:
        try:
            data = json.loads(blob) if isinstance(blob, str) else blob
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        # Common public field names on scheme APIs
        mapping = (
            ("details", ("details", "detail", "description", "overview", "about")),
            ("benefits", ("benefits", "benefit")),
            ("eligibility", ("eligibility", "eligibilityCriteria", "eligible")),
            ("application", ("applicationProcess", "application", "howToApply")),
            ("documents", ("documentsRequired", "documents", "requiredDocuments")),
            ("faqs", ("faqs", "faq", "frequentlyAskedQuestions")),
        )
        for key, names in mapping:
            if key in sections:
                continue
            for n in names:
                val = data.get(n)
                if isinstance(val, str) and len(val.strip()) >= 40:
                    sections[key] = val.strip()[:4000]
                    log_myscheme(
                        "MYSCHEME_NETWORK_DATA",
                        section=key,
                        chars=len(val),
                    )
                    break
                if isinstance(val, list) and val:
                    joined = "\n".join(str(x) for x in val[:40])
                    if len(joined) >= 40:
                        sections[key] = joined[:4000]
                        log_myscheme(
                            "MYSCHEME_NETWORK_DATA",
                            section=key,
                            chars=len(joined),
                        )
                        break

    # Extract visible sections before shell rejection — Network Error toasts
    # often remain in the DOM after real scheme panels hydrate.
    if html or rendered_text:
        for key, body in extract_scheme_sections(
            html, rendered_text=rendered_text
        ).items():
            if key not in sections or len(body) > len(sections.get(key) or ""):
                sections[key] = body

    shell, shell_reason = is_myscheme_shell_html(html, rendered_text=rendered_text)
    real_section_keys = [
        k
        for k in ("benefits", "eligibility", "application", "documents", "faqs", "details")
        if k in sections
        and len((sections.get(k) or "").strip()) >= 40
        and not any(
            m in (sections.get(k) or "").lower()
            for m in ("something went wrong", "network error", "please try again later")
        )
    ]
    # Error-toast shells may still hydrate real panels — require real sections.
    if shell and not real_section_keys:
        log_myscheme(
            "MYSCHEME_STATIC_SHELL",
            url=(source_url or "")[:160],
            reason=shell_reason,
        )
        return {
            "ok": False,
            "reason": shell_reason or "STATIC_SHELL",
            "is_shell": True,
            "sections": {},
            "content": None,
            "text_chars": 0,
        }

    name = scheme_name or extract_scheme_name_hint(query) or ""
    sid = (
        extract_scheme_id_from_url(source_url)
        or slug_hint_from_query(name)
        or slug_hint_from_query(query)
        or ""
    )
    canonical = canonical_myscheme_page_url(source_url, sid) if sid else (source_url or "")
    package = sections_as_evidence_text(
        sections,
        scheme_name=name,
        scheme_id=sid,
        canonical_url=canonical,
    )
    text = (rendered_text or "").strip()
    if not text and html:
        text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
        text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
        text = re.sub(r"(?is)<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

    # Reject chrome-only / nav-only blobs
    low = text.lower()
    has_scheme_signal = any(
        k in low
        for k in (
            "eligib",
            "benefit",
            "scheme",
            "yojana",
            "document",
            "application",
            "subsidy",
        )
    )
    chrome_only = (
        (len(text) < 60 and not sections)
        or (
            low.count("government of india")
            + low.count("privacy policy")
            + low.count("copyright")
            >= 2
            and len(sections) == 0
            and len(text) < 400
            and not has_scheme_signal
        )
    )
    if not package and chrome_only:
        return {
            "ok": False,
            "reason": "CONTENT_EMPTY",
            "is_shell": False,
            "sections": {},
            "content": None,
            "text_chars": len(text),
        }

    if not package and (len(text) >= 80 or (has_scheme_signal and len(text) >= 35)):
        # Usable body without clean headings — still valid HTML evidence
        sections = sections or {"details": text[:4000]}
        package = sections_as_evidence_text(
            sections,
            scheme_name=name,
            scheme_id=sid,
            canonical_url=canonical,
        )

    if not package or len(package) < 50:
        return {
            "ok": False,
            "reason": "CONTENT_EMPTY",
            "is_shell": False,
            "sections": sections,
            "content": None,
            "text_chars": len(text),
        }

    relevant = sections_meet_query_need(sections, query) or len(package) >= 300
    log_myscheme(
        "MYSCHEME_CONTENT_LENGTH",
        chars=len(package),
        sections=list(sections.keys()),
        url=(source_url or "")[:160],
    )
    log_myscheme(
        "MYSCHEME_CONTENT_RELEVANT",
        relevant=relevant,
        required=required_sections_for_query(query),
        found=list(sections.keys()),
    )
    log_myscheme(
        "MYSCHEME_EVIDENCE_PACKAGED",
        scheme_name=name,
        scheme_id=sid or None,
        chars=len(package),
        sections=list(sections.keys()),
        url=(source_url or "")[:160],
    )

    content = (
        f"<html><body><pre>{package}</pre></body></html>"
    ).encode("utf-8")
    return {
        "ok": True,
        "reason": "CONTENT_OK",
        "is_shell": False,
        "sections": sections,
        "content": content,
        "text_chars": len(package),
        "query_sufficient": relevant,
        "package_text": package,
        "scheme_id": sid,
        "scheme_name": name,
        "canonical_url": canonical,
    }


def discover_myscheme_scheme_links(
    base_url: str,
    html: str,
    *,
    verify_fn: Callable[[str], bool],
    query: str = "",
    limit: int = 8,
) -> List[Dict[str, Any]]:
    """Extract /schemes/... links from myScheme HTML (search, catalogue, or hub)."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    soup = BeautifulSoup(html or "", "html.parser")
    q_tokens = set(_query_tokens(query))
    q_key = normalize_scheme_key(extract_scheme_name_hint(query) or query)
    scored: List[tuple] = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        absolute = urljoin(base_url, href).split("#")[0]
        if absolute in seen:
            continue
        sid = extract_scheme_id_from_url(absolute)
        if not sid:
            continue
        if not verify_linked_url(absolute, verify_fn=verify_fn):
            continue
        if not is_myscheme_url(absolute):
            if not verify_fn(absolute):
                continue
        seen.add(absolute)
        text = (a.get_text(" ", strip=True) or "")[:200]
        name_key = normalize_scheme_key(text or sid)
        score = 5
        blob = f"{text} {absolute}".lower()
        for t in q_tokens:
            if t in blob:
                score += 3
        if q_key and name_key == q_key:
            score += 20
        elif q_key and len(q_key) >= 4 and (q_key in name_key or name_key in q_key):
            score += 16
        elif sid and q_key and (sid == q_key or sid in q_key.split() or q_key.replace(" ", "") == sid):
            score += 18
        elif q_key and SequenceMatcher(None, q_key, name_key).ratio() >= 0.82:
            score += 12
        # Soft filter only — final ranking rejects weak matches
        if q_key and len(q_key) >= 4 and score < 8:
            continue
        scored.append(
            (
                score,
                {
                    "url": absolute,
                    "link_text": text,
                    "kind": "scheme_page",
                    "scheme_name": text or sid,
                    "scheme_id": sid,
                    "stage": "myscheme_link",
                    "source": "myscheme",
                    "match_score": score,
                },
            )
        )

    scored.sort(key=lambda x: -x[0])
    out = [item for _, item in scored[: max(0, limit)]]
    for item in out[:3]:
        log_myscheme(
            "MYSCHEME_CANDIDATE",
            scheme_id=item.get("scheme_id"),
            scheme_name=(item.get("scheme_name") or "")[:80],
            score=item.get("match_score"),
        )
    return out


def extract_embedded_scheme_candidates(
    html: str,
    *,
    query: str = "",
    verify_fn: Optional[Callable[[str], bool]] = None,
) -> List[Dict[str, Any]]:
    """Pull scheme IDs/names from JSON blobs / Next data / regex (dynamic)."""
    raw = html or ""
    out: List[Dict[str, Any]] = []
    seen = set()
    q_key = normalize_scheme_key(extract_scheme_name_hint(query) or query)

    # /schemes/{id} anywhere in HTML/JSON
    for m in re.finditer(
        r"https?://(?:www\.)?myscheme\.gov\.in/schemes/([A-Za-z0-9][A-Za-z0-9\-_]{0,80})",
        raw,
        re.I,
    ):
        sid = m.group(1)
        url = build_myscheme_scheme_url(sid)
        if url in seen:
            continue
        if verify_fn and not verify_fn(url):
            continue
        seen.add(url)
        out.append(
            {
                "url": url,
                "scheme_id": sid,
                "scheme_name": sid,
                "kind": "scheme_page",
                "stage": "myscheme_embedded",
                "source": "myscheme",
            }
        )

    # Relative paths
    for m in re.finditer(r"[\"']/schemes/([A-Za-z0-9][A-Za-z0-9\-_]{0,80})[\"']", raw):
        sid = m.group(1)
        url = build_myscheme_scheme_url(sid)
        if url in seen:
            continue
        if verify_fn and not verify_fn(url):
            continue
        seen.add(url)
        out.append(
            {
                "url": url,
                "scheme_id": sid,
                "scheme_name": sid,
                "kind": "scheme_page",
                "stage": "myscheme_embedded",
                "source": "myscheme",
            }
        )

    # __NEXT_DATA__ / JSON objects with name + slug
    for blob_m in re.finditer(
        r"<script[^>]+id=[\"']__NEXT_DATA__[\"'][^>]*>(.*?)</script>",
        raw,
        re.I | re.S,
    ):
        try:
            data = json.loads(blob_m.group(1))
        except Exception:
            continue
        _walk_json_schemes(data, out, seen, verify_fn=verify_fn)

    # Rank by name similarity when query present (avoid short false substrings like "us")
    if q_key:
        ranked = []
        for c in out:
            sid = normalize_scheme_key(c.get("scheme_id") or "")
            name_key = normalize_scheme_key(c.get("scheme_name") or c.get("scheme_id") or "")
            score = SequenceMatcher(None, q_key, name_key).ratio()
            if q_key == name_key or (sid and q_key == sid):
                score = 1.0
            elif len(name_key) >= 4 and (q_key in name_key or name_key in q_key):
                score = max(score, 0.9)
            elif len(sid) >= 4 and (sid in q_key or q_key.replace(" ", "") == sid):
                score = max(score, 0.88)
            c = {**c, "match_score": round(score * 100)}
            if score >= 0.55:
                ranked.append(c)
        ranked.sort(key=lambda x: -float(x.get("match_score") or 0))
        return ranked[:12]
    return out[:12]


def _walk_json_schemes(
    obj: Any,
    out: List[Dict[str, Any]],
    seen: Set[str],
    *,
    verify_fn: Optional[Callable[[str], bool]],
    depth: int = 0,
) -> None:
    if depth > 8 or obj is None:
        return
    if isinstance(obj, dict):
        sid = (
            obj.get("schemeId")
            or obj.get("scheme_id")
            or obj.get("slug")
            or obj.get("id")
        )
        name = obj.get("schemeName") or obj.get("name") or obj.get("title")
        if sid and isinstance(sid, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9\-_]{0,80}", sid):
            url = build_myscheme_scheme_url(sid)
            if url not in seen and (not verify_fn or verify_fn(url)):
                seen.add(url)
                out.append(
                    {
                        "url": url,
                        "scheme_id": sid,
                        "scheme_name": str(name or sid)[:200],
                        "kind": "scheme_page",
                        "stage": "myscheme_json",
                        "source": "myscheme",
                    }
                )
        for v in list(obj.values())[:60]:
            _walk_json_schemes(v, out, seen, verify_fn=verify_fn, depth=depth + 1)
    elif isinstance(obj, list):
        for item in obj[:80]:
            _walk_json_schemes(item, out, seen, verify_fn=verify_fn, depth=depth + 1)


def rank_scheme_candidates(
    candidates: Sequence[Dict[str, Any]],
    query: str,
    *,
    state_hint: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Exact/alias/state-aware ranking; reject weak matches when a clear name exists."""
    q_hint = extract_scheme_name_hint(query) or query
    q_key = normalize_scheme_key(q_hint)
    prefer_ka = "karnataka" in (query or "").lower() or (state_hint or "").lower() == "karnataka"
    ranked: List[Dict[str, Any]] = []

    for c in candidates:
        name = c.get("scheme_name") or c.get("link_text") or c.get("scheme_id") or ""
        name_key = normalize_scheme_key(str(name))
        sid = (c.get("scheme_id") or extract_scheme_id_from_url(c.get("url") or "") or "").lower()
        score = float(c.get("match_score") or 0)
        if q_key and name_key == q_key:
            score += 50
        elif q_key and len(name_key) >= 4 and (q_key in name_key or name_key in q_key):
            score += 30
        else:
            score += SequenceMatcher(None, q_key, name_key).ratio() * 20
        # Alias boosts
        for canon, aliases in _NAME_ALIASES.items():
            if normalize_scheme_key(canon) == q_key or q_key == normalize_scheme_key(canon):
                if any(
                    normalize_scheme_key(a) == name_key
                    or (
                        len(normalize_scheme_key(a)) >= 4
                        and normalize_scheme_key(a) in name_key
                    )
                    for a in aliases
                ):
                    score += 25
        if prefer_ka and "karnataka" in f"{name} {c.get('url')}".lower():
            score += 8
        if sid and q_key and normalize_scheme_key(sid) == q_key:
            score += 15
        # Prefer alias/slug candidates already tagged
        if (c.get("stage") or "") in ("myscheme_alias", "myscheme_scheme") and score >= 40:
            score += 20
        item = {**c, "match_score": score, "scheme_id": sid or c.get("scheme_id")}
        # Hard reject weak matches when user named a scheme
        if q_key and len(q_key) >= 4 and score < 18:
            continue
        ranked.append(item)

    ranked.sort(key=lambda x: -float(x.get("match_score") or 0))
    return ranked


def load_discovery_cache() -> Dict[str, Any]:
    try:
        if not _DISCOVERY_CACHE_PATH.exists():
            return {"version": 1, "schemes": {}}
        data = json.loads(_DISCOVERY_CACHE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"version": 1, "schemes": {}}
        data.setdefault("schemes", {})
        return data
    except Exception:
        return {"version": 1, "schemes": {}}


def save_discovery_cache(data: Dict[str, Any]) -> None:
    try:
        _DISCOVERY_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _DISCOVERY_CACHE_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:  # noqa: BLE001
        logger.debug("myscheme discovery cache write failed: %s", type(e).__name__)


def lookup_discovery_cache(query: str) -> Optional[Dict[str, Any]]:
    """Return cached discovery metadata if fresh enough (not factual evidence)."""
    q_key = normalize_scheme_key(normalize_myscheme_search_query(query) or query)
    if not q_key:
        return None
    data = load_discovery_cache()
    schemes = data.get("schemes") or {}
    # Direct + alias keys
    entry = schemes.get(q_key)
    if not entry:
        for key, val in schemes.items():
            aliases = val.get("aliases") or []
            if q_key == key or q_key in [normalize_scheme_key(a) for a in aliases]:
                entry = val
                break
    if not entry:
        return None
    verified = float(entry.get("last_verified") or 0)
    if verified and (time.time() - verified) > _DISCOVERY_CACHE_TTL_SECONDS:
        return None
    sid = entry.get("scheme_id")
    url = entry.get("canonical_url") or (build_myscheme_scheme_url(sid) if sid else "")
    if not sid or not url:
        return None
    return {
        "scheme_name": entry.get("scheme_name") or sid,
        "normalized_name": q_key,
        "scheme_id": sid,
        "canonical_url": url,
        "url": url,
        "state": entry.get("state"),
        "ministry": entry.get("ministry"),
        "category": entry.get("category"),
        "source": "myscheme_cache",
        "stage": "myscheme_cache",
        "kind": "scheme_page",
        "confidence": float(entry.get("confidence") or 0.85),
        "match_score": 55,
    }


def remember_discovery_candidate(candidate: Dict[str, Any], *, query: str = "") -> None:
    """Persist discovery metadata after a successful resolve (not RAG content)."""
    sid = candidate.get("scheme_id") or extract_scheme_id_from_url(
        candidate.get("canonical_url") or candidate.get("url") or ""
    )
    if not sid:
        return
    name = candidate.get("scheme_name") or sid
    keys = {
        normalize_scheme_key(name),
        normalize_scheme_key(normalize_myscheme_search_query(query) or ""),
        normalize_scheme_key(sid),
    }
    keys.discard("")
    data = load_discovery_cache()
    schemes = data.setdefault("schemes", {})
    payload = {
        "scheme_name": name,
        "scheme_id": sid,
        "canonical_url": build_myscheme_scheme_url(sid),
        "state": candidate.get("state"),
        "ministry": candidate.get("ministry"),
        "category": candidate.get("category"),
        "aliases": sorted(k for k in keys if k != normalize_scheme_key(sid)),
        "confidence": float(candidate.get("confidence") or candidate.get("match_score") or 0),
        "last_verified": time.time(),
    }
    for k in keys:
        schemes[k] = {**schemes.get(k, {}), **payload}
    save_discovery_cache(data)


def collect_candidates_from_html(
    html: str,
    *,
    query: str,
    base_url: str,
    verify_fn: Callable[[str], bool],
    source_tag: str = "static",
) -> List[Dict[str, Any]]:
    """Extract ranked candidate objects from any myScheme/rules HTML/JSON blob."""
    links = discover_myscheme_scheme_links(
        base_url, html, verify_fn=verify_fn, query=query, limit=16
    )
    embedded = extract_embedded_scheme_candidates(
        html, query=query, verify_fn=verify_fn
    )
    merged = [{**c, "source": source_tag} for c in (links + embedded)]
    return rank_scheme_candidates(merged, query)


def candidate_to_ingest_row(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a discovery candidate for the live ingest loop."""
    sid = candidate.get("scheme_id") or extract_scheme_id_from_url(
        candidate.get("url") or candidate.get("canonical_url") or ""
    )
    url = candidate.get("canonical_url") or candidate.get("url") or (
        build_myscheme_scheme_url(sid) if sid else ""
    )
    return {
        "url": url,
        "canonical_url": url,
        "scheme_id": sid,
        "scheme_name": candidate.get("scheme_name") or sid,
        "link_text": candidate.get("scheme_name") or sid or "",
        "kind": "scheme_page",
        "stage": candidate.get("stage") or "myscheme_canonical",
        "source": "myscheme",
        "match_score": candidate.get("match_score") or candidate.get("confidence") or 0,
        "state": candidate.get("state"),
        "ministry": candidate.get("ministry"),
    }


def extract_candidates_from_json_text(
    text: str,
    *,
    query: str = "",
    verify_fn: Optional[Callable[[str], bool]] = None,
) -> List[Dict[str, Any]]:
    """Normalize public JSON/API search payloads into scheme candidate objects."""
    raw = (text or "").strip()
    if not raw:
        return []
    out: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    if raw[:1] in "{[":
        try:
            data = json.loads(raw)
            _walk_json_schemes(data, out, seen, verify_fn=verify_fn)
        except Exception:
            pass
    # Also mine /schemes/ URLs + name ranking via embedded path
    embedded = extract_embedded_scheme_candidates(
        raw if raw[:1] in "{[" else f"<script type=\"application/json\">{raw}</script>",
        query=query,
        verify_fn=verify_fn,
    )
    return merge_discovery_candidates(out, embedded) or rank_scheme_candidates(
        out, query
    )


def merge_discovery_candidates(
    *groups: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Deduplicate candidates by canonical scheme URL / id."""
    seen: Set[str] = set()
    out: List[Dict[str, Any]] = []
    for group in groups:
        for c in group or []:
            sid = c.get("scheme_id") or extract_scheme_id_from_url(
                c.get("url") or c.get("canonical_url") or ""
            )
            url = (c.get("canonical_url") or c.get("url") or "").split("?")[0]
            key = (sid or url or "").lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(dict(c))
    return out


def resolve_canonical_scheme(
    query: str,
    *,
    html: str = "",
    base_url: str = MYSCHEME_SEARCH,
    verify_fn: Callable[[str], bool],
) -> Optional[Dict[str, Any]]:
    """Resolve the best canonical https://www.myscheme.gov.in/schemes/{id} dynamically."""
    log_myscheme("MYSCHEME_DISCOVERY_START", query=(query or "")[:160])
    candidates: List[Dict[str, Any]] = []

    cached = lookup_discovery_cache(query)
    if cached and verify_fn(cached.get("url") or ""):
        candidates.append(cached)
        log_myscheme(
            "MYSCHEME_MATCH",
            strategy="cache",
            scheme_id=cached.get("scheme_id"),
        )

    # Known slug hint (catalog aliases only — not invented IDs)
    slug = slug_hint_from_query(query)
    if slug:
        url = build_myscheme_scheme_url(slug)
        if verify_fn(url):
            candidates.append(
                {
                    "url": url,
                    "scheme_id": slug,
                    "scheme_name": extract_scheme_name_hint(query) or slug,
                    "stage": "myscheme_alias",
                    "source": "myscheme",
                    "match_score": 40,
                }
            )
            log_myscheme("MYSCHEME_MATCH", strategy="alias", scheme_id=slug)

    if html:
        from_html = collect_candidates_from_html(
            html, query=query, base_url=base_url, verify_fn=verify_fn, source_tag="html"
        )
        candidates.extend(from_html)
        log_myscheme("MYSCHEME_SEARCH", candidates=len(from_html), base_url=base_url)

    ranked = rank_scheme_candidates(candidates, query)
    if not ranked:
        log_myscheme("MYSCHEME_MATCH", strategy="none", query=(query or "")[:80])
        return None

    best = ranked[0]
    sid = best.get("scheme_id") or extract_scheme_id_from_url(best.get("url") or "")
    if not sid:
        return None
    canonical = build_myscheme_scheme_url(sid)
    if not verify_fn(canonical) or not is_myscheme_url(canonical):
        log_myscheme("MYSCHEME_CANONICAL_URL", ok=False, scheme_id=sid)
        return None
    result = {
        **best,
        "scheme_id": sid,
        "url": canonical,
        "canonical_url": canonical,
        "kind": "scheme_page",
        "source": "myscheme",
        "stage": "myscheme_canonical",
    }
    remember_discovery_candidate(result, query=query)
    log_myscheme(
        "MYSCHEME_CANONICAL_URL",
        ok=True,
        scheme_id=sid,
        url=canonical,
        scheme_name=(result.get("scheme_name") or "")[:80],
        score=result.get("match_score"),
    )
    log_myscheme("MYSCHEME_MATCH", strategy=best.get("stage"), scheme_id=sid)
    return result


def build_myscheme_seeds_for_query(
    query: str,
    *,
    verify_fn: Callable[[str], bool],
    already: Optional[Set[str]] = None,
    limit: int = 6,
    include_search: bool = True,
) -> List[Dict[str, Any]]:
    """myScheme-first seeds: canonical (if known) + search + external + rules catalogue."""
    if not _looks_like_scheme_query(query):
        return []

    seen = set(already or set())
    out: List[Dict[str, Any]] = []
    log_myscheme("MYSCHEME_ACQUISITION_START", query=(query or "")[:160])
    log_myscheme("MYSCHEME_DISCOVERY_START", query=(query or "")[:160])

    def _add(seed: Dict[str, Any]) -> bool:
        url = seed.get("url") or ""
        if not url or url in seen or not verify_fn(url):
            return False
        if not is_myscheme_url(url):
            return False
        seen.add(url)
        out.append(seed)
        return True

    # A0) Discovery metadata cache (not RAG evidence)
    cached = lookup_discovery_cache(query)
    if cached and cached.get("url"):
        if _add(candidate_to_ingest_row(cached)):
            log_myscheme(
                "MYSCHEME_SCHEME_SEED",
                url=cached.get("url"),
                slug=cached.get("scheme_id"),
                source="cache",
            )

    # A) Known alias → canonical (still dynamic for unknowns)
    slug = slug_hint_from_query(query)
    if slug:
        url = build_myscheme_scheme_url(slug)
        if _add(
            {
                "url": url,
                "scheme_name": extract_scheme_name_hint(query) or slug,
                "scheme_id": slug,
                "link_text": slug,
                "stage": "myscheme_scheme",
                "source": "myscheme",
                "kind": "scheme_page",
            }
        ):
            log_myscheme("MYSCHEME_SCHEME_SEED", url=url, slug=slug)

    if include_search and len(out) < limit:
        variants = scheme_query_variants(query)
        # B) Internal search (primary variant)
        for variant in variants[:2]:
            search_url = build_myscheme_search_url(variant)
            if _add(
                {
                    "url": search_url,
                    "scheme_name": extract_scheme_name_hint(query) or "myScheme search",
                    "link_text": f"myScheme search: {variant}"[:120],
                    "stage": "myscheme_search",
                    "source": "myscheme",
                }
            ):
                log_myscheme("MYSCHEME_SEARCH", url=search_url, variant=variant[:80])
            if len(out) >= limit:
                break

        # C) External search
        if len(out) < limit and variants:
            ext = build_myscheme_external_search_url(variants[0])
            if _add(
                {
                    "url": ext,
                    "scheme_name": "myScheme external search",
                    "link_text": "myScheme external search",
                    "stage": "myscheme_external_search",
                    "source": "myscheme",
                }
            ):
                log_myscheme("MYSCHEME_SEARCH", url=ext, channel="external")

        # D) Eligibility / catalogue discovery index
        if len(out) < limit and verify_fn(MYSCHEME_RULES_HOME):
            if _add(
                {
                    "url": MYSCHEME_RULES_HOME,
                    "scheme_name": "myScheme eligibility catalogue",
                    "link_text": "myScheme rules / eligibility",
                    "stage": "myscheme_catalogue",
                    "source": "myscheme",
                }
            ):
                log_myscheme("MYSCHEME_CATALOGUE", url=MYSCHEME_RULES_HOME)

    return out[:limit]


def extract_tables_as_text(html: str) -> str:
    """Preserve HTML table structure as tab-separated rows for evidence."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return ""

    soup = BeautifulSoup(html or "", "html.parser")
    blocks: List[str] = []
    for table in soup.find_all("table"):
        rows: List[str] = []
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            cells = [c for c in cells if c]
            if cells:
                rows.append("\t".join(cells))
        if rows:
            blocks.append("TABLE:\n" + "\n".join(rows))
    return "\n\n".join(blocks).strip()


def discover_relevant_media(
    base_url: str,
    html: str,
    *,
    verify_fn: Callable[[str], bool],
    query: str = "",
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """Rank public images/audio/video; do not download every asset."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    if not is_myscheme_url(base_url):
        host = (urlparse(base_url).hostname or "").lower()
        if not is_myscheme_host(host):
            return []

    soup = BeautifulSoup(html or "", "html.parser")
    q_tokens = set(_query_tokens(query))
    scored: List[tuple] = []
    seen = set()

    def _score(url: str, *parts: str) -> int:
        blob = " ".join([url, *parts]).lower()
        s = 0
        for t in q_tokens:
            if t in blob:
                s += 4
        for hint in (
            "scheme",
            "eligib",
            "benefit",
            "guideline",
            "infographic",
            "poster",
            "faq",
            "document",
        ):
            if hint in blob:
                s += 2
        return s

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src:
            continue
        absolute = urljoin(base_url, src).split("#")[0]
        if absolute in seen:
            continue
        lower = absolute.lower().split("?")[0]
        if not any(lower.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp")):
            continue
        if not verify_linked_url(absolute, verify_fn=verify_fn):
            continue
        alt = img.get("alt") or ""
        score = _score(absolute, alt, img.get("title") or "")
        if score < 4:
            continue
        seen.add(absolute)
        scored.append(
            (
                score,
                {
                    "url": absolute,
                    "link_text": alt[:200],
                    "kind": "image",
                    "stage": "myscheme_media",
                },
            )
        )

    for tag in soup.find_all(["audio", "video", "source"]):
        src = tag.get("src") or ""
        if not src:
            continue
        absolute = urljoin(base_url, src).split("#")[0]
        if absolute in seen:
            continue
        lower = absolute.lower().split("?")[0]
        kind = None
        if any(lower.endswith(ext) for ext in (".mp3", ".wav", ".m4a", ".aac", ".ogg")):
            kind = "audio"
        elif any(lower.endswith(ext) for ext in (".mp4", ".webm", ".m4v")):
            kind = "video"
        if not kind:
            continue
        if not verify_linked_url(absolute, verify_fn=verify_fn):
            continue
        score = _score(absolute, tag.get("title") or "")
        if score < 2 and not q_tokens:
            score = 3
        if score < 2:
            continue
        seen.add(absolute)
        scored.append(
            (
                score,
                {
                    "url": absolute,
                    "link_text": kind,
                    "kind": kind,
                    "stage": "myscheme_media",
                },
            )
        )

    scored.sort(key=lambda x: -x[0])
    out = [item for _, item in scored[: max(0, limit)]]
    for item in out:
        if item["kind"] == "image":
            log_myscheme("MYSCHEME_IMAGE_FOUND", url=item["url"])
        elif item["kind"] == "audio":
            log_myscheme("MYSCHEME_AUDIO_FOUND", url=item["url"])
        elif item["kind"] == "video":
            log_myscheme("MYSCHEME_VIDEO_FOUND", url=item["url"])
    return out


def ocr_image_bytes_to_text(content: bytes, *, max_chars: int = 8000) -> str:
    """OCR a public image into text for existing .txt ingest (best-effort)."""
    if not content:
        return ""
    try:
        from rapidocr_onnxruntime import RapidOCR
        from io import BytesIO
        from PIL import Image
    except Exception:
        return ""
    try:
        img = Image.open(BytesIO(content)).convert("RGB")
        ocr = RapidOCR()
        result, _ = ocr(img)
        if not result:
            return ""
        lines = []
        for item in result:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                lines.append(str(item[1]))
        text = "\n".join(lines).strip()
        if text:
            log_myscheme("MYSCHEME_OCR_SUCCESS", chars=len(text))
            log_myscheme("MYSCHEME_OCR", chars=len(text), ok=True)
        return text[:max_chars]
    except Exception as e:  # noqa: BLE001
        log_myscheme("MYSCHEME_FAILURE", reason="ocr_failed", err=type(e).__name__)
        log_myscheme("MYSCHEME_OCR", ok=False, reason="ocr_failed")
        return ""


def transcribe_public_audio_bytes(
    content: bytes,
    *,
    filename: str = "media.mp3",
) -> Dict[str, Any]:
    """Use existing STT stack for public government audio (not citizen mic)."""
    if not content:
        return {"success": False, "text": ""}
    try:
        from app.services.voice.stt_service import transcribe_audio

        out = transcribe_audio(content, filename=filename)
        if out.get("success") and (out.get("text") or "").strip():
            log_myscheme(
                "MYSCHEME_STT_SUCCESS",
                chars=len(out.get("text") or ""),
                language=out.get("detected_language"),
            )
        return out
    except Exception as e:  # noqa: BLE001
        log_myscheme("MYSCHEME_FAILURE", reason="stt_failed", err=type(e).__name__)
        return {"success": False, "text": "", "error": type(e).__name__}


def public_api_to_evidence_text(data: Any, *, source_url: str = "") -> str:
    """Normalize public JSON into readable evidence text."""
    try:
        if isinstance(data, (bytes, bytearray)):
            data = json.loads(data.decode("utf-8", errors="ignore"))
        elif isinstance(data, str):
            data = json.loads(data)
    except Exception:
        return ""

    lines: List[str] = []
    if source_url:
        lines.append(f"Source URL: {source_url}")
        lines.append("Content-Type: application/json")

    def _walk(obj: Any, prefix: str = "") -> None:
        if isinstance(obj, dict):
            for k, v in list(obj.items())[:80]:
                key = str(k)
                if isinstance(v, (dict, list)):
                    _walk(v, prefix=f"{prefix}{key}.")
                else:
                    val = str(v).strip()
                    if val and len(val) < 500:
                        lines.append(f"{prefix}{key}: {val}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj[:40]):
                _walk(item, prefix=f"{prefix}[{i}].")

    _walk(data)
    text = "\n".join(lines).strip()
    if text:
        log_myscheme("MYSCHEME_API_DISCOVERED", chars=len(text), url=source_url)
    return text
