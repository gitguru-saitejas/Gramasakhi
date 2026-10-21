"""When to prefer NLU-normalized text over rewrite for retrieval."""

from __future__ import annotations

import re


def should_use_nlu_retrieval_query(original_query: str, *, rewrite_was_applied: bool) -> bool:
    if rewrite_was_applied:
        return False
    q = (original_query or "").strip()
    if not q:
        return False
    lower = q.lower()
    if re.search(
        r"\b(who is eligible|who can apply|what are the benefits|what documents|"
        r"when is the deadline|where can i apply)\b",
        lower,
    ):
        return False
    if re.search(r"\b(this|that|it|these|those)\b", lower):
        return True
    if re.search(r"\bhow (can|do|should) i (get|apply|avail|register)\b", lower):
        return True
    if re.search(r"\bwhat (papers|documents)\b", lower):
        return True
    if re.search(r"\bhow much\b", lower):
        return True
    if len(lower.split()) <= 4 and re.search(
        r"^(how|what|where|when|why|documents?|papers?|money|apply|status|"
        r"eligibility|amount|benefits?|then|next)\??$",
        lower,
    ):
        return True
    return False
