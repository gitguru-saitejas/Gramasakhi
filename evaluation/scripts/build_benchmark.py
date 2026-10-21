#!/usr/bin/env python3
"""Inventory sources, extract truth, generate, validate, and write benchmark_v1."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.build import build_benchmark  # noqa: E402


def main() -> int:
    payload = build_benchmark()
    print(f"accepted={payload['n_accepted']} rejected={payload['n_rejected']} candidates={payload['n_candidates']}")
    print(json.dumps(payload["distribution"], indent=2))
    if payload.get("shortages"):
        print("shortages:")
        print(json.dumps(payload["shortages"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
