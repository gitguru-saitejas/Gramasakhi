from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.myscheme_karnataka_crawler import compress, detail, discovery, pdf_rank, pdf_validate
from app.services.myscheme_karnataka_crawler.cleanup import execute_duplicate_cleanup, plan_duplicate_cleanup
from app.services.myscheme_karnataka_crawler.config import (
    REQUEST_DELAY_SECONDS,
    STORAGE_PREFIX,
)
from app.services.myscheme_karnataka_crawler.db_ops import find_canonical_for_scheme, find_document_by_hash
from app.services.myscheme_karnataka_crawler.http_client import RespectfulHttpClient
from app.services.myscheme_karnataka_crawler.report import build_report, write_reports
from app.services.myscheme_karnataka_crawler.state_store import (
    load_schemes,
    merge_discovered,
    save_schemes,
    scheme_by_id,
)
from app.services.rag import ingest_raw_bytes

logger = logging.getLogger("gramsakhi.myscheme_crawler")

SKIP_STATUSES = frozenset({"UPLOADED", "DOWNLOADED", "HTML_ONLY", "NO_PDF"})


class KarnatakaCrawler:
    def __init__(self, db: Optional[Session] = None, *, delay: float = REQUEST_DELAY_SECONDS):
        self.db = db
        self.client = RespectfulHttpClient(delay_seconds=delay)
        self.stats: Dict[str, Any] = {
            "schemes_discovered": 0,
            "schemes_processed": 0,
            "schemes_with_pdf": 0,
            "schemes_no_pdf": 0,
            "schemes_html_only": 0,
            "candidate_pdfs": 0,
            "valid_pdfs": 0,
            "invalid_pdfs": 0,
            "unique_pdfs": 0,
            "duplicate_pdfs": 0,
            "uploaded": 0,
            "reused_existing": 0,
            "failed": 0,
            "original_bytes": 0,
            "final_bytes": 0,
            "compression_saved": 0,
            "pages_processed": 0,
            "largest_pdf": 0,
            "avg_pdf_size": 0,
            "pagination_pages_fetched": 0,
            "duplicate_scheme_ids_skipped": 0,
            "api_total_reported": None,
            "documents_ingested": 0,
            "chunks_generated": 0,
        }
        self.failures: List[Dict[str, Any]] = []
        self._size_samples: List[int] = []

    def discover_and_save(self) -> List[Dict[str, Any]]:
        fresh, meta = discovery.discover_karnataka_schemes(self.client)
        merged = merge_discovered(load_schemes(), fresh)
        save_schemes(merged)
        self.stats["schemes_discovered"] = len(merged)
        self.stats["pagination_pages_fetched"] = meta.get("pagination_pages_fetched", 0)
        self.stats["duplicate_scheme_ids_skipped"] = meta.get("duplicate_scheme_ids_skipped", 0)
        self.stats["api_total_reported"] = meta.get("api_total_reported")
        return merged

    def _should_process(self, rec: Dict[str, Any], *, resume: bool, recheck: bool) -> bool:
        if recheck:
            return True
        if resume and rec.get("status") in SKIP_STATUSES:
            return False
        return True

    def process_scheme(
        self,
        rec: Dict[str, Any],
        *,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        slug = rec.get("scheme_id") or rec.get("slug")
        rec["status"] = "PROCESSING"
        try:
            meta, candidates, html_only = detail.fetch_scheme_detail(self.client, slug)
            rec["scheme_name"] = meta.get("scheme_name") or rec.get("scheme_name")
            rec["ministry"] = meta.get("ministry") or rec.get("ministry")
            rec["candidate_pdfs"] = candidates
            self.stats["candidate_pdfs"] += len(candidates)

            if html_only and not candidates:
                rec["pdf_status"] = "HTML_ONLY"
                rec["status"] = "HTML_ONLY"
                self.stats["schemes_html_only"] += 1
                return rec

            chosen = pdf_rank.select_canonical_pdf(candidates)
            if not chosen:
                rec["pdf_status"] = "NO_PDF"
                rec["status"] = "NO_PDF"
                self.stats["schemes_no_pdf"] += 1
                return rec

            rec["canonical_pdf_url"] = chosen["url"]
            rec["canonical_pdf_score"] = pdf_rank.score_pdf_candidate(chosen)

            if dry_run:
                rec["pdf_status"] = "DRY_RUN"
                rec["status"] = "PENDING"
                self.stats["schemes_with_pdf"] += 1
                return rec

            dl = pdf_validate.download_and_validate_pdf(self.client, chosen["url"])
            if not dl.get("ok"):
                rec["pdf_status"] = "FAILED"
                rec["status"] = "FAILED"
                rec["error"] = dl.get("error")
                self.stats["invalid_pdfs"] += 1
                self.stats["failed"] += 1
                self.failures.append(
                    {
                        "scheme_id": slug,
                        "scheme_name": rec.get("scheme_name"),
                        "url": rec.get("scheme_url"),
                        "error": dl.get("error"),
                    }
                )
                return rec

            self.stats["valid_pdfs"] += 1
            data = dl["data"]
            digest = dl["sha256"]
            pages = dl["page_count"]
            self.stats["pages_processed"] += pages

            final_data, orig, saved = compress.try_lossless_compress_pdf(data)
            self.stats["original_bytes"] += orig
            self.stats["final_bytes"] += len(final_data)
            self.stats["compression_saved"] += saved
            self._size_samples.append(len(final_data))
            if len(final_data) > self.stats["largest_pdf"]:
                self.stats["largest_pdf"] = len(final_data)

            hash_prefix = digest[:8]
            storage_path = f"{STORAGE_PREFIX}/{slug}_{hash_prefix}.pdf"

            if self.db:
                existing = find_document_by_hash(self.db, digest)
                if existing:
                    rec["pdf_status"] = "REUSED_HASH"
                    rec["status"] = "UPLOADED"
                    rec["sha256"] = digest
                    rec["storage_path"] = existing.file_url
                    rec["document_id"] = str(existing.id)
                    self.stats["reused_existing"] += 1
                    self.stats["duplicate_pdfs"] += 1
                    self.stats["schemes_with_pdf"] += 1
                    self.stats["documents_ingested"] += 1
                    return rec

                prior = find_canonical_for_scheme(self.db, slug)
                if prior and prior.document_hash == digest:
                    rec["pdf_status"] = "UNCHANGED"
                    rec["status"] = "UPLOADED"
                    rec["sha256"] = digest
                    rec["storage_path"] = prior.file_url
                    rec["document_id"] = str(prior.id)
                    self.stats["reused_existing"] += 1
                    self.stats["schemes_with_pdf"] += 1
                    return rec

            extra = {
                "scheme_id": slug,
                "canonical_url": rec.get("scheme_url"),
                "document_url": chosen["url"],
                "source_type": "myscheme",
                "ingestion_type": "myscheme_crawler",
                "pdf_status": "DOWNLOADED",
                "is_canonical": True,
                "page_count": pages,
            }
            if self.db:
                doc = ingest_raw_bytes(
                    self.db,
                    uploaded_by=None,
                    title=rec.get("scheme_name") or slug,
                    category="GOVERNMENT_SCHEMES",
                    version="1.0",
                    contents=final_data,
                    ext=".pdf",
                    scheme_name=rec.get("scheme_name"),
                    ministry=rec.get("ministry"),
                    state="Karnataka",
                    source=rec.get("source_url"),
                    language="en",
                    document_type="scheme_pdf",
                    extra_metadata=extra,
                    document_hash=digest,
                    storage_path=storage_path,
                )
                rec["document_id"] = str(doc.id)
                rec["storage_path"] = doc.file_url
                self.stats["uploaded"] += 1
                self.stats["documents_ingested"] += 1
                try:
                    self.stats["chunks_generated"] += len(doc.chunks or [])
                except Exception:
                    pass
            else:
                rec["storage_path"] = storage_path

            rec["sha256"] = digest
            rec["size_bytes"] = len(final_data)
            rec["page_count"] = pages
            rec["pdf_status"] = "DOWNLOADED"
            rec["status"] = "UPLOADED"
            self.stats["unique_pdfs"] += 1
            self.stats["schemes_with_pdf"] += 1
            return rec
        except Exception as e:
            rec["status"] = "FAILED"
            rec["pdf_status"] = "FAILED"
            rec["error"] = str(e)
            self.stats["failed"] += 1
            self.failures.append(
                {
                    "scheme_id": slug,
                    "scheme_name": rec.get("scheme_name"),
                    "url": rec.get("scheme_url"),
                    "error": str(e),
                }
            )
            return rec

    def run(
        self,
        *,
        dry_run: bool = False,
        limit: Optional[int] = None,
        resume: bool = False,
        recheck: bool = False,
        scheme_id: Optional[str] = None,
        build_index: bool = False,
    ) -> Dict[str, Any]:
        schemes = self.discover_and_save()
        if scheme_id:
            one = scheme_by_id(schemes, scheme_id)
            schemes = [one] if one else [{"scheme_id": scheme_id, "scheme_url": f"https://www.myscheme.gov.in/schemes/{scheme_id}", "status": "PENDING"}]

        processed = 0
        for idx, rec in enumerate(schemes):
            if limit is not None and processed >= limit:
                break
            if not self._should_process(rec, resume=resume, recheck=recheck):
                continue
            self.process_scheme(rec, dry_run=dry_run)
            schemes[idx] = rec
            processed += 1
            self.stats["schemes_processed"] += 1
            save_schemes(schemes)

        if self._size_samples:
            self.stats["avg_pdf_size"] = int(sum(self._size_samples) / len(self._size_samples))

        if build_index and self.db and not dry_run:
            from app.services.index_builder import IndexBuilder

            try:
                IndexBuilder().build_all(self.db)
                self.stats["faiss_status"] = "built"
                self.stats["bm25_status"] = "built"
            except Exception as e:
                self.stats["faiss_status"] = "failed"
                self.stats["bm25_status"] = "failed"
                self.failures.append({"stage": "INDEXING", "error": str(e)})
                raise

        report = build_report(self.stats, self.failures)
        write_reports(report)
        return report

    def cleanup_duplicates(self, *, execute: bool = False) -> List[Dict[str, Any]]:
        if not self.db:
            raise RuntimeError("Database session required for duplicate cleanup")
        plan = plan_duplicate_cleanup(self.db)
        if execute:
            execute_duplicate_cleanup(self.db, plan)
        return plan
