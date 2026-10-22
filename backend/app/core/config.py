import json
from pathlib import Path
from typing import Any, List

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always load backend/.env regardless of process cwd (uvicorn reloader, tests, etc.)
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
# Force-load into os.environ so SQLAlchemy / subprocesses see the same values.
# override=True beats empty or stale shell vars that otherwise pin SQLite.
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE, override=True)


class Settings(BaseSettings):
    PROJECT_NAME: str = "GramSakhi API"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = "gramsakhi_very_secret_key_change_me_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days (JWT; web client keeps token in memory only)

    # Loaded from backend/.env — falls back to local SQLite if not set
    DATABASE_URL: str = "sqlite:///./gramsakhi.db"

    # Supabase Storage Configurations for RAG Guideline Documents
    SUPABASE_URL: str = ""
    # New-style publishable key (sb_publishable_...) or legacy anon JWT
    SUPABASE_PUBLISHABLE_KEY: str = ""
    # Secret / service_role key required for private bucket writes
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_STORAGE_BUCKET: str = "rag-documents"

    # Embedding Configurations (must match document_chunks.embedding vector size)
    EMBEDDING_PROVIDER: str = "ollama"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    EMBEDDING_DIMENSIONS: int = 768
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    GEMINI_EMBEDDING_TIMEOUT_SECONDS: float = 60.0
    GEMINI_EMBEDDING_BATCH_SIZE: int = 16
    GEMINI_EMBEDDING_MAX_RETRIES: int = 1
    # local | cloud — cloud forbids Ollama and requires Gemini LLM + embeddings
    RUNTIME_PROFILE: str = "local"
    # Shared Ollama host (embeddings + legacy callers)
    OLLAMA_API_URL: str = "http://127.0.0.1:11434"
    # Phase 5 generation — prefer OLLAMA_BASE_URL; falls back to OLLAMA_API_URL in llm_service
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_LLM_MODEL: str = "llama3.2:3b"
    # Backward-compatible alias used in some .env files
    OLLAMA_MODEL: str = "llama3.2:3b"
    OLLAMA_LLM_TEMPERATURE: float = 0.1
    OLLAMA_LLM_TIMEOUT_SECONDS: float = 60.0
    OLLAMA_LLM_NUM_PREDICT: int = 512

    # LLM text generation provider: ollama | gemini (embeddings remain separate)
    LLM_PROVIDER: str = "ollama"
    GEMINI_API_KEY: str = ""
    # Default targets free-tier text models per Google AI docs (verify for your account).
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_TEMPERATURE: float = 0.1
    GEMINI_TIMEOUT_SECONDS: float = 60.0
    GEMINI_MAX_OUTPUT_TOKENS: int = 512
    GEMINI_MAX_RETRIES: int = 1
    # When LLM_PROVIDER=gemini, fall back to Ollama on transient Gemini failures.
    LLM_FALLBACK_TO_OLLAMA: bool = True

    # Kannada / multilingual output quality gate (post-Evidence Validator)
    MAX_LANGUAGE_REGEN_ATTEMPTS: int = 2
    LANGUAGE_QUALITY_GATE_ENABLED: bool = True

    # Phase 6 — conversation memory + query rewriting
    CONVERSATION_HISTORY_LIMIT: int = 6
    QUERY_REWRITE_USE_OLLAMA: bool = False
    QUERY_REWRITE_TIMEOUT_SECONDS: float = 15.0

    # Live government retrieval fallback (only when indexed evidence is insufficient)
    LIVE_GOV_FALLBACK_ENABLED: bool = True
    LIVE_GOV_MAX_SOURCES: int = 4
    LIVE_GOV_MAX_CANDIDATES: int = 8
    LIVE_GOV_MAX_PDFS: int = 4
    LIVE_GOV_MAX_PAGES: int = 6
    LIVE_GOV_MAX_DOCUMENTS: int = 6
    LIVE_GOV_MAX_PDF_SIZE_MB: float = 10.0
    LIVE_GOV_TIMEOUT_SECONDS: float = 25.0
    LIVE_GOV_OVERALL_TIMEOUT_SECONDS: float = 240.0
    # Adaptive acquisition (static → browser JS)
    LIVE_GOV_BROWSER_ENABLED: bool = True
    LIVE_GOV_BROWSER_TIMEOUT_SECONDS: float = 45.0
    LIVE_GOV_MAX_BROWSER_ACTIONS: int = 8
    LIVE_GOV_OCR_TIMEOUT_SECONDS: float = 60.0
    # Provider registry orchestration (myScheme → registry government)
    LIVE_GOV_PROVIDER_REGISTRY_ENABLED: bool = True
    INDIAGOV_PROVIDER_ENABLED: bool = True
    DATAGOV_PROVIDER_ENABLED: bool = True

    # Hybrid RAG (FAISS + BM25 + CrossEncoder)
    HYBRID_INDEX_DIR: str = "indexes"
    HYBRID_FAISS_WEIGHT: float = 0.6
    HYBRID_BM25_WEIGHT: float = 0.4
    HYBRID_CANDIDATE_K: int = 20
    HYBRID_TOP_K: int = 5
    HYBRID_RERANK_ENABLED: bool = True
    # Load CrossEncoder on startup (local dev). Disable on memory-constrained hosts (e.g. Render Free).
    STARTUP_WARM_CROSS_ENCODER: bool = True
    CROSS_ENCODER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Evidence sufficiency hard gate (Phase 4)
    EVIDENCE_RELEVANCE_THRESHOLD: float = 0.65
    EVIDENCE_COVERAGE_THRESHOLD: float = 0.6
    EVIDENCE_AGREEMENT_THRESHOLD: float = 0.7
    EVIDENCE_AGREEMENT_VARIANCE_MAX: float = 0.08
    EVIDENCE_MIN_QUERY_TERMS: int = 2
    EVIDENCE_GATE_ENABLED: bool = True
    # Chunks scoring below this are dropped before validation so weak tail hits
    # cannot drag down (or pad) the evidence set.
    EVIDENCE_DOC_FLOOR: float = 0.5
    # Cache query embeddings — repeated citizen questions are common.
    QUERY_EMBED_CACHE_SIZE: int = 256

    # Phase 7 — STT (local Whisper-family when installed; optional)
    STT_ENABLED: bool = True
    STT_MODEL: str = "base"
    STT_DEVICE: str = "cpu"  # cpu | cuda
    STT_COMPUTE_TYPE: str = "int8"
    STT_MAX_AUDIO_SIZE_MB: float = 8.0
    STT_MAX_DURATION_SECONDS: float = 60.0
    STT_TIMEOUT_SECONDS: float = 90.0
    STT_MIN_CONFIDENCE: float = 0.35
    STT_MAX_CONCURRENT: int = 2

    # Phase 7 — TTS (edge-tts when installed; optional)
    TTS_ENABLED: bool = True
    TTS_MODEL: str = "edge-tts"
    TTS_VOICE_EN: str = "en-IN-NeerjaNeural"
    TTS_VOICE_KN: str = "kn-IN-SapnaNeural"
    TTS_VOICE_HI: str = "hi-IN-SwaraNeural"
    TTS_DEVICE: str = "cpu"
    TTS_TIMEOUT_SECONDS: float = 60.0
    TTS_MAX_CONCURRENT: int = 2
    TTS_CACHE_ENABLED: bool = True
    TTS_CACHE_MAX_ENTRIES: int = 64
    VOICE_RATE_LIMIT_WINDOW_SECONDS: float = 60.0
    VOICE_RATE_LIMIT_PER_WINDOW: int = 30

    # Application environment (production disables dev-only tooling)
    APP_ENV: str = "production"

    # Auth abuse controls
    AUTH_RATE_LIMIT_WINDOW_SECONDS: float = 3600.0
    AUTH_OTP_SEND_MAX_PER_WINDOW: int = 5
    AUTH_RATE_LIMIT_MAX_PER_WINDOW: int = 30
    AUTH_LOGIN_WINDOW_SECONDS: float = 900.0
    AUTH_LOGIN_MAX_PER_WINDOW: int = 10
    AUTH_RATE_LIMIT_MAX_KEYS: int = 4096
    # Dev-only OTP console simulator (terminal output when APP_ENV is not production)
    OTP_CONSOLE_SIMULATOR_ENABLED: bool = True
    # OTP delivery: sms (default) | dev_popup (development/FYP demo only)
    OTP_DELIVERY_MODE: str = "sms"
    OTP_DEV_POPUP_ENABLED: bool = False
    # Dev-only OTP retrieval endpoint (requires APP_ENV != production + secret key)
    OTP_DEV_RETRIEVAL_ENABLED: bool = False
    OTP_DEV_RETRIEVAL_KEY: str = ""
    SECURITY_HEADERS_ENABLED: bool = True

    # IVR — Exotel telephony (credentials used by Flow/dashboard tooling, not echoed in IVR responses)
    IVR_PROVIDER: str = "mock"
    EXOTEL_ACCOUNT_SID: str = ""
    EXOTEL_API_KEY: str = ""
    EXOTEL_API_TOKEN: str = ""
    EXOTEL_RECORDING_FETCH_TIMEOUT_SECONDS: float = 30.0
    EXOTEL_RECORDING_ALLOWED_HOST_SUFFIXES: List[str] = [
        ".exotel.com",
        ".exotel.in",
        ".amazonaws.com",
    ]
    # IVR-A3 — server-side bridge to existing /api/chat (CitizenAccount id or phone lookup)
    IVR_CITIZEN_ACCOUNT_ID: str = ""
    IVR_SYSTEM_ACCOUNT_PHONE: str = ""
    IVR_PUBLIC_BASE_URL: str = ""
    IVR_AUDIO_TOKEN_TTL_SECONDS: float = 300.0
    IVR_AUDIO_MAX_BYTES: int = 10 * 1024 * 1024
    IVR_MAX_TURNS: int = 10
    IVR_SESSION_TTL_SECONDS: float = 1800.0
    IVR_MAX_ACTIVE_SESSIONS: int = 1000
    IVR_MAX_ACTIVE_AUDIO_TOKENS: int = 2000
    IVR_MAX_CALL_SID_LENGTH: int = 64
    IVR_MAX_RECORDING_URL_LENGTH: int = 2048
    IVR_RATE_LIMIT_WINDOW_SECONDS: float = 60.0
    IVR_RATE_LIMIT_PER_CALLSID: int = 120
    IVR_RATE_LIMIT_PER_IP: int = 300
    IVR_RATE_LIMIT_INVALID_PER_IP: int = 60
    IVR_RATE_LIMIT_AUDIO_PER_IP: int = 120
    IVR_RATE_LIMIT_MAX_KEYS: int = 4096
    IVR_WEBHOOK_SHARED_SECRET: str = ""
    # Accept the webhook secret via ?ivr_secret= query (query strings may be logged
    # by proxies; prefer the X-GramSakhi-Ivr-Secret header and disable this in production).
    IVR_WEBHOOK_SECRET_ALLOW_QUERY: bool = True
    # Only trust X-Forwarded-For for IVR rate limiting when a trusted reverse proxy
    # sets it; otherwise the socket peer address is used.
    IVR_TRUST_PROXY_HEADERS: bool = False
    # Direct audio upload (POST /api/ivr/transcribe) is a dev/test path; production
    # returns 404 unless explicitly enabled.
    IVR_DIRECT_UPLOAD_IN_PRODUCTION: bool = False
    # Spec-name alias for IVR_AUDIO_TOKEN_TTL_SECONDS; when > 0 it takes precedence.
    IVR_PUBLIC_AUDIO_TOKEN_TTL: float = 0.0

    # CORS — local dev + deployed static frontend on Render (credentials enabled; no wildcard)
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5176",
        "http://127.0.0.1:5176",
        "https://gramasakhi-1.onrender.com",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_backend_cors_origins(cls, value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    return [raw]
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
                return [raw]
            if "," in raw:
                return [part.strip() for part in raw.split(",") if part.strip()]
            return [raw]
        return value

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        # Empty OS env vars (common in IDE shells) must not override .env values
        env_ignore_empty=True,
    )


settings = Settings()
