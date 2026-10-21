from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import JSONResponse
import logging
import os
import json
import sys
import threading
import urllib.request

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.database.session import engine, Base
from app.api.endpoints import auth, super_admin, chat, voice, ivr

# Import active GramSakhi models so Base recognizes them before table creation
from app.models import citizen_account, user, rag, audit, conversation  # noqa: F401

# Ensure static directory exists
os.makedirs("static/uploads", exist_ok=True)

# Automatically create missing database tables on startup
if "pytest" not in sys.modules and "unittest" not in sys.modules:
    if settings.DATABASE_URL.startswith("sqlite"):
        _db_host = settings.DATABASE_URL
    else:
        _db_host = "redacted"
    print(f"Database: {engine.dialect.name} -> {_db_host}", flush=True)
    if engine.dialect.name != "postgresql":
        print(
            "WARNING: Not using Supabase Postgres. Check DATABASE_URL in backend/.env "
            "and restart after killing any old uvicorn processes.",
            flush=True,
        )
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(
            f"WARNING: Database schema create_all failed ({type(e).__name__}). "
            "API will start; /health/db will report the error. Check network/DNS for Supabase.",
            flush=True,
        )
    try:
        from app.database.migrations.run_migrations import ensure_sqlite_columns

        ensure_sqlite_columns(engine)
    except Exception as e:
        print(f"Schema ensure skipped: {e}", flush=True)


_DEFAULT_SECRET_KEY = "gramsakhi_very_secret_key_change_me_in_production"


def _guard_production_config() -> None:
    """Refuse to start with known-insecure JWT secret on Postgres (non-test)."""
    if any(name in sys.modules for name in ("pytest", "unittest")):
        return
    if settings.SECRET_KEY != _DEFAULT_SECRET_KEY:
        return
    if settings.DATABASE_URL.startswith("sqlite"):
        print(
            "WARNING: Using default SECRET_KEY with SQLite. "
            "Set SECRET_KEY in backend/.env before production deployment.",
            flush=True,
        )
        return
    print(
        "FATAL: SECRET_KEY is still the default while DATABASE_URL points to PostgreSQL. "
        "Set a unique SECRET_KEY in backend/.env.",
        flush=True,
    )
    sys.exit(1)


_guard_production_config()


def _log_dev_otp_console_hint() -> None:
    if any(name in sys.modules for name in ("pytest", "unittest")):
        return
    from app.services.otp_console import otp_console_simulator_enabled

    if otp_console_simulator_enabled():
        from app.services.otp_console import DEV_OTP_MIRROR_FILE

        print(
            "GramSakhi OTP console simulator: ENABLED — codes print as VERIFICATION OTP",
            flush=True,
        )
        print(
            f"OTP mirror file (always updated on send): {DEV_OTP_MIRROR_FILE}",
            flush=True,
        )
        return
    env = settings.APP_ENV.strip().lower()
    if settings.OTP_CONSOLE_SIMULATOR_ENABLED and env in ("production", "prod"):
        print(
            "NOTE: OTP terminal output is disabled (APP_ENV=production). "
            "For local login testing set APP_ENV=development in backend/.env, "
            "or enable OTP_DEV_RETRIEVAL with a dev key.",
            flush=True,
        )


_log_dev_otp_console_hint()


def _guard_ivr_production_config() -> None:
    if any(name in sys.modules for name in ("pytest", "unittest")):
        return
    if settings.APP_ENV.strip().lower() != "production":
        return
    from app.services.ivr.ivr_config import collect_ivr_production_config_errors

    errors = collect_ivr_production_config_errors(settings)
    if not errors:
        return
    print(f"FATAL: IVR production configuration invalid: {'; '.join(errors)}", flush=True)
    sys.exit(1)


_guard_ivr_production_config()


def _check_ollama_connection() -> bool:
    try:
        url = f"{settings.OLLAMA_API_URL.rstrip('/')}/api/embed"
        payload = json.dumps({"model": settings.EMBEDDING_MODEL, "input": "ping"}).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            _ = json.loads(resp.read().decode("utf-8"))
        print("Ollama embedding service is reachable.", flush=True)
        return True
    except Exception as e:
        print(f"Failed to reach Ollama embedding service: {e}", flush=True)
        return False


# Swagger UI / OpenAPI are development aids; production must not expose the
# full API surface description.
_IS_PRODUCTION_ENV = settings.APP_ENV.strip().lower() == "production"

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=None if _IS_PRODUCTION_ENV else f"{settings.API_V1_STR}/openapi.json",
    docs_url=None if _IS_PRODUCTION_ENV else "/docs",
    redoc_url=None if _IS_PRODUCTION_ENV else "/redoc",
)

_api_logger = logging.getLogger("gramsakhi.api")


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(_request: Request, exc: SQLAlchemyError):
    _api_logger.warning("database_error err=%s", type(exc).__name__)
    return JSONResponse(
        status_code=503,
        content={"detail": "Service temporarily unavailable. Please try again."},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    _api_logger.exception("unhandled_api_error err=%s", type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    if settings.SECURITY_HEADERS_ENABLED:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(self), geolocation=()",
        )
        path = request.url.path or ""
        if path.startswith("/api/auth") or path.startswith("/api/v1/super-admin/auth"):
            response.headers["Cache-Control"] = "no-store"
        if settings.APP_ENV.strip().lower() == "production":
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
            )
            if request.url.scheme == "https":
                response.headers.setdefault(
                    "Strict-Transport-Security",
                    "max-age=31536000; includeSubDomains",
                )
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.BACKEND_CORS_ORIGINS or []),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


def _warm_reranker() -> None:
    """Load the CrossEncoder off the request path so the first query isn't slow."""
    try:
        from app.services.cross_encoder import get_reranker

        get_reranker(settings.CROSS_ENCODER_MODEL).rerank(
            "warmup", [{"content": "warmup"}], top_k=1
        )
        print("CrossEncoder reranker warmed.", flush=True)
    except Exception as e:
        print(f"CrossEncoder warmup skipped: {e}", flush=True)


@app.on_event("startup")
async def startup_event():
    if "unittest" in sys.modules or "pytest" in sys.modules:
        return
    # Safe config summary (never print secrets)
    print(
        f"Config: Database={'PostgreSQL' if engine.dialect.name == 'postgresql' else engine.dialect.name}; "
        f"Supabase={'configured' if settings.SUPABASE_URL else 'missing'}; "
        f"Storage={'configured' if settings.SUPABASE_SERVICE_ROLE_KEY else 'missing'}; "
        f"Ollama={'configured'}; "
        f"Embed={settings.EMBEDDING_MODEL}/{settings.EMBEDDING_DIMENSIONS}; "
        f"LLM={settings.OLLAMA_LLM_MODEL or settings.OLLAMA_MODEL}",
        flush=True,
    )
    _check_ollama_connection()
    try:
        from app.background_jobs.web_ingest_scheduler import start_web_ingest_scheduler_if_enabled

        start_web_ingest_scheduler_if_enabled()
    except Exception as e:
        print(f"Web ingest scheduler not started: {e}", flush=True)

    if settings.HYBRID_RERANK_ENABLED:
        threading.Thread(target=_warm_reranker, daemon=True).start()


# Local knowledge-base files are served only via authenticated admin download.
# Do not mount /static — that previously exposed /static/uploads without auth.


app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(chat.router, prefix=f"{settings.API_V1_STR}/chat", tags=["chat"])
app.include_router(voice.router, prefix=f"{settings.API_V1_STR}/chat", tags=["voice"])
app.include_router(ivr.router, prefix=f"{settings.API_V1_STR}/ivr", tags=["ivr"])
app.include_router(super_admin.router, prefix="/api/v1/super-admin", tags=["admin"])


@app.get("/health/stt")
def health_stt_root():
    from app.services.voice.stt_service import get_stt_health

    return get_stt_health()


@app.get("/health/tts")
def health_tts_root():
    from app.services.voice.tts_service import get_tts_health

    return get_tts_health()


@app.get("/")
def read_root():
    return {
        "message": "Welcome to GramSakhi API",
        "project": "GramSakhi: RAG-Based Vernacular GenAI LLM + IVR System for Last-Mile Governance",
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "gramsakhi"}


@app.get("/health/db")
def db_health():
    """Report which database the live process is actually using."""
    from sqlalchemy import text
    from app.database.session import engine

    url = settings.DATABASE_URL
    dialect = engine.dialect.name
    if url.startswith("sqlite"):
        host = url
    else:
        host = "redacted"

    ok = False
    detail = None
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            ok = True
    except Exception as e:  # noqa: BLE001
        detail = "connection_failed"
        _api_logger.warning("health_db_failed err=%s", type(e).__name__)

    return JSONResponse(
        status_code=200 if ok else 503,
        content={
            "ok": ok,
            "dialect": dialect,
            "using_supabase_postgres": dialect == "postgresql" and "supabase.co" in url,
            "host": host,
            "detail": detail,
        },
    )


@app.get("/health/ollama")
def ollama_health():
    reachable = _check_ollama_connection()
    llm_status = {}
    try:
        from app.services.llm_service import check_ollama_llm

        llm_status = check_ollama_llm()
    except Exception as e:  # noqa: BLE001
        _api_logger.warning("health_ollama_failed err=%s", type(e).__name__)
        llm_status = {
            "ollama_available": False,
            "model_available": False,
            "detail": "check_failed",
        }
    return {
        "ollama_reachable": reachable,
        "embedding_reachable": reachable,
        "ollama_available": llm_status.get("ollama_available", reachable),
        "model_available": llm_status.get("model_available", False),
        "llm_model": llm_status.get("model"),
        "detail": llm_status.get("detail"),
    }


@app.get("/health/supabase")
def supabase_health():
    from app.services.storage import check_supabase_connection

    return check_supabase_connection()


@app.get("/health/system")
def system_health():
    """Unified pre-demo / ops system check (no secrets)."""
    from app.services.system_check import format_system_check_text, run_system_check

    report = run_system_check()
    report["summary_text"] = format_system_check_text(report)
    return report
