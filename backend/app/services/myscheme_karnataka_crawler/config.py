from __future__ import annotations

import os
from pathlib import Path

# Public SPA key (same as myScheme web client); override via env for rotation.
DEFAULT_MYSCHEME_API_KEY = os.environ.get(
    "MYSCHEME_PUBLIC_API_KEY",
    "tYTy5eEhlu9rFjyxuCr7ra7ACp4dv1RH8gWuHTDc",
)

BACKEND_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = BACKEND_ROOT / "data" / "myscheme" / "karnataka"
SCHEMES_JSON = DATA_DIR / "schemes.json"
STATE_JSON = DATA_DIR / "crawl_state.json"
REPORT_JSON = DATA_DIR / "crawl_report.json"
REPORT_MD = DATA_DIR / "crawl_report.md"
WORK_DIR = DATA_DIR / "work"

MYSCHEME_API_ORIGIN = "https://api.myscheme.gov.in"
MYSCHEME_WEB_ORIGIN = "https://www.myscheme.gov.in"

USER_AGENT = "GramSakhiMySchemeCrawler/1.0 (+research; respectful; local)"

REQUEST_DELAY_SECONDS = float(os.environ.get("MYSCHEME_CRAWL_DELAY", "1.0"))
REQUEST_TIMEOUT_SECONDS = float(os.environ.get("MYSCHEME_CRAWL_TIMEOUT", "45"))
MAX_RETRIES = int(os.environ.get("MYSCHEME_CRAWL_MAX_RETRIES", "4"))
MAX_PDF_BYTES = int(float(os.environ.get("MYSCHEME_CRAWL_MAX_PDF_MB", "15")) * 1024 * 1024)
PAGE_SIZE = int(os.environ.get("MYSCHEME_CRAWL_PAGE_SIZE", "100"))
MAX_CONCURRENT = 1  # sequential by design

KARNATAKA_FILTER = [
    {"identifier": "beneficiaryState", "value": "Karnataka"},
]

STORAGE_PREFIX = "scheme-documents/karnataka"
