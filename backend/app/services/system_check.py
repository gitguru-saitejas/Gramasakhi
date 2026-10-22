"""
GramSakhi production-style system check (no secrets in output).

Used by GET /health/system and scripts/gramsakhi_system_check.py.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.core.config import settings
from app.services.index_builder import default_index_dir


def _status(ok: bool, detail: str = "") -> Dict[str, Any]:
    return {"status": "PASS" if ok else "FAIL", "detail": detail or None}


def _check_database() -> Dict[str, Any]:
    from sqlalchemy import text
    from app.database.session import engine

    dialect = engine.dialect.name
    url = settings.DATABASE_URL or ""
    host = "redacted"
    if url.startswith("sqlite"):
        host = "sqlite"

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        ok = dialect == "postgresql"
        detail = f"{dialect} -> {host}"
        if not ok:
            detail += " — demo expects Supabase Postgres"
        return {
            **_status(ok, detail),
            "dialect": dialect,
            "using_supabase_postgres": dialect == "postgresql" and "supabase.co" in url,
        }
    except Exception as e:  # noqa: BLE001
        return {**_status(False, f"{type(e).__name__}"), "dialect": dialect}


def _check_supabase_storage() -> Dict[str, Any]:
    try:
        from app.services.storage import check_supabase_connection

        if not settings.SUPABASE_URL:
            return _status(False, "SUPABASE_URL not configured")
        if not settings.SUPABASE_SERVICE_ROLE_KEY:
            return _status(False, "service role key not configured")

        result = check_supabase_connection() or {}
        ok = bool(result.get("storage_reachable")) or bool(result.get("can_write_storage"))
        detail_parts = []
        if result.get("bucket"):
            detail_parts.append(f"bucket={result.get('bucket')}")
        if result.get("can_write_storage"):
            detail_parts.append("writable")
        elif result.get("storage_reachable"):
            detail_parts.append("reachable")
        if result.get("detail"):
            detail_parts.append(str(result["detail"])[:100])
        return {**_status(ok, "; ".join(detail_parts) or "configured")}
    except Exception as e:  # noqa: BLE001
        return _status(False, type(e).__name__)


def _check_ollama() -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    from app.services.runtime_profile import is_cloud_runtime

    if is_cloud_runtime():
        from app.services.gemini_llm import check_gemini_llm

        gem = check_gemini_llm()
        llm_ok = bool(gem.get("gemini_configured"))
        llm_detail = gem.get("model") or "gemini"
        emb_ok = bool((settings.GEMINI_API_KEY or "").strip())
        emb_detail = settings.GEMINI_EMBEDDING_MODEL
        return (
            _status(True, "cloud runtime (Ollama not required)"),
            _status(emb_ok, emb_detail),
            _status(llm_ok, llm_detail),
        )

    base = (settings.OLLAMA_API_URL or settings.OLLAMA_BASE_URL or "").rstrip("/")
    ollama_ok = False
    tags: List[str] = []
    try:
        req = urllib.request.Request(f"{base}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        ollama_ok = True
        tags = [m.get("name") or m.get("model") or "" for m in (data.get("models") or [])]
    except Exception as e:  # noqa: BLE001
        return (
            _status(False, type(e).__name__),
            _status(False, "Ollama unreachable"),
            _status(False, "Ollama unreachable"),
        )

    def _model_present(name: str) -> bool:
        n = (name or "").strip()
        if not n:
            return False
        return any(t == n or t.startswith(n + ":") or n.startswith(t.split(":")[0]) for t in tags if t)

    emb_model = settings.EMBEDDING_MODEL
    llm_model = settings.OLLAMA_LLM_MODEL or settings.OLLAMA_MODEL
    llm_provider = (settings.LLM_PROVIDER or "ollama").strip().lower()

    # Probe embedding endpoint (stronger than tag list alone)
    emb_probe = False
    try:
        payload = json.dumps({"model": emb_model, "input": "ping"}).encode("utf-8")
        req = urllib.request.Request(
            f"{base}/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            _ = json.loads(resp.read().decode("utf-8"))
        emb_probe = True
    except Exception:
        emb_probe = _model_present(emb_model)

    if llm_provider == "gemini":
        from app.services.gemini_llm import check_gemini_llm, get_gemini_model

        gem = check_gemini_llm()
        llm_ok = bool(gem.get("gemini_configured") and gem.get("gemini_available"))
        llm_detail = get_gemini_model()
        if not gem.get("gemini_configured"):
            llm_detail = "GEMINI_API_KEY missing"
        elif not gem.get("gemini_available"):
            llm_detail = f"{get_gemini_model()} ({gem.get('detail')})"
    else:
        llm_ok = _model_present(llm_model)
        llm_detail = llm_model

    return (
        _status(ollama_ok, base.replace("http://", "").replace("https://", "")),
        _status(emb_probe, emb_model),
        _status(llm_ok, llm_detail),
    )


def _check_whisper() -> Dict[str, Any]:
    if not settings.STT_ENABLED:
        return _status(False, "STT_ENABLED=false")
    try:
        from app.services.voice.stt_service import get_stt_health

        h = get_stt_health() or {}
        ok = bool(h.get("available") or h.get("ok") or h.get("ready"))
        detail = h.get("detail") or h.get("model") or settings.STT_MODEL
        return _status(ok, str(detail)[:120] if detail else settings.STT_MODEL)
    except Exception as e:  # noqa: BLE001
        try:
            import faster_whisper  # noqa: F401

            return _status(True, f"faster-whisper import ok; model={settings.STT_MODEL}")
        except Exception:
            return _status(False, type(e).__name__)


def _check_tts() -> Dict[str, Any]:
    if not settings.TTS_ENABLED:
        return _status(False, "TTS_ENABLED=false")
    try:
        from app.services.voice.tts_service import get_tts_health

        h = get_tts_health() or {}
        ok = bool(h.get("available") or h.get("ok") or h.get("ready"))
        detail = h.get("detail") or settings.TTS_MODEL
        return _status(ok, str(detail)[:120] if detail else settings.TTS_MODEL)
    except Exception as e:  # noqa: BLE001
        try:
            import edge_tts  # noqa: F401

            return _status(True, "edge-tts import ok")
        except Exception:
            return _status(False, type(e).__name__)


def _check_playwright() -> Dict[str, Any]:
    try:
        from app.services.acquisition.browser_playwright import playwright_available

        ok = bool(playwright_available())
        return _status(ok, "Chromium available" if ok else "Playwright/Chromium missing")
    except Exception as e:  # noqa: BLE001
        return _status(False, type(e).__name__)


def _check_indexes() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    idx = default_index_dir()
    faiss_path = idx / "faiss.index"
    bm25_path = idx / "bm25_model.pkl"
    meta_path = idx / "chunk_lookup.json"
    faiss_ok = faiss_path.is_file()
    bm25_ok = bm25_path.is_file()
    extra = ""
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            n = len(meta) if isinstance(meta, (list, dict)) else "?"
            extra = f"; chunks~{n}"
        except Exception:
            pass
    return (
        _status(faiss_ok, f"{faiss_path.name} @ {idx.name}{extra}" if faiss_ok else f"missing under {idx}"),
        _status(bm25_ok, f"{bm25_path.name}" if bm25_ok else f"missing under {idx}"),
    )


def _check_registry() -> Dict[str, Any]:
    try:
        from app.services import gov_source_registry as registry

        registry.ensure_curated_hosts_merged()
        stats = registry.registry_stats() or {}
        sources = registry.list_sources(enabled_only=True) or []
        hosts = {(s.get("domain") or "").lower() for s in sources}
        myscheme = any("myscheme.gov.in" in h for h in hosts)
        ok = bool(sources) and myscheme
        detail = f"{len(sources)} enabled; myscheme={'yes' if myscheme else 'NO'}"
        if stats:
            detail += f"; total={stats.get('total', stats.get('sources', '?'))}"
        return _status(ok, detail)
    except Exception as e:  # noqa: BLE001
        return _status(False, type(e).__name__)


def run_system_check() -> Dict[str, Any]:
    db = _check_database()
    storage = _check_supabase_storage()
    ollama, emb, llm = _check_ollama()
    whisper = _check_whisper()
    tts = _check_tts()
    browser = _check_playwright()
    faiss, bm25 = _check_indexes()
    registry = _check_registry()

    checks = {
        "Database": db,
        "Supabase Storage": storage,
        "Ollama": ollama,
        "Embedding Model": emb,
        "LLM Model": llm,
        "Whisper": whisper,
        "TTS": tts,
        "Playwright": browser,
        "FAISS": faiss,
        "BM25": bm25,
        "Government Registry": registry,
    }

    # Demo-critical subset (voice/browser can degrade gracefully)
    critical = ["Database", "Ollama", "Embedding Model", "LLM Model", "FAISS", "BM25", "Government Registry"]
    critical_fail = [k for k in critical if checks[k]["status"] != "PASS"]
    overall = "PASS" if not critical_fail else "FAIL"

    return {
        "overall": overall,
        "critical_failures": critical_fail,
        "checks": checks,
        "safe_config": {
            "database": "PostgreSQL" if db.get("dialect") == "postgresql" else db.get("dialect"),
            "supabase": "configured" if settings.SUPABASE_URL else "missing",
            "storage_bucket": settings.SUPABASE_STORAGE_BUCKET or "unset",
            "ollama": "configured",
            "embedding_model": settings.EMBEDDING_MODEL,
            "embedding_dimensions": settings.EMBEDDING_DIMENSIONS,
            "llm_provider": (settings.LLM_PROVIDER or "ollama").strip().lower(),
            "llm_model": (
                settings.GEMINI_MODEL
                if (settings.LLM_PROVIDER or "").strip().lower() == "gemini"
                else (settings.OLLAMA_LLM_MODEL or settings.OLLAMA_MODEL)
            ),
            "hybrid_index_dir": str(default_index_dir()),
            "live_gov_fallback": bool(settings.LIVE_GOV_FALLBACK_ENABLED),
            "stt_enabled": bool(settings.STT_ENABLED),
            "tts_enabled": bool(settings.TTS_ENABLED),
        },
    }


def format_system_check_text(report: Dict[str, Any]) -> str:
    lines = [
        "GRAMSAKHI SYSTEM CHECK",
        "----------------------",
    ]
    for name, item in (report.get("checks") or {}).items():
        status = item.get("status", "?")
        detail = item.get("detail")
        suffix = f" ({detail})" if detail else ""
        lines.append(f"{name}: {status}{suffix}")
    lines.append("")
    lines.append(f"Overall: {report.get('overall')}")
    if report.get("critical_failures"):
        lines.append("Critical failures: " + ", ".join(report["critical_failures"]))
    return "\n".join(lines)
