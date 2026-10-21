#!/usr/bin/env python3
"""CLI: Karnataka myScheme PDF crawler (discover → PDF → Supabase → RAG metadata)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database.session import SessionLocal
from app.models import audit, citizen_account, conversation, rag, user  # noqa: F401
from app.services.myscheme_karnataka_crawler.runner import KarnatakaCrawler

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Karnataka myScheme PDF crawler")
    parser.add_argument("--dry-run", action="store_true", help="Discover + rank PDFs only; no upload")
    parser.add_argument("--limit", type=int, default=None, help="Process at most N schemes")
    parser.add_argument("--resume", action="store_true", help="Skip schemes already UPLOADED/DOWNLOADED")
    parser.add_argument("--scheme", dest="scheme_id", default=None, help="Process a single scheme slug")
    parser.add_argument("--state", default="Karnataka", help="State label (discovery uses Karnataka filter)")
    parser.add_argument("--recheck", action="store_true", help="Re-process even if previously completed")
    parser.add_argument(
        "--cleanup-duplicates",
        action="store_true",
        help="Execute safe duplicate cleanup by SHA-256 (requires DB)",
    )
    parser.add_argument(
        "--cleanup-duplicates-dry-run",
        action="store_true",
        help="Show duplicate SHA-256 groups without deleting",
    )
    parser.add_argument("--report", action="store_true", help="Only regenerate report from last crawl state")
    parser.add_argument("--build-index", action="store_true", help="Rebuild FAISS/BM25 after ingest")
    args = parser.parse_args()

    db = None
    if not args.dry_run or args.cleanup_duplicates or args.cleanup_duplicates_dry_run:
        db = SessionLocal()

    crawler = KarnatakaCrawler(db=db)

    try:
        if args.cleanup_duplicates_dry_run:
            plan = crawler.cleanup_duplicates(execute=False)
            print(json.dumps(plan, indent=2))
            return 0
        if args.cleanup_duplicates:
            plan = crawler.cleanup_duplicates(execute=True)
            print(json.dumps({"cleaned_groups": len(plan)}, indent=2))
            return 0

        report = crawler.run(
            dry_run=args.dry_run,
            limit=args.limit,
            resume=args.resume,
            recheck=args.recheck,
            scheme_id=args.scheme_id,
            build_index=args.build_index,
        )

        print(json.dumps({k: report[k] for k in report if k != "failures"}, indent=2))
        if args.dry_run:
            schemes = json.loads(
                (BACKEND_ROOT / "data" / "myscheme" / "karnataka" / "schemes.json").read_text(encoding="utf-8")
            )
            with_pdf = [s for s in schemes if s.get("canonical_pdf_url")]
            no_pdf = [s for s in schemes if s.get("pdf_status") == "NO_PDF"]
            print(f"\nKarnataka schemes discovered: {len(schemes)}")
            print(f"Schemes with candidate PDFs: {len(with_pdf)}")
            print(f"Schemes with no PDFs: {len(no_pdf)}\n")
            for s in schemes[: min(10, len(schemes))]:
                print(f"- {s.get('scheme_name')} ({s.get('scheme_id')})")
                print(f"  URL: {s.get('scheme_url')}")
                print(f"  candidates: {len(s.get('candidate_pdfs') or [])}")
                print(f"  canonical: {s.get('canonical_pdf_url')}\n")
        return 0
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    raise SystemExit(main())
