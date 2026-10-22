"""
Safe staging workflow for re-embedding document_chunks and rebuilding hybrid indexes.

Does not mutate active DB embeddings or index files until explicit activate steps pass validation.
"""

from __future__ import annotations

import json
import logging
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Set

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.rag import DocumentChunk
from app.services.index_builder import IndexBuilder, default_index_dir, load_all_chunks_from_db

logger = logging.getLogger("gramsakhi.embedding_migration")

MIGRATIONS_ROOT_NAME = "embedding_migrations"


def migrations_root() -> Path:
    backend_root = Path(__file__).resolve().parents[2]
    return (backend_root / "data" / MIGRATIONS_ROOT_NAME).resolve()


def migration_paths(migration_id: str) -> Dict[str, Path]:
    base = migrations_root() / migration_id
    return {
        "base": base,
        "manifest": base / "manifest.json",
        "embedding_backup": base / "embedding_backup.jsonl",
        "staging": base / "staging.jsonl",
        "candidate_indexes": base / "candidate_indexes",
    }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def embedding_model_name() -> str:
    provider = (settings.EMBEDDING_PROVIDER or "").strip().lower()
    if provider == "gemini":
        return (settings.GEMINI_EMBEDDING_MODEL or "gemini-embedding-001").strip()
    return (settings.EMBEDDING_MODEL or "nomic-embed-text").strip()


def validate_vector(vec: List[float], dim: int, *, chunk_id: Optional[str] = None) -> None:
    if len(vec) != dim:
        label = f" chunk_id={chunk_id}" if chunk_id else ""
        raise ValueError(f"Embedding dimension {len(vec)} != {dim}{label}")
    for i, x in enumerate(vec):
        fx = float(x)
        if not math.isfinite(fx):
            label = f" chunk_id={chunk_id}" if chunk_id else ""
            raise ValueError(f"Non-finite embedding value at index {i}{label}")


def validate_vectors_for_ids(
    vectors: List[List[float]],
    chunk_ids: List[str],
    dim: int,
) -> None:
    if len(vectors) != len(chunk_ids):
        raise ValueError(
            f"Embedding count mismatch: got {len(vectors)} vectors for {len(chunk_ids)} chunk IDs"
        )
    for cid, vec in zip(chunk_ids, vectors, strict=True):
        validate_vector(vec, dim, chunk_id=cid)


def load_manifest(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Manifest not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(path: Path, manifest: MutableMapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(manifest), indent=2), encoding="utf-8")


def new_migration_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def init_manifest(db: Session, migration_id: str) -> Dict[str, Any]:
    dim = int(settings.EMBEDDING_DIMENSIONS)
    provider = (settings.EMBEDDING_PROVIDER or "").strip().lower()
    chunk_count = db.query(DocumentChunk.id).count()
    manifest: Dict[str, Any] = {
        "migration_id": migration_id,
        "status": "initialized",
        "embedding_provider": provider,
        "embedding_model": embedding_model_name(),
        "embedding_dimensions": dim,
        "chunk_count_expected": chunk_count,
        "staging_count": 0,
        "embedding_backup_complete": False,
        "staging_validated": False,
        "candidate_index_built": False,
        "db_applied": False,
        "indexes_activated": False,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "active_index_dir": str(default_index_dir()),
        "candidate_index_dir": str(migration_paths(migration_id)["candidate_indexes"]),
    }
    paths = migration_paths(migration_id)
    paths["base"].mkdir(parents=True, exist_ok=True)
    save_manifest(paths["manifest"], manifest)
    return manifest


def _parse_embedding_backup_line(raw: str) -> Optional[tuple[str, List[float]]]:
    line = raw.strip()
    if not line:
        return None
    row = json.loads(line)
    cid = str(row["chunk_id"])
    vec = [float(x) for x in row["embedding"]]
    return cid, vec


def write_embedding_backup(db: Session, backup_path: Path, dim: int) -> int:
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    rows = db.query(DocumentChunk).order_by(DocumentChunk.id.asc()).all()
    with backup_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            emb = row.embedding
            if emb is None:
                raise ValueError(f"Chunk {row.id} has no embedding to backup")
            vec = [float(x) for x in list(emb)]
            validate_vector(vec, dim, chunk_id=str(row.id))
            fh.write(
                json.dumps({"chunk_id": str(row.id), "embedding": vec}, separators=(",", ":"))
                + "\n"
            )
            count += 1
    return count


def load_staging_ids(staging_path: Path) -> Set[str]:
    if not staging_path.is_file():
        return set()
    ids: Set[str] = set()
    with staging_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            ids.add(str(row["chunk_id"]))
    return ids


def load_staging_vectors(staging_path: Path, dim: int) -> Dict[str, List[float]]:
    if not staging_path.is_file():
        return {}
    out: Dict[str, List[float]] = {}
    with staging_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            cid = str(row["chunk_id"])
            vec = [float(x) for x in row["embedding"]]
            validate_vector(vec, dim, chunk_id=cid)
            out[cid] = vec
    return out


def append_staging_rows(staging_path: Path, chunk_ids: List[str], vectors: List[List[float]], dim: int) -> None:
    validate_vectors_for_ids(vectors, chunk_ids, dim)
    staging_path.parent.mkdir(parents=True, exist_ok=True)
    with staging_path.open("a", encoding="utf-8") as fh:
        for cid, vec in zip(chunk_ids, vectors, strict=True):
            fh.write(
                json.dumps({"chunk_id": cid, "embedding": vec}, separators=(",", ":")) + "\n"
            )


def validate_staging_complete(
    db: Session,
    staging_path: Path,
    dim: int,
    expected_count: int,
) -> Dict[str, Any]:
    staging = load_staging_vectors(staging_path, dim)
    if len(staging) != expected_count:
        raise ValueError(
            f"Staging incomplete: {len(staging)} vectors, expected {expected_count}"
        )
    db_ids = {str(r.id) for r in db.query(DocumentChunk.id).all()}
    missing = db_ids - set(staging.keys())
    extra = set(staging.keys()) - db_ids
    if missing:
        raise ValueError(f"Staging missing {len(missing)} chunk IDs (e.g. {next(iter(missing))})")
    if extra:
        raise ValueError(f"Staging has {len(extra)} unknown chunk IDs")
    return {"staging_count": len(staging), "dimensions": dim}


def chunks_from_staging_and_db(db: Session, staging: Mapping[str, List[float]]) -> List[Dict[str, Any]]:
    """Build index-builder chunk dicts using staged vectors + current DB text/metadata."""
    base_chunks = load_all_chunks_from_db(db)
    by_id = {c["chunk_id"]: c for c in base_chunks}
    merged: List[Dict[str, Any]] = []
    for cid, vec in staging.items():
        if cid not in by_id:
            raise ValueError(f"Chunk {cid} in staging but not loaded from DB")
        chunk = dict(by_id[cid])
        chunk["embedding"] = list(vec)
        merged.append(chunk)
    merged.sort(key=lambda c: (c.get("document_id") or "", int(c.get("chunk_index") or 0)))
    return merged


def build_candidate_indexes(db: Session, candidate_dir: Path, staging_path: Path, dim: int) -> Dict[str, Any]:
    staging = load_staging_vectors(staging_path, dim)
    chunks = chunks_from_staging_and_db(db, staging)
    if not chunks:
        raise ValueError("No chunks to index")
    bad = [c for c in chunks if len(c["embedding"]) != dim]
    if bad:
        raise ValueError(f"{len(bad)} staged chunks have wrong embedding dimension")
    if candidate_dir.exists():
        shutil.rmtree(candidate_dir)
    candidate_dir.mkdir(parents=True, exist_ok=True)
    builder = IndexBuilder(index_dir=candidate_dir, dim=dim)
    builder.chunk_meta = {c["chunk_id"]: c for c in chunks}
    builder.build_faiss(chunks)
    builder.build_bm25(chunks)
    builder.save_indexes()
    stats = {
        "chunk_count": len(chunks),
        "faiss": builder.faiss.index.ntotal,
        "bm25": len(builder.bm25.ids),
        "index_dir": str(candidate_dir),
        "faiss_dim": builder.faiss.index.d,
    }
    if stats["faiss"] != len(chunks) or stats["bm25"] != len(chunks):
        raise ValueError(f"Candidate index counts inconsistent: {stats}")
    if stats["faiss_dim"] != dim:
        raise ValueError(f"Candidate FAISS dim {stats['faiss_dim']} != {dim}")
    return stats


def validate_candidate_indexes(candidate_dir: Path, dim: int, expected_vectors: int) -> None:
    builder = IndexBuilder(index_dir=candidate_dir, dim=dim)
    if not builder.load_indexes():
        raise ValueError(f"Candidate indexes failed to load under {candidate_dir}")
    if builder.faiss.index.ntotal != expected_vectors:
        raise ValueError(
            f"Candidate FAISS vector count {builder.faiss.index.ntotal} != {expected_vectors}"
        )
    if len(builder.bm25.ids) != expected_vectors:
        raise ValueError(
            f"Candidate BM25 doc count {len(builder.bm25.ids)} != {expected_vectors}"
        )


def apply_staging_to_database(db: Session, staging_path: Path, dim: int, expected_count: int) -> int:
    validate_staging_complete(db, staging_path, dim, expected_count)
    staging = load_staging_vectors(staging_path, dim)
    try:
        rows = db.query(DocumentChunk).order_by(DocumentChunk.id.asc()).all()
        updated = 0
        for row in rows:
            cid = str(row.id)
            vec = staging.get(cid)
            if vec is None:
                raise ValueError(f"Missing staging vector for {cid}")
            row.embedding = vec
            updated += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return updated


def restore_embeddings_from_backup(db: Session, backup_path: Path, dim: int) -> int:
    if not backup_path.is_file():
        raise FileNotFoundError(f"Embedding backup not found: {backup_path}")
    restored = 0
    try:
        with backup_path.open(encoding="utf-8") as fh:
            for line in fh:
                parsed = _parse_embedding_backup_line(line)
                if not parsed:
                    continue
                cid, vec = parsed
                validate_vector(vec, dim, chunk_id=cid)
                row = db.query(DocumentChunk).filter(DocumentChunk.id == cid).one_or_none()
                if row is None:
                    raise ValueError(f"Backup references unknown chunk_id={cid}")
                row.embedding = vec
                restored += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return restored


def activate_candidate_indexes(migration_id: str, candidate_dir: Path) -> Path:
    active = default_index_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = active.parent / f"{active.name}_pre_activate_{stamp}"
    if active.is_dir():
        shutil.copytree(active, backup)
    if active.is_dir():
        shutil.rmtree(active)
    shutil.copytree(candidate_dir, active)
    logger.info("Activated candidate indexes from migration %s (backup at %s)", migration_id, backup)
    return backup


def list_chunk_rows(db: Session) -> List[DocumentChunk]:
    return db.query(DocumentChunk).order_by(DocumentChunk.chunk_index.asc(), DocumentChunk.id.asc()).all()
