# No-source anomaly investigation (Phase 3B vs final frozen)

## Summary counts

| Run | Empty `response.sources` (raw) | v2 eval "no-source" (retrieval section) |
|-----|-------------------------------|-------------------------------------------|
| `benchmark_v2_phase3b.json` | 21 | 4 |
| `benchmark_v2_final_frozen.json` | 63 | 50 |

## Root finding (not a RAG index regression)

Phase 3B had **0** responses with `reason=nlu_clarification`. The final frozen run had **48** such responses (empty sources, `validated=True`). That alone explains most of the eval no-source delta: the NLU clarification short-circuit answers without retrieval, so v2 retrieval metrics treat them as no-source.

Final frozen no-source reason breakdown (63 empty-source HTTP 200 cases):

| reason | count | validated=True |
|--------|------:|---------------:|
| nlu_clarification | 48 | 48 |
| no_trusted_information | 7 | 0 |
| live_evidence_insufficient | 6 | 0 |
| query_too_short | 2 | 0 |

## Classification (case-level, final vs Phase 3B)

- **A. genuine retrieval failure**: 7 `no_trusted_information` + 6 `live_evidence_insufficient` ≈ 13 cases
- **B. evaluator/source-field issue**: 0 primary (sources truly empty in JSON)
- **C. benchmark runner issue**: resume/checkpoint on prior final run mixed with register-token bootstrap fixes; not the dominant no-source cause
- **D. index/environment issue**: unlikely — Phase 3B and final both hit same API/index; delta tracks NLU routing not FAISS/BM25 absence
- **E. legitimate no-source/refusal**: 13 refusals above + 2 query_too_short
- **F. NLU clarification routing (production behavior change)**: **48** cases — not retrieval failure; post–Phase 3B human-language layer returns clarification without RAG

## Lost sources (had sources in Phase 3B, empty in final)

43 cases regained sources in Phase 3B but not in final; 43/48 align with `nlu_clarification` in final.

## Conclusion

The ~50 eval no-source figure on the interrupted/resumed final run is **not** evidence of ~50 broken retrievals. It primarily reflects **NLU clarification routing** (48 cases) plus normal refusal paths (13). Do **not** treat the final factual-score drop (35%) as a pure architecture regression without rerunning on a fresh, single-session benchmark.
