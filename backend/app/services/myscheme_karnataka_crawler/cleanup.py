from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.rag import RagDocument
from app.services.myscheme_karnataka_crawler.db_ops import duplicate_hash_groups
from app.services.storage import delete_rag_document


def plan_duplicate_cleanup(db: Session) -> List[Dict[str, Any]]:
    """Dry-run plan: identical document_hash groups."""
    groups = duplicate_hash_groups(db)
    plan: List[Dict[str, Any]] = []
    for digest, docs in sorted(groups.items()):
        docs_sorted = sorted(docs, key=lambda d: (d.created_at or d.updated_at))
        canonical = docs_sorted[0]
        duplicates = docs_sorted[1:]
        plan.append(
            {
                "hash": digest,
                "canonical_document_id": str(canonical.id),
                "canonical_storage_path": canonical.file_url,
                "duplicates": [
                    {"document_id": str(d.id), "storage_path": d.file_url, "source": d.source}
                    for d in duplicates
                ],
            }
        )
    return plan


def execute_duplicate_cleanup(db: Session, plan: List[Dict[str, Any]]) -> Dict[str, int]:
    deleted = 0
    updated = 0
    for entry in plan:
        canonical_id = entry["canonical_document_id"]
        for dup in entry.get("duplicates") or []:
            doc = db.query(RagDocument).filter_by(id=dup["document_id"]).first()
            if not doc:
                continue
            # Repoint is out of scope for minimal cleanup — delete redundant copies only
            path = dup.get("storage_path")
            if path and path != entry.get("canonical_storage_path"):
                try:
                    delete_rag_document(path)
                except Exception:
                    pass
            db.delete(doc)
            deleted += 1
        updated += 1
    db.commit()
    return {"groups": len(plan), "documents_deleted": deleted}
