"""Discover authoritative scheme sources already present in the repository."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from evaluation.paths import (
    BACKEND_DATA,
    CATALOG_PATH,
    REGISTRY_PATH,
    REPO_ROOT,
    SEED_DOCUMENTS,
    SOURCE_INVENTORY_PATH,
)

_URL_RE = re.compile(r"https?://[^\s)>\]]+", re.I)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _urls_in_text(text: str) -> List[str]:
    found: List[str] = []
    for match in _URL_RE.findall(text):
        cleaned = match.rstrip(".,;\"'")
        if cleaned not in found:
            found.append(cleaned)
    return found


def inventory_sources() -> Dict[str, Any]:
    documents: List[Dict[str, Any]] = []
    for spec in SEED_DOCUMENTS:
        path = REPO_ROOT / spec["path"]
        if not path.is_file():
            documents.append({**spec, "present": False, "error": "file_missing"})
            continue
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        documents.append(
            {
                **spec,
                "present": True,
                "absolute_path": str(path),
                "bytes": path.stat().st_size,
                "line_count": len(lines),
                "sha256": _sha256(path),
                "urls_in_document": _urls_in_text(text),
                "fact_authority": True,
            }
        )

    catalog_schemes: List[Dict[str, Any]] = []
    catalog_file = REPO_ROOT / CATALOG_PATH
    if catalog_file.is_file():
        catalog = json.loads(catalog_file.read_text(encoding="utf-8"))
        seed_ids = {d["scheme_id"] for d in SEED_DOCUMENTS}
        for item in catalog.get("schemes") or []:
            catalog_schemes.append(
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "scope": item.get("scope"),
                    "state": item.get("state"),
                    "ministry": item.get("ministry"),
                    "urls": item.get("urls") or [],
                    "has_seed_document": item.get("id") in seed_ids,
                    "fact_authority": item.get("id") in seed_ids,
                    "note": (
                        "Catalog metadata (name/URL/keywords) only. "
                        "Do not treat as eligibility or benefit evidence."
                    ),
                }
            )

    registry_sources: List[Dict[str, Any]] = []
    registry_file = REPO_ROOT / REGISTRY_PATH
    if registry_file.is_file():
        registry = json.loads(registry_file.read_text(encoding="utf-8"))
        for src in registry.get("sources") or []:
            registry_sources.append(
                {
                    "id": src.get("id"),
                    "name": src.get("name"),
                    "domain": src.get("domain"),
                    "base_urls": src.get("base_urls") or [],
                    "enabled": src.get("enabled"),
                    "fact_authority": False,
                    "note": "Trusted-domain registry entry; not a scheme fact sheet.",
                }
            )

    inventory = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "backend_data": str(BACKEND_DATA),
        "authoritative_seed_documents": documents,
        "catalog_schemes_metadata_only": catalog_schemes,
        "trusted_registry_metadata_only": registry_sources,
        "authoritative_scheme_ids": [d["scheme_id"] for d in documents if d.get("present")],
        "gap": (
            "Only seed/overview text files are treated as fact authority. "
            "Catalog and registry entries without a seed document cannot ground factual or eligibility cases."
        ),
    }
    SOURCE_INVENTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SOURCE_INVENTORY_PATH.write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return inventory


def allowed_source_urls(inventory: Dict[str, Any]) -> set[str]:
    urls: set[str] = set()
    for doc in inventory.get("authoritative_seed_documents") or []:
        urls.update(doc.get("urls_in_document") or [])
    for item in inventory.get("catalog_schemes_metadata_only") or []:
        urls.update(item.get("urls") or [])
    for item in inventory.get("trusted_registry_metadata_only") or []:
        urls.update(item.get("base_urls") or [])
    return urls
