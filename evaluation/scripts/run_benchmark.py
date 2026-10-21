#!/usr/bin/env python3
"""Send benchmark_v1 through the existing GramSakhi HTTP API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.runners.execute import run_benchmark  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run GramSakhi Benchmark v1")
    parser.add_argument("--limit", type=int, default=None, help="Optional case cap for smoke runs")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--resume", action="store_true", help="Skip cases already in the checkpoint file")
    parser.add_argument("--start-after", default=None, help="Resume after this case id, e.g. gsb1-0038")
    parser.add_argument("--backfill-missing", action="store_true", help="After resume, run any earlier uncheckpointed cases")
    args = parser.parse_args()
    result = run_benchmark(
        limit=args.limit,
        timeout=args.timeout,
        resume=args.resume,
        start_after=args.start_after,
        backfill_missing=args.backfill_missing,
    )
    print(result["api_status"])
    print(json.dumps(result["metrics"], indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
