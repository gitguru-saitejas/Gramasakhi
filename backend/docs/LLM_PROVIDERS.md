# LLM generation providers (Gemini / Ollama)

GramSakhi separates **text generation** (answers, rephrase, translation) from **embeddings** (RAG indexing). This migration adds Google Gemini for generation while keeping Ollama for `nomic-embed-text` unless you change `EMBEDDING_PROVIDER` separately.

## Obtain a Gemini API key

1. Sign in at [Google AI Studio](https://aistudio.google.com/).
2. Create an API key (server-side use only).
3. Set `GEMINI_API_KEY` in `backend/.env` (never commit the key).

Free-tier rate limits and model availability depend on your account and current Google policies. See [Gemini API pricing](https://ai.google.dev/pricing) and [models](https://ai.google.dev/gemini-api/docs/models).

**Privacy:** Do not send OTPs, passwords, or unnecessary citizen PII in prompts. Free-tier API usage may be subject to Google's data handling terms; review current documentation before production deployment.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `LLM_PROVIDER` | `gemini` or `ollama` (default `ollama` for backward compatibility) |
| `GEMINI_API_KEY` | Server-side Gemini key |
| `GEMINI_MODEL` | Model id (default `gemini-3.5-flash-lite`) |
| `GEMINI_TEMPERATURE` | Generation temperature (default `0.1`) |
| `GEMINI_TIMEOUT_SECONDS` | Per-request timeout |
| `GEMINI_MAX_OUTPUT_TOKENS` | Cap on completion length |
| `GEMINI_MAX_RETRIES` | Retries for rate limits / transient errors |
| `LLM_FALLBACK_TO_OLLAMA` | If `true`, Gemini failures fall back to Ollama when configured |

Ollama variables (`OLLAMA_BASE_URL`, `OLLAMA_LLM_MODEL`, etc.) remain for embeddings and optional generation fallback.

## Recommended setup (Gemini generation + Ollama embeddings)

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.5-flash-lite

EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
OLLAMA_API_URL=http://127.0.0.1:11434
LLM_FALLBACK_TO_OLLAMA=true
```

Ollama must still run for embeddings and hybrid retrieval unless you migrate embeddings separately (out of scope).

## Start backend

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Health checks

- `GET /health/llm` — configured generation provider
- `GET /health/ollama` — embedding reachability + Ollama LLM tags
- `GET /health/system` — full demo checklist

CLI:

```powershell
cd backend
.\.venv\Scripts\python.exe -c "from app.services.gemini_llm import check_gemini_llm; print(check_gemini_llm())"
```

## Fallback behavior

With `LLM_PROVIDER=gemini` and `LLM_FALLBACK_TO_OLLAMA=true`, transient Gemini errors (timeout, 429, network) attempt one Ollama `/api/generate` call. Responses still pass through evidence validation and grounding—fallback does not bypass RAG gates.

With `LLM_FALLBACK_TO_OLLAMA=false`, only Gemini is used; failures return the same controlled errors as Ollama outages.

Gemini-only deployments do not require Ollama for **generation**, but still need Ollama (or another embedding provider) for default RAG embeddings.

## Troubleshooting

| Symptom | Action |
|---------|--------|
| `GEMINI_API_KEY not configured` | Set key in `backend/.env`, restart API |
| `invalid_api_key` on `/health/llm` | Regenerate key in AI Studio |
| Model not found | Pick a model listed for your account; update `GEMINI_MODEL` |
| 429 / quota | Reduce benchmark concurrency; wait for quota reset; enable fallback |
| Timeouts | Increase `GEMINI_TIMEOUT_SECONDS` or shorten prompts |
| Empty answers | Check blocked/safety responses in logs; verify evidence gate still passes |

## Tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_llm*.py" -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Gemini tests mock the SDK—no API key required for CI.

## Benchmark (unchanged procedure)

```powershell
# API running with desired LLM_PROVIDER in .env
cd evaluation
$env:PYTHONPATH=".."
..\backend\.venv\Scripts\python.exe -m evaluation.runners.benchmark_v2 ...
```

Compare reports only when the same dataset and methodology are used. Switching `LLM_PROVIDER` changes generation only—not retrieval metrics definitions.

## Unchanged in this migration

- FAISS / BM25 indexes and hybrid retrieval weights
- `nomic-embed-text` embedding pipeline (default)
- Evidence validator, output grounding, eligibility logic
- Frontend API contracts
