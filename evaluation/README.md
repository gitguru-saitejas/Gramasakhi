# GramSakhi Benchmark v1

Isolated evaluation of the existing GramSakhi API. This package does not modify production RAG, Ollama, Evidence Validator, STT/TTS, auth, clients, or the database.

Ground truth is taken only from seed/overview documents already in `backend/data/`. Catalog and registry files contribute URLs and names only.

## Reproduce

From the repository root, using the backend virtualenv Python:

```powershell
.\backend\.venv\Scripts\python.exe evaluation\scripts\build_benchmark.py
```

Then, with the API running, authenticate as a **citizen** (not admin). The runner reads the live login field `accessToken` and probes `GET /api/chat/conversations` before scoring. An expired env token is rejected unless phone/password login can mint a fresh citizen JWT.

```powershell
$env:GRAMSAKHI_API_BASE_URL = "http://127.0.0.1:8000"
$env:GRAMSAKHI_BENCH_PHONE = "<citizen phone>"
$env:GRAMSAKHI_BENCH_PASSWORD = "<citizen password>"
.\backend\.venv\Scripts\python.exe evaluation\scripts\run_benchmark.py
```

Or set `GRAMSAKHI_BENCH_TOKEN` to a **fresh** citizen JWT from `POST /api/auth/login`. The runner never logs the token.

## Tests

```powershell
.\backend\.venv\Scripts\python.exe -m unittest discover -s evaluation/tests -p "test_*.py"
```
