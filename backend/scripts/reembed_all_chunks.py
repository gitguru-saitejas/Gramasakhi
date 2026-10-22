#!/usr/bin/env python3

"""

Staged re-embedding for document_chunks + candidate FAISS/BM25 rebuild.



Active DB embeddings and indexes are not switched until validate + activate steps succeed.



Usage (from backend/):

  .venv\\Scripts\\python.exe scripts/reembed_all_chunks.py --dry-run

  .venv\\Scripts\\python.exe scripts/reembed_all_chunks.py --step init

  .venv\\Scripts\\python.exe scripts/reembed_all_chunks.py --step backup --migration-id <id> --backup-indexes

  .venv\\Scripts\\python.exe scripts/reembed_all_chunks.py --step embed --migration-id <id>

  .venv\\Scripts\\python.exe scripts/reembed_all_chunks.py --step validate --migration-id <id>

  .venv\\Scripts\\python.exe scripts/reembed_all_chunks.py --step build-candidate --migration-id <id>

  .venv\\Scripts\\python.exe scripts/reembed_all_chunks.py --step apply-db --migration-id <id>

  .venv\\Scripts\\python.exe scripts/reembed_all_chunks.py --step activate-indexes --migration-id <id> --backup-indexes

  .venv\\Scripts\\python.exe scripts/reembed_all_chunks.py --step rollback-db --migration-id <id>

  .venv\\Scripts\\python.exe scripts/reembed_all_chunks.py --step rollback-indexes --from-dir <indexes_backup_path>



Requires GEMINI_API_KEY when EMBEDDING_PROVIDER=gemini.

"""



from __future__ import annotations



import argparse

import shutil

import sys

from datetime import datetime, timezone

from pathlib import Path



BACKEND = Path(__file__).resolve().parents[1]

if str(BACKEND) not in sys.path:

    sys.path.insert(0, str(BACKEND))



from app.core.config import settings

from app.database.session import SessionLocal
from app.models import audit, citizen_account, conversation, rag, user  # noqa: F401

from app.services.embedding_migration import (

    activate_candidate_indexes,

    append_staging_rows,

    apply_staging_to_database,

    build_candidate_indexes,

    embedding_model_name,

    init_manifest,

    list_chunk_rows,

    load_manifest,

    load_staging_ids,

    migration_paths,

    restore_embeddings_from_backup,

    save_manifest,

    utc_now_iso,

    validate_candidate_indexes,

    validate_staging_complete,

    write_embedding_backup,

)

from app.services.index_builder import default_index_dir

from app.services.rag import get_embeddings_batch



STEPS = (

    "init",

    "backup",

    "embed",

    "validate",

    "build-candidate",

    "apply-db",

    "activate-indexes",

    "rollback-db",

    "rollback-indexes",

)





def _resolve_migration_id(args: argparse.Namespace) -> str:

    if args.migration_id:

        return args.migration_id.strip()

    if args.step == "init":

        from app.services.embedding_migration import new_migration_id



        return new_migration_id()

    raise SystemExit("--migration-id is required for this step")





def _print_config() -> None:

    provider = (settings.EMBEDDING_PROVIDER or "").strip().lower()

    print(

        f"Embedding provider: {provider} "

        f"model={embedding_model_name()} dim={settings.EMBEDDING_DIMENSIONS}"

    )





def main() -> int:

    parser = argparse.ArgumentParser(description="Staged chunk re-embedding and index migration")

    parser.add_argument("--dry-run", action="store_true", help="Report chunk count only; no writes")

    parser.add_argument("--step", choices=STEPS, help="Migration phase (omit with --dry-run only)")

    parser.add_argument("--migration-id", help="Existing migration directory name")

    parser.add_argument(

        "--backup-indexes",

        action="store_true",

        help="Copy active indexes/ to indexes_backup_<ts>/",

    )

    parser.add_argument(

        "--from-dir",

        help="Source index directory for rollback-indexes",

    )

    parser.add_argument(

        "--batch-size",

        type=int,

        default=max(1, int(settings.GEMINI_EMBEDDING_BATCH_SIZE)),

        help="Embedding API batch size",

    )

    args = parser.parse_args()



    _print_config()



    db = SessionLocal()

    try:

        rows = list_chunk_rows(db)

        print(f"Chunks in database: {len(rows)}")

        if args.dry_run:

            return 0

        if not args.step:

            parser.error("Provide --step or --dry-run")



        migration_id = _resolve_migration_id(args)

        paths = migration_paths(migration_id)

        dim = int(settings.EMBEDDING_DIMENSIONS)



        if args.step == "init":

            manifest = init_manifest(db, migration_id)

            print(f"Created migration {migration_id} at {paths['base']}")

            print(f"  expected_chunks={manifest['chunk_count_expected']}")

            return 0



        if args.step == "rollback-indexes":

            src = args.from_dir or ""

            if not src:

                raise SystemExit("--from-dir is required for rollback-indexes")

            src_path = Path(src).resolve()

            if not src_path.is_dir():

                raise SystemExit(f"Index backup not found: {src_path}")

            active = default_index_dir()

            if active.is_dir():

                shutil.rmtree(active)

            shutil.copytree(src_path, active)

            print(f"Restored active indexes from {src_path}")

            return 0



        if not paths["manifest"].is_file():

            raise SystemExit(f"Unknown migration {migration_id}; run --step init first")



        manifest = load_manifest(paths["manifest"])

        manifest["updated_at"] = utc_now_iso()

        expected = int(manifest["chunk_count_expected"])



        if args.step == "backup":

            if args.backup_indexes:

                idx = default_index_dir()

                if idx.is_dir():

                    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

                    dest = idx.parent / f"{idx.name}_backup_{stamp}"

                    shutil.copytree(idx, dest)

                    manifest["indexes_backup_dir"] = str(dest)

                    print(f"Backed up indexes to {dest}")

            count = write_embedding_backup(db, paths["embedding_backup"], dim)

            manifest["embedding_backup_complete"] = True

            manifest["embedding_backup_count"] = count

            manifest["status"] = "backup_complete"

            save_manifest(paths["manifest"], manifest)

            print(f"Wrote embedding backup for {count} chunks")

            return 0



        if args.step == "embed":

            if not manifest.get("embedding_backup_complete"):

                raise SystemExit("Run --step backup before embed")

            done = load_staging_ids(paths["staging"])

            pending = [r for r in rows if str(r.id) not in done]

            print(f"Staging: {len(done)} done, {len(pending)} remaining")

            batch_size = max(1, int(args.batch_size))

            for start in range(0, len(pending), batch_size):

                batch_rows = pending[start : start + batch_size]

                batch_texts = [r.content or "" for r in batch_rows]

                batch_ids = [str(r.id) for r in batch_rows]

                try:

                    vectors = get_embeddings_batch(batch_texts)

                except Exception as exc:

                    manifest["status"] = "embed_failed"

                    manifest["last_error"] = type(exc).__name__

                    save_manifest(paths["manifest"], manifest)

                    raise

                append_staging_rows(paths["staging"], batch_ids, vectors, dim)

                done.update(batch_ids)

                manifest["staging_count"] = len(done)

                manifest["status"] = "embedding"

                save_manifest(paths["manifest"], manifest)

                print(f"  staged {len(done)}/{expected}")

            manifest["status"] = "staging_complete"

            save_manifest(paths["manifest"], manifest)

            return 0



        if args.step == "validate":

            stats = validate_staging_complete(db, paths["staging"], dim, expected)

            manifest["staging_validated"] = True

            manifest["staging_count"] = stats["staging_count"]

            manifest["status"] = "staging_validated"

            save_manifest(paths["manifest"], manifest)

            print("Staging validation OK:", stats)

            return 0



        if args.step == "build-candidate":

            if not manifest.get("staging_validated"):

                validate_staging_complete(db, paths["staging"], dim, expected)

                manifest["staging_validated"] = True

            stats = build_candidate_indexes(db, paths["candidate_indexes"], paths["staging"], dim)

            validate_candidate_indexes(paths["candidate_indexes"], dim, expected)

            manifest["candidate_index_built"] = True

            manifest["candidate_index_stats"] = stats

            manifest["status"] = "candidate_ready"

            save_manifest(paths["manifest"], manifest)

            print("Candidate indexes built:", stats)

            return 0



        if args.step == "apply-db":

            if not manifest.get("candidate_index_built"):

                raise SystemExit("Run --step build-candidate before apply-db")

            updated = apply_staging_to_database(db, paths["staging"], dim, expected)

            manifest["db_applied"] = True

            manifest["db_applied_count"] = updated

            manifest["status"] = "db_applied"

            save_manifest(paths["manifest"], manifest)

            print(f"Applied {updated} embeddings to database")

            return 0



        if args.step == "activate-indexes":

            if not manifest.get("db_applied"):

                raise SystemExit("Run --step apply-db before activate-indexes")

            if not manifest.get("candidate_index_built"):

                raise SystemExit("Candidate indexes missing")

            validate_candidate_indexes(paths["candidate_indexes"], dim, expected)

            if args.backup_indexes:

                idx = default_index_dir()

                if idx.is_dir():

                    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

                    dest = idx.parent / f"{idx.name}_backup_{stamp}"

                    shutil.copytree(idx, dest)

                    manifest["indexes_backup_dir"] = str(dest)

                    print(f"Backed up active indexes to {dest}")

            pre_activate = activate_candidate_indexes(migration_id, paths["candidate_indexes"])

            manifest["indexes_activated"] = True

            manifest["indexes_pre_activate_backup"] = str(pre_activate)

            manifest["status"] = "complete"

            save_manifest(paths["manifest"], manifest)

            print(f"Activated candidate indexes (pre-activate copy at {pre_activate})")

            return 0



        if args.step == "rollback-db":

            if not manifest.get("embedding_backup_complete"):

                raise SystemExit("No embedding backup recorded for this migration")

            restored = restore_embeddings_from_backup(db, paths["embedding_backup"], dim)

            manifest["status"] = "rolled_back_db"

            manifest["rollback_db_count"] = restored

            save_manifest(paths["manifest"], manifest)

            print(f"Restored {restored} embeddings from backup")

            return 0



        raise SystemExit(f"Unhandled step: {args.step}")

    finally:

        db.close()





if __name__ == "__main__":

    raise SystemExit(main())

