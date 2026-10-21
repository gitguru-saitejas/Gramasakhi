"""Benchmark v1 methodology-fixed evaluators (v2).

Legacy v1 scoring remains in ``evaluation.metrics.evaluate`` for reproducibility.
"""

from evaluation.metrics.v2.evaluate import aggregate_scores_v2, score_case_v2

__all__ = ["aggregate_scores_v2", "score_case_v2"]
