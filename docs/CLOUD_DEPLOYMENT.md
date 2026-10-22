# GramSakhi cloud deployment (Render + static frontend)

## Architecture

| Component | Suggested host |
|-----------|----------------|
| Frontend (Vite) | Vercel / Netlify / Render static |
| Backend (FastAPI) | Render web service |
| Database | Existing Supabase PostgreSQL |
| LLM generation | Gemini API (`LLM_PROVIDER=gemini`) |
| Embeddings | Gemini (`EMBEDDING_PROVIDER=gemini`) |
| FAISS/BM25 indexes | Persistent disk on Render **or** rebuild on deploy from DB |

Ollama is **not** required when `RUNTIME_PROFILE=cloud`.

## Backend environment (production template — no secrets)

```env
APP_ENV=production
RUNTIME_PROFILE=cloud
SECRET_KEY=<long-random>

DATABASE_URL=<supabase-postgres-url>

LLM_PROVIDER=gemini
GEMINI_API_KEY=<from-ai-studio>
GEMINI_MODEL=gemini-3.5-flash-lite
LLM_FALLBACK_TO_OLLAMA=false

EMBEDDING_PROVIDER=gemini
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIMENSIONS=768

OTP_DELIVERY_MODE=sms
OTP_DEV_POPUP_ENABLED=false

BACKEND_CORS_ORIGINS=["https://gramasakhi-1.onrender.com","http://127.0.0.1:5173"]
```

## Frontend environment

See also [`FRONTEND_BACKEND.md`](FRONTEND_BACKEND.md).

```env
VITE_API_BASE_URL=https://gramasakhi.onrender.com
```

On the **backend** Render service, set `BACKEND_CORS_ORIGINS` to your static frontend origin(s), e.g. `["https://your-app.vercel.app"]`. Keep `http://127.0.0.1:5173` only if you test local UI against production API.

## Embedding migration (required once when switching off Ollama)

**Do not run against production until staging is validated.** The script never writes partial embeddings to the active DB.

1. Set `EMBEDDING_PROVIDER=gemini` and `GEMINI_API_KEY`.
2. From `backend/` (each step is explicit; resume with the same `--migration-id`):

   ```powershell
   .\.venv\Scripts\python.exe scripts/reembed_all_chunks.py --dry-run
   .\.venv\Scripts\python.exe scripts/reembed_all_chunks.py --step init
   .\.venv\Scripts\python.exe scripts/reembed_all_chunks.py --step backup --migration-id <id> --backup-indexes
   .\.venv\Scripts\python.exe scripts/reembed_all_chunks.py --step embed --migration-id <id>
   .\.venv\Scripts\python.exe scripts/reembed_all_chunks.py --step validate --migration-id <id>
   .\.venv\Scripts\python.exe scripts/reembed_all_chunks.py --step build-candidate --migration-id <id>
   .\.venv\Scripts\python.exe scripts/reembed_all_chunks.py --step apply-db --migration-id <id>
   .\.venv\Scripts\python.exe scripts/reembed_all_chunks.py --step activate-indexes --migration-id <id> --backup-indexes
   ```

3. Manifest and artifacts live under `backend/data/embedding_migrations/<id>/` (gitignored). Roll back DB vectors with `--step rollback-db`; restore indexes with `--step rollback-indexes --from-dir <indexes_backup_*>`.
4. Run the evaluation framework and compare retrieval metrics before deleting backups.

**Note:** Vectors from `nomic-embed-text` (768) are not comparable to Gemini embeddings even at 768 dims — full re-embed is mandatory. Index file backup alone does not restore old DB embeddings; use `embedding_backup.jsonl` from the migration directory.

## SMS OTP blocker

Production must use `OTP_DELIVERY_MODE=sms`. The SMS hook in `otp_sms.py` logs dispatch only until Exotel/other credentials are wired. **Do not enable `dev_popup` in production.**

## Deploy steps (manual — credentials not in repo)

### Render backend

1. New Web Service → connect GitHub repo → root `backend`.
2. Build: `pip install -r requirements.txt`
3. Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add env vars from template above.
5. Attach persistent disk at `/data/indexes` and set `HYBRID_INDEX_DIR=/data/indexes` if indexes must survive redeploys.
6. Health check path: `/health`

### Static frontend

1. Build command: `cd frontend/gramsakhi && npm ci && npm run build`
2. Output: `frontend/gramsakhi/dist`
3. Set `VITE_API_BASE_URL` at build time.

## Session behavior (web)

Citizen JWTs are kept **in memory only** for the SPA tab session. Reload or new tab requires login. Backend JWT expiry is unchanged; invalid tokens still return 401.

## Rollback

- Restore `indexes_backup_*` directory.
- Set `EMBEDDING_PROVIDER=ollama` and local `RUNTIME_PROFILE=local` for developer machines only.

## Deployment status

**Not live-deployed from this repository run** — no Render/Vercel credentials were available in the agent environment. Follow the steps above and verify URLs with `/health` and a full OTP login flow.
