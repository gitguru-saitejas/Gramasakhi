"""Deterministic metric calculations. Unmeasurable values stay N/A."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence


def mean(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def percentile(values: Sequence[float], p: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * (p / 100.0)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return float(ordered[lo])
    weight = rank - lo
    return float(ordered[lo] * (1 - weight) + ordered[hi] * weight)


def precision_at_k(relevant: Sequence[str], retrieved: Sequence[str], k: int) -> Optional[float]:
    if not relevant:
        return None
    top = list(retrieved)[:k]
    if not top:
        return 0.0
    rel = {item.lower() for item in relevant if item}
    hits = sum(1 for item in top if item and item.lower() in rel)
    return hits / float(k)


def recall_at_k(relevant: Sequence[str], retrieved: Sequence[str], k: int) -> Optional[float]:
    if not relevant:
        return None
    rel = {item.lower() for item in relevant if item}
    if not rel:
        return None
    top = {item.lower() for item in list(retrieved)[:k] if item}
    return len(rel & top) / float(len(rel))


def f1(precision: Optional[float], recall: Optional[float]) -> Optional[float]:
    if precision is None or recall is None:
        return None
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def binary_prf(pairs: Iterable[tuple[bool, bool]]) -> Dict[str, Optional[float]]:
    """pairs of (expected_positive, predicted_positive)."""
    tp = fp = fn = tn = 0
    count = 0
    for expected, predicted in pairs:
        count += 1
        if expected and predicted:
            tp += 1
        elif not expected and predicted:
            fp += 1
        elif expected and not predicted:
            fn += 1
        else:
            tn += 1
    if count == 0:
        return {"accuracy": None, "precision": None, "recall": None, "f1": None, "support": 0}
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    accuracy = (tp + tn) / count
    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1(precision, recall),
        "support": count,
    }


def group_mean(rows: Iterable[Dict[str, Any]], key: str, value_key: str) -> Dict[str, Optional[float]]:
    buckets: Dict[str, List[float]] = defaultdict(list)
    for row in rows:
        value = row.get(value_key)
        if isinstance(value, (int, float)):
            buckets[str(row.get(key))].append(float(value))
    return {name: mean(vals) for name, vals in sorted(buckets.items())}
