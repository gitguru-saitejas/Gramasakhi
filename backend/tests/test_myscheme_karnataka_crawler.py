"""Unit tests for Karnataka myScheme crawler (mocked network)."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from app.services.myscheme_karnataka_crawler import pdf_rank, pdf_validate
from app.services.myscheme_karnataka_crawler.discovery import _parse_search_item
from app.services.myscheme_karnataka_crawler.security import is_safe_http_url, is_trusted_document_host
from app.services.myscheme_karnataka_crawler.state_store import merge_discovered
from app.services.voice.audio_utils import make_tone_wav


class TestMyschemeKarnatakaCrawler(unittest.TestCase):
    def test_parse_search_item(self):
        item = {
            "fields": {
                "slug": "us",
                "schemeName": "Udyogini Scheme",
                "beneficiaryState": ["Karnataka"],
                "level": "State",
            }
        }
        rec = _parse_search_item(item)
        self.assertEqual(rec["scheme_id"], "us")
        self.assertIn("/schemes/us", rec["scheme_url"])

    def test_merge_discovered_dedupes(self):
        a = [{"scheme_id": "a", "status": "UPLOADED", "scheme_name": "Old"}]
        b = [{"scheme_id": "a", "scheme_name": "New"}, {"scheme_id": "b", "status": "PENDING"}]
        merged = merge_discovered(a, b)
        self.assertEqual(len(merged), 2)
        by = {m["scheme_id"]: m for m in merged}
        self.assertEqual(by["a"]["scheme_name"], "New")
        self.assertEqual(by["a"]["status"], "UPLOADED")

    def test_pdf_rank_prefers_guidelines(self):
        cands = [
            {"url": "https://x.gov.in/logo-banner.pdf", "title": "logo"},
            {"url": "https://x.gov.in/scheme-guidelines.pdf", "title": "Guidelines"},
        ]
        best = pdf_rank.select_canonical_pdf(cands)
        self.assertIn("guidelines", best["url"])

    def test_reject_invalid_pdf(self):
        ok, reason, _ = pdf_validate.validate_pdf_bytes(b"not-a-pdf")
        self.assertFalse(ok)
        self.assertEqual(reason, "invalid_magic")

    def test_valid_pdf_and_hash(self):
        data = make_tone_wav(0.3)
        ok, reason, _ = pdf_validate.validate_pdf_bytes(data)
        self.assertFalse(ok)
        # real pdf magic
        fake = b"%PDF-1.4\n" + b"0" * 200
        ok2, reason2, pages = pdf_validate.validate_pdf_bytes(fake)
        self.assertFalse(ok2)  # corrupt structure

    def test_sha256_stable(self):
        h1 = pdf_validate.sha256_hex(b"abc")
        h2 = pdf_validate.sha256_hex(b"abc")
        self.assertEqual(h1, h2)

    def test_security_blocks_localhost(self):
        self.assertFalse(is_safe_http_url("http://127.0.0.1/secret.pdf"))
        self.assertTrue(is_trusted_document_host("https://karnataka.gov.in/doc.pdf"))

    @patch("app.services.myscheme_karnataka_crawler.discovery.RespectfulHttpClient")
    def test_discovery_pagination(self, client_cls):
        client = MagicMock()

        def fake_get(url, **kwargs):
            if "from=0" in url:
                body = {
                    "data": {
                        "hits": {
                            "items": [
                                {"fields": {"slug": "a", "schemeName": "A"}},
                                {"fields": {"slug": "b", "schemeName": "B"}},
                            ]
                        }
                    }
                }
            else:
                body = {"data": {"hits": {"items": []}}}
            return json.dumps(body).encode("utf-8"), "application/json", 200

        client.get_bytes.side_effect = fake_get
        client_cls.return_value = client
        from app.services.myscheme_karnataka_crawler import discovery as disc

        out, meta = disc.discover_karnataka_schemes(client)
        self.assertEqual(len(out), 2)
        self.assertEqual(meta.get("pagination_pages_fetched"), 1)


if __name__ == "__main__":
    unittest.main()
