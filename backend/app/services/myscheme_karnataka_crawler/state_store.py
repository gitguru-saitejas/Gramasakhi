from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.myscheme_karnataka_crawler.config import DATA_DIR, SCHEMES_JSON, STATE_JSON


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_schemes(path: Path = SCHEMES_JSON) -> List[Dict[str, Any]]:
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_schemes(schemes: List[Dict[str, Any]], path: Path = SCHEMES_JSON) -> None:
    ensure_data_dirs()
    path.write_text(json.dumps(schemes, indent=2, ensure_ascii=False), encoding="utf-8")


def load_state() -> Dict[str, Any]:
    if not STATE_JSON.is_file():
        return {"updated_at": _utc_now(), "stats": {}}
    return json.loads(STATE_JSON.read_text(encoding="utf-8"))


def save_state(state: Dict[str, Any]) -> None:
    ensure_data_dirs()
    state["updated_at"] = _utc_now()
    STATE_JSON.write_text(json.dumps(state, indent=2), encoding="utf-8")


def merge_discovered(existing: List[Dict[str, Any]], fresh: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_id = {s["scheme_id"]: s for s in existing if s.get("scheme_id")}
    for rec in fresh:
        sid = rec.get("scheme_id")
        if not sid:
            continue
        if sid in by_id:
            prev = by_id[sid]
            for k in ("scheme_name", "scheme_url", "ministry", "source_url"):
                if rec.get(k):
                    prev[k] = rec[k]
        else:
            by_id[sid] = rec
    return sorted(by_id.values(), key=lambda x: x.get("scheme_id") or "")


def scheme_by_id(schemes: List[Dict[str, Any]], scheme_id: str) -> Optional[Dict[str, Any]]:
    for s in schemes:
        if s.get("scheme_id") == scheme_id:
            return s
    return None
