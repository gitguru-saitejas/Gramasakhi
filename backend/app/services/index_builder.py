"""
Build FAISS + BM25 indexes from already-ingested DB chunks.

Does not re-run embeddings — reads vectors stored by ingest_raw_bytes.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.rag import DocumentChunk, RagDocument
from app.services.bm25_index import BM25Index
from app.services.faiss_index import FaissIndex

logger = logging.getLogger("gramsakhi.index_builder")


def default_index_dir() -> Path:
    """Resolve hybrid index dir relative to backend/ when not absolute (CWD-safe)."""
    raw = getattr(settings, "HYBRID_INDEX_DIR", "indexes") or "indexes"
    path = Path(raw)
    if path.is_absolute():
        return path
    backend_root = Path(__file__).resolve().parents[2]
    return (backend_root / path).resolve()


def _parse_embedding(value: Any) -> Optional[List[float]]:
    if value is None:
        return None
    if isinstance(value, list):
        return [float(x) for x in value]
    if isinstance(value, str):
        raw = value.strip()
        if raw.startswith("[") and raw.endswith("]"):
            raw = raw[1:-1]
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        return [float(p) for p in parts]
    try:
        return [float(x) for x in list(value)]
    except Exception:
        return None


def load_all_chunks_from_db(db: Session) -> List[Dict[str, Any]]:
    rows = (
        db.query(DocumentChunk)
        .options(joinedload(DocumentChunk.document))
        .order_by(DocumentChunk.chunk_index.asc())
        .all()
    )
    chunks: List[Dict[str, Any]] = []
    for row in rows:
        emb = _parse_embedding(row.embedding)
        if not emb:
            continue
        doc: Optional[RagDocument] = row.document
        meta = dict(row.metadata_dict or {})
        if doc and doc.id:
            meta.setdefault("document_id", str(doc.id))
        meta.setdefault("chunk_index", row.chunk_index)
        try:
            from app.services.evidence_expansion import chunk_section_tags

            tags = chunk_section_tags(row.content or "")
            if tags:
                meta["section_tags"] = tags
                meta["section_category"] = tags[0]
        except Exception:  # noqa: BLE001
            pass
        chunks.append(
            {
                "chunk_id": str(row.id),
                "content": row.content,
                "embedding": emb,
                "document_id": str(doc.id) if doc and doc.id else meta.get("document_id"),
                "chunk_index": row.chunk_index,
                "document_title": doc.title if doc else None,
                "scheme_name": (doc.scheme_name if doc else None)
                or meta.get("scheme_name"),
                "scheme_id": meta.get("scheme_id"),
                "source": (doc.source if doc else None) or meta.get("source"),
                "state": (doc.state if doc else None) or meta.get("state"),
                "ministry": (doc.ministry if doc else None) or meta.get("ministry"),
                "metadata": meta,
                "page": meta.get("page"),
            }
        )
    logger.info("Loaded %s chunks with embeddings from DB", len(chunks))
    return chunks


class IndexBuilder:
    def __init__(self, index_dir: Optional[Path] = None, dim: Optional[int] = None):
        self.index_dir = Path(index_dir or default_index_dir())
        self.dim = int(dim or settings.EMBEDDING_DIMENSIONS)
        self.faiss = FaissIndex(dim=self.dim, index_dir=self.index_dir)
        self.bm25 = BM25Index(index_dir=self.index_dir)
        self.chunk_meta: Dict[str, Dict[str, Any]] = {}

    def build_faiss(self, chunks: List[Dict[str, Any]]) -> None:
        embeddings = [c["embedding"] for c in chunks]
        ids = [c["chunk_id"] for c in chunks]
        self.faiss.build_index(embeddings, ids)

    def build_bm25(self, chunks: List[Dict[str, Any]]) -> None:
        # Include title/source so filename signals (e.g. "Refund Mechanism.pdf") are searchable
        docs = []
        for c in chunks:
            meta = c.get("metadata") if isinstance(c.get("metadata"), dict) else {}
            section_hint = " ".join(meta.get("section_tags") or [])
            text = " ".join(
                x
                for x in (
                    c.get("document_title"),
                    c.get("scheme_name"),
                    c.get("source"),
                    section_hint,
                    c.get("content"),
                )
                if x
            )
            docs.append({"id": c["chunk_id"], "text": text})
        self.bm25.build_index(docs)

    def save_indexes(self) -> None:
        self.faiss.save()
        self.bm25.save()
        # Persist lightweight chunk lookup for retrieval hydration
        import json

        lookup = {
            cid: {
                "content": meta.get("content"),
                "document_title": meta.get("document_title"),
                "scheme_name": meta.get("scheme_name"),
                "scheme_id": meta.get("scheme_id"),
                "source": meta.get("source"),
                "state": meta.get("state"),
                "ministry": meta.get("ministry"),
                "metadata": meta.get("metadata"),
                "page": meta.get("page"),
            }
            for cid, meta in self.chunk_meta.items()
        }
        path = self.index_dir / "chunk_lookup.json"
        path.write_text(json.dumps(lookup), encoding="utf-8")
        logger.info("Indexes saved under %s", self.index_dir)

    def load_indexes(self) -> bool:
        ok_f = self.faiss.load()
        ok_b = self.bm25.load()
        lookup_path = self.index_dir / "chunk_lookup.json"
        if lookup_path.exists():
            import json

            raw = json.loads(lookup_path.read_text(encoding="utf-8"))
            self.chunk_meta = {k: dict(v) for k, v in raw.items()}
            # Restore content key used by retrieval
            for cid, meta in self.chunk_meta.items():
                meta["chunk_id"] = cid
        return ok_f and ok_b

    def build_all(self, db: Session) -> Dict[str, Any]:
        chunks = load_all_chunks_from_db(db)
        if not chunks:
            logger.warning("No chunks available to index")
            self.chunk_meta = {}
            self.build_faiss([])
            self.build_bm25([])
            self.save_indexes()
            return {"chunk_count": 0, "faiss": 0, "bm25": 0}

        # Validate dimensions
        bad = [c for c in chunks if len(c["embedding"]) != self.dim]
        if bad:
            raise ValueError(
                f"{len(bad)} chunks have embedding dim != {self.dim}. "
                "Re-ingest or align EMBEDDING_DIMENSIONS."
            )

        self.chunk_meta = {c["chunk_id"]: c for c in chunks}
        self.build_faiss(chunks)
        self.build_bm25(chunks)
        self.save_indexes()
        return {
            "chunk_count": len(chunks),
            "faiss": self.faiss.index.ntotal,
            "bm25": len(self.bm25.ids),
            "index_dir": str(self.index_dir),
        }


# Process-wide cache for retrieval
_BUILDER: Optional[IndexBuilder] = None


def get_index_builder(force_reload: bool = False) -> IndexBuilder:
    global _BUILDER
    if _BUILDER is not None and not force_reload:
        return _BUILDER
    builder = IndexBuilder()
    builder.load_indexes()
    _BUILDER = builder
    return _BUILDER


def set_index_builder(builder: IndexBuilder) -> None:
    global _BUILDER
    _BUILDER = builder
