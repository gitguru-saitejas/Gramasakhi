#!/usr/bin/env python3
"""Phase 3A Step 1 — eligibility pipeline diagnostic (read-only)."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.services.citizen_assistance import build_assistance_context, classify_citizen_intent
from app.services.eligibility_criteria import enrich_assistance_fields_from_criteria, extract_eligibility_criteria
from app.services.eligibility_questioning import extract_scenario_facts_from_text
from app.services.myscheme_service import requested_scheme_identity
from app.services.scenario_eligibility import is_scenario_eligibility_query, try_evaluate_scenario_eligibility


def main() -> int:
    bench = json.loads((ROOT / "evaluation/datasets/benchmark_v1.json").read_text(encoding="utf-8"))
    results = json.loads((ROOT / "evaluation/results/benchmark_v2.json").read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in results.get("raw_runs", [])}
    cases = [c for c in bench["cases"] if c.get("category") == "eligibility"]
    rows = []
    for c in cases:
        q = c["question"]
        intent = classify_citizen_intent(q).value
        ctx = build_assistance_context(original_query=q)
        scheme = ctx.detected_scheme
        scheme_identity = requested_scheme_identity(q) or {}
        facts = extract_scenario_facts_from_text(q)
        is_scenario = is_scenario_eligibility_query(q)
        r = by_id.get(c["id"], {})
        resp = r.get("response") or {}
        sources = resp.get("sources") or []
        docs = []
        for s in sources:
            if isinstance(s, dict):
                docs.append(
                    {
                        "content": s.get("content") or s.get("text") or s.get("snippet") or "",
                        "scheme_name": s.get("scheme_name") or "",
                        "source": s.get("source") or s.get("url") or "",
                        "metadata": s.get("metadata") or {},
                    }
                )
        criteria = None
        scenario_eval = None
        required = missing = []
        if docs and resp.get("validated"):
            criteria = extract_eligibility_criteria(
                docs, scheme_identity=scheme_identity, query=q
            )
            required, _, missing = enrich_assistance_fields_from_criteria(criteria)
            scenario_eval = try_evaluate_scenario_eligibility(
                query=q,
                criteria=criteria,
                scheme_name=scheme_identity.get("scheme_name"),
                scheme_id=scheme_identity.get("scheme_id"),
                evidence_validated=True,
            )
        exp = (c.get("ground_truth") or {}).get("eligibility_status")
        api = resp.get("eligibility_status")
        det_status = scenario_eval.status if scenario_eval else None
        llm_decides = scenario_eval is None

        if intent not in ("ELIGIBILITY", "PERSONAL_ELIGIBILITY"):
            fail = "A"
        elif not resp.get("validated"):
            fail = "F"
        elif not docs:
            fail = "F"
        elif criteria and not criteria.criteria:
            fail = "D"
        elif is_scenario and not facts:
            fail = "C"
        elif is_scenario and scenario_eval is None:
            fail = "C" if not facts else "E"
        elif not is_scenario and intent == "ELIGIBILITY":
            fail = "H"
        elif det_status and api is None:
            fail = "G"
        else:
            fail = "H"

        rows.append(
            {
                "id": c["id"],
                "scheme": c.get("scheme"),
                "expected": exp,
                "intent": intent,
                "detected_scheme": scheme,
                "validated": resp.get("validated"),
                "sources_n": len(sources),
                "is_scenario": is_scenario,
                "facts": facts,
                "criteria_n": len(criteria.criteria) if criteria else 0,
                "required": required,
                "missing": missing,
                "det_status": det_status,
                "api": api,
                "llm_decides": llm_decides,
                "fail": fail,
                "question": q,
            }
        )

    print("FAIL_COUNTS", dict(Counter(r["fail"] for r in rows)))
    print("api_none", sum(1 for r in rows if r["api"] is None))
    print("scenario_true", sum(1 for r in rows if r["is_scenario"]))
    print("det_ran", sum(1 for r in rows if r["det_status"]))
    print("validated_false", sum(1 for r in rows if not r["validated"]))
    for r in rows:
        print(
            f"{r['id']}|exp={r['expected']}|intent={r['intent']}|scen={r['is_scenario']}|val={r['validated']}|"
            f"facts={r['facts']}|crit={r['criteria_n']}|req={r['required']}|det={r['det_status']}|api={r['api']}|"
            f"{r['fail']}|{r['question'][:100]}"
        )
    out = ROOT / "evaluation/reports/eligibility_diagnostic_3a.json"
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
