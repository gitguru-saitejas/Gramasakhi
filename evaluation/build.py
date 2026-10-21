"""Build benchmark_v1 from repository sources."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict

from evaluation.extract import build_structured_truth
from evaluation.generate import generate_candidates
from evaluation.inventory import allowed_source_urls, inventory_sources
from evaluation.paths import (
    BENCHMARK_PATH,
    BUILD_REPORT_PATH,
    REPO_ROOT,
    SEED_DOCUMENTS,
    TARGET_QUOTAS,
    VALIDATION_REPORT_PATH,
)
from evaluation.validate import assign_stable_ids, validate_benchmark


def build_benchmark() -> Dict[str, Any]:
    inventory = inventory_sources()
    schemes, excerpts = build_structured_truth()
    candidates = generate_candidates(excerpts)
    allowed_urls = allowed_source_urls(inventory)
    allowed_paths = {spec["path"].replace("\\", "/") for spec in SEED_DOCUMENTS}
    gate = validate_benchmark(candidates, allowed_urls=allowed_urls, allowed_paths=allowed_paths)
    accepted = assign_stable_ids(gate["accepted"])

    distribution = {
        "category": dict(Counter(case["category"] for case in accepted)),
        "language": dict(Counter(case["language"] for case in accepted)),
        "difficulty": dict(Counter(case["difficulty"] for case in accepted)),
        "scheme": dict(Counter(case["scheme"] for case in accepted)),
    }
    coverage = {
        "authoritative_seed_documents": [
            {
                "id": doc.get("id"),
                "scheme_id": doc.get("scheme_id"),
                "path": doc.get("path"),
                "present": doc.get("present"),
                "line_count": doc.get("line_count"),
            }
            for doc in inventory.get("authoritative_seed_documents") or []
        ],
        "catalog_schemes_without_seed": [
            item["id"]
            for item in inventory.get("catalog_schemes_metadata_only") or []
            if not item.get("has_seed_document")
        ],
        "n_excerpts": len(excerpts),
        "n_structured_schemes": len(schemes),
    }
    shortages = {}
    for category, quota in TARGET_QUOTAS.items():
        have = distribution["category"].get(category, 0)
        if have < quota:
            shortages[category] = {"target": quota, "accepted": have, "short": quota - have}

    payload = {
        "version": "benchmark_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository_root": str(REPO_ROOT),
        "n_candidates": len(candidates),
        "n_accepted": len(accepted),
        "n_rejected": len(gate["rejected"]),
        "target_quotas": TARGET_QUOTAS,
        "distribution": distribution,
        "source_coverage": coverage,
        "shortages": shortages,
        "validation_summary": {
            "rejected": gate["rejected"],
            "duplicates": gate["duplicate_pairs"],
        },
        "cases": accepted,
    }
    BENCHMARK_PATH.parent.mkdir(parents=True, exist_ok=True)
    BENCHMARK_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    VALIDATION_REPORT_PATH.write_text(
        json.dumps({"rejected": gate["rejected"], "duplicates": gate["duplicate_pairs"]}, indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    BUILD_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    BUILD_REPORT_PATH.write_text(
        "\n".join(
            [
                "# GramSakhi Benchmark v1 build",
                "",
                f"Accepted cases: {len(accepted)}",
                f"Rejected cases: {len(gate['rejected'])}",
                "",
                "## Distribution",
                json.dumps(distribution, indent=2),
                "",
                "## Shortages vs target ~100",
                json.dumps(shortages or {"none": "all quotas met or exceeded after validation"}, indent=2),
                "",
                "## Gap",
                inventory.get("gap", ""),
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return payload
