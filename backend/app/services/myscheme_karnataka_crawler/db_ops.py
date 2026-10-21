from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.rag import DocumentChunk, RagDocument
from app.services.web_ingestion_service import compute_hash


def find_document_by_hash(db: Session, sha256: str) -> Optional[RagDocument]:
    if not sha256:
        return None
    return db.query(RagDocument).filter(RagDocument.document_hash == sha256).first()


def find_canonical_for_scheme(db: Session, scheme_id: str) -> Optional[RagDocument]:
    """One canonical ingest per myScheme slug (source URL ends with /schemes/{id})."""
    suffix = f"/schemes/{scheme_id}"
    return (
        db.query(RagDocument)
        .filter(RagDocument.source.isnot(None))
        .filter(RagDocument.source.like(f"%{suffix}"))
        .order_by(RagDocument.updated_at.desc())
        .first()
    )


def list_documents_with_hash(db: Session) -> List[RagDocument]:
    return (
        db.query(RagDocument)
        .filter(RagDocument.document_hash.isnot(None))
        .all()
    )


def duplicate_hash_groups(db: Session) -> Dict[str, List[RagDocument]]:
    groups: Dict[str, List[RagDocument]] = {}
    for doc in list_documents_with_hash(db):
        h = doc.document_hash or ""
        if not h:
            continue
        groups.setdefault(h, []).append(doc)
    return {h: docs for h, docs in groups.items() if len(docs) > 1}
