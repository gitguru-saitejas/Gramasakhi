from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

from app.services.myscheme_karnataka_crawler.config import (
    DEFAULT_MYSCHEME_API_KEY,
    MYSCHEME_API_ORIGIN,
    MYSCHEME_WEB_ORIGIN,
    REQUEST_TIMEOUT_SECONDS,
    USER_AGENT,
)


class RespectfulHttpClient:
    def __init__(
        self,
        *,
        delay_seconds: float = 1.0,
        max_retries: int = 4,
        api_key: Optional[str] = None,
    ):
        self.delay_seconds = max(0.0, delay_seconds)
        self.max_retries = max(1, max_retries)
        self.api_key = api_key or DEFAULT_MYSCHEME_API_KEY
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)

    def get_bytes(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        myscheme_api: bool = False,
    ) -> Tuple[bytes, str, int]:
        hdrs = {"User-Agent": USER_AGENT, "Accept": "*/*"}
        if myscheme_api:
            hdrs["x-api-key"] = self.api_key
            hdrs["Accept"] = "application/json"
            hdrs["Origin"] = MYSCHEME_WEB_ORIGIN
        if headers:
            hdrs.update(headers)

        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries):
            self._throttle()
            req = urllib.request.Request(url, headers=hdrs, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                    self._last_request_at = time.monotonic()
                    body = resp.read()
                    ctype = resp.headers.get("Content-Type", "")
                    return body, ctype, resp.status
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code in (429, 500, 502, 503, 504) and attempt + 1 < self.max_retries:
                    time.sleep(min(30.0, 2**attempt))
                    continue
                raise
            except Exception as e:
                last_err = e
                if attempt + 1 < self.max_retries:
                    time.sleep(min(30.0, 2**attempt))
                    continue
                raise
        raise last_err or RuntimeError("request failed")

    def get_json(self, path: str, *, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        q = urllib.parse.urlencode(params or {})
        url = f"{MYSCHEME_API_ORIGIN}{path}"
        if q:
            url = f"{url}?{q}"
        raw, _, _ = self.get_bytes(url, myscheme_api=True)
        return json.loads(raw.decode("utf-8"))
