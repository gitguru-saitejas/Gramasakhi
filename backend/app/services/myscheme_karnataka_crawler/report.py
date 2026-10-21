from __future__ import annotations

import json
from typing import Any, Dict, List

from app.services.myscheme_karnataka_crawler.config import REPORT_JSON, REPORT_MD


def build_report(stats: Dict[str, Any], failures: List[Dict[str, Any]]) -> Dict[str, Any]:
    report = {
        **stats,
        "failures": failures,
    }
    return report


def write_reports(report: Dict[str, Any]) -> None:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Karnataka myScheme crawl report",
        "",
        f"- Total Karnataka schemes discovered: **{report.get('schemes_discovered', 0)}**",
        f"- Total schemes processed: **{report.get('schemes_processed', 0)}**",
        f"- Schemes with PDFs: **{report.get('schemes_with_pdf', 0)}**",
        f"- Schemes without PDFs: **{report.get('schemes_no_pdf', 0)}**",
        f"- HTML-only schemes: **{report.get('schemes_html_only', 0)}**",
        f"- Candidate PDFs seen: **{report.get('candidate_pdfs', 0)}**",
        f"- Valid PDFs: **{report.get('valid_pdfs', 0)}**",
        f"- Invalid PDFs: **{report.get('invalid_pdfs', 0)}**",
        f"- Unique PDFs (by hash): **{report.get('unique_pdfs', 0)}**",
        f"- Duplicate PDFs skipped: **{report.get('duplicate_pdfs', 0)}**",
        f"- Uploaded: **{report.get('uploaded', 0)}**",
        f"- Reused existing storage: **{report.get('reused_existing', 0)}**",
        f"- Failed: **{report.get('failed', 0)}**",
        f"- Original storage bytes: **{report.get('original_bytes', 0)}**",
        f"- Final storage bytes: **{report.get('final_bytes', 0)}**",
        f"- Storage saved by compression: **{report.get('compression_saved', 0)}**",
        f"- Average PDF size: **{report.get('avg_pdf_size', 0)}**",
        f"- Largest PDF: **{report.get('largest_pdf', 0)}** bytes",
        f"- Pages processed: **{report.get('pages_processed', 0)}**",
        "",
    ]
    fails = report.get("failures") or []
    if fails:
        lines.append("## Failures")
        lines.append("")
        for f in fails[:200]:
            lines.append(
                f"- `{f.get('scheme_id')}` **{f.get('scheme_name')}** — {f.get('error')} ({f.get('url')})"
            )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
