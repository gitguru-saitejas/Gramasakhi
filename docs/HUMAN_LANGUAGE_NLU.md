# Human Language Understanding (NLU)

GramSakhi interprets citizen messages in **one shared backend layer** used by Web, Android, IVR, and STT transcripts.

## Flow

```
Client (text or STT transcript)
  → POST /api/chat  (or IVR adapter → handle_citizen_chat)
  → interpret_human_language()
  → build_assistance_context()  (CitizenIntent + scheme + normalized query)
  → RAG / eligibility / evidence / LLM
```

## Intent types

Backend NLU intents (`HumanLanguageIntent`):

- `SCHEME_DISCOVERY`, `GENERAL_INFORMATION`, `ELIGIBILITY`, `PERSONAL_ELIGIBILITY`
- `BENEFITS`, `BENEFITS_AMOUNT`, `APPLICATION_PROCESS`, `APPLICATION_CHANNEL`
- `DOCUMENTS_REQUIRED`, `STATUS`, `UNKNOWN`

These map to existing `CitizenIntent` for prompts and eligibility (no client duplication).

## Context resolution

Order: explicit scheme in message → conversation `active_scheme_context` → rewrite active scheme → history. Scheme slug (`scheme_id`) is filled when `requested_scheme_identity` resolves it.

## Multilingual support

Deterministic regex/phrase rules cover English, Hindi, Kannada, and common Hinglish/Kanglish. STT text is normalized via `normalize_stt_artifacts` before classification.

Optional Ollama JSON classification runs only when `NLU_LLM_ENABLED=true` and deterministic rules return `UNKNOWN`; failures fall back safely.

## RAG integration

`AssistanceContext.normalized_query` drives retrieval (intent + scheme phrasing). `build_retrieval_plan(..., nlu_intent=...)` boosts semantic keywords (application, documents, amount, status) without replacing FAISS/BM25.

## Ambiguity

Very short messages (`How?`, `Can I?`) stay `UNKNOWN`; the assistant may ask a clarification question. NLU never answers factual scheme questions.

## API metadata (additive)

`ChatResponse` may include `nlu_intent`, `normalized_query`, and `scheme_id` alongside existing `citizen_intent` and `detected_scheme`.
