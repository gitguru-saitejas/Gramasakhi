# GramSakhi Benchmark v2 Report (Phase 2 Live API)

Generated at: 2026-09-15T16:31:59.350978+00:00
Results artifact: `C:\Users\tarun\Downloads\Gramasakhi\evaluation\results\benchmark_v2_phase3b.json`
API status: healthy auth_configured base=http://127.0.0.1:8000 phase=2

## 1. Executive summary

- Cases executed: **100**
- HTTP success rate: **1.0**
- Phase 2 production API with v2 evaluation methodology
- Grounding-blocked responses: **0**
- Hallucination cases: **['gsb1-0066', 'gsb1-0069']**
- Recommendation: **NEEDS TARGETED FIXES**

## 2. Environment / pre-flight

{
  "api_healthy": true,
  "api_detail": "{\"status\": \"ok\", \"service\": \"gramsakhi\"}",
  "ollama_healthy": true,
  "ollama_detail": "{'models': [{'name': 'nomic-embed-text:latest', 'model': 'nomic-embed-text:latest', 'modified_at': '2026-08-10T22:24:24.6946123+05:30', 'size': 274302450, 'digest': '0a109f422b47e3a30ba2b10eca18548e94",
  "auth_ok": true,
  "auth_detail": "configured",
  "dataset_path": "C:\\Users\\tarun\\Downloads\\Gramasakhi\\evaluation\\datasets\\benchmark_v1.json",
  "dataset_cases": 100,
  "dataset_distribution": {
    "category": {
      "factual": 40,
      "eligibility": 25,
      "unsupported": 15,
      "multilingual": 10,
      "difficult": 10
    },
    "language": {
      "en": 90,
      "hi": 5,
      "kn": 5
    },
    "difficulty": {
      "easy": 54,
      "medium": 18,
      "hard": 15,
      "adversarial": 13
    },
    "scheme": {
      "pmfby": 25,
      "shakti": 20,
      "anna-bhagya": 12,
      "pmsby": 23,
      "gruha-lakshmi": 12,
      "unspecified": 8
    }
  }
}

## 3. Dataset integrity

- Path: `C:\Users\tarun\Downloads\Gramasakhi\evaluation\datasets\benchmark_v1.json`
- Cases: 100
- Dataset file was not modified for this run.

{
  "category": {
    "factual": 40,
    "eligibility": 25,
    "unsupported": 15,
    "multilingual": 10,
    "difficult": 10
  },
  "language": {
    "en": 90,
    "hi": 5,
    "kn": 5
  },
  "difficulty": {
    "easy": 54,
    "medium": 18,
    "hard": 15,
    "adversarial": 13
  },
  "scheme": {
    "pmfby": 25,
    "shakti": 20,
    "anna-bhagya": 12,
    "pmsby": 23,
    "gruha-lakshmi": 12,
    "unspecified": 8
  }
}

## 4. Overall benchmark results

{
  "n_cases": 100,
  "success_rate": 1.0,
  "error_rate": 0.0,
  "n_errors": 0,
  "average_latency_ms": 18571.816390999957,
  "p95_latency_ms": 42258.353240001605,
  "precision_at_1": 0.0,
  "precision_at_3": 0.0,
  "precision_at_5": 0.0,
  "retrieval_recall_at_5": 0.0,
  "factual_correctness": 0.4583333333333333,
  "factual_full_correct": 27,
  "factual_partial": 1,
  "factual_evaluated": 60,
  "unsupported_detection_rate": 0.5333333333333333,
  "hallucination_rate": 0.13333333333333333,
  "eligibility": {
    "accuracy": 0.9230769230769231,
    "precision": 0.8571428571428571,
    "recall": 1.0,
    "f1": 0.923076923076923,
    "support": 13
  },
  "language_accuracy": {
    "en": 0.55,
    "hi": 0.0,
    "kn": 0.0
  },
  "difficulty_accuracy": {
    "easy": 0.44047619047619047,
    "medium": 0.625,
    "hard": 0.4,
    "adversarial": "N/A"
  },
  "category_accuracy": {
    "factual": 0.5875,
    "eligibility": 0.6,
    "unsupported": 0.5333333333333333,
    "multilingual": 0.0,
    "difficult": 0.4
  },
  "hallucination_case_ids": [
    "gsb1-0066",
    "gsb1-0069"
  ],
  "note": "Factual scores are deterministic keyphrase overlap against seed excerpts, not LLM-as-judge unless labeled otherwise. Retrieval metrics are N/A when the API returns no sources."
}

## 5. Retrieval (v2 methodology)

- Evaluable: 96
- No-source: 4
- Unevaluated: 0
- P@1: 0.78125
- P@3: 0.2604166666666667
- P@5: 0.15625
- Recall@5: 0.78125

_Unevaluated cases occur when ground truth lacks expected scheme_id._

## 6. Factual (v2)

- Overall correctness: 0.6018518518518519
- Full correct: 32 / 54
- Partial: 1
- Semantic review required: 6

## 7. Multilingual (v2)

{
  "en": 0.57,
  "hi": 1.0,
  "kn": 1.0
}

{
  "en": 0,
  "hi": 3,
  "kn": 3
}

## 8. Eligibility (v2)

{
  "accuracy": 0.56,
  "precision": 1.0,
  "recall": 0.5454545454545454,
  "f1": 0.7058823529411764,
  "support": 25,
  "uncertain_count": 10,
  "uncertain_rate": 0.4,
  "confusion_matrix": {
    "eligible_predicted_eligible": 6,
    "eligible_predicted_ineligible": 1,
    "eligible_predicted_uncertain": 4,
    "ineligible_predicted_eligible": 0,
    "ineligible_predicted_ineligible": 8,
    "ineligible_predicted_uncertain": 6
  }
}

- Scored cases: 15
- Uncertain cases: 10

### Third-person scenario cases


## 9. Unsupported-query results

- Detection rate: 0.5333333333333333

## 10. Hallucination results

- Rate: 0.13333333333333333
- Cases: ['gsb1-0066', 'gsb1-0069']
- Grounding-blocked (Phase 2 gates): 0

### Grounding-blocked responses

None detected via reason/signal inspection.

## 11. Latency

- Average ms: 18571.816390999957
- P50 ms: 11069.380399998408
- P95 ms: 42258.353240001605
- Max ms: 236569.6179000006

## 12. Historical hallucination regression

### `gsb1-0074`

- Question: N/A
- HTTP ok: True
- validated: True
- reason: evidence_sufficient
- eligibility_status: None
- sources count: 2
- claim_support: {}
- grounding_failure: {}
- answer preview: According to the evidence provided, the current MGNREGA daily wage is not explicitly stated. However, it is mentioned that the wage is deposited directly into the Bank Account or Post Office Account of the applicant and is paid within a week, or on a weekly basis.

The evidence does not provide the specific daily wage amount.
- hallucinated (legacy): False

### `gsb1-0076`

- Question: N/A
- HTTP ok: True
- validated: False
- reason: no_trusted_information
- eligibility_status: None
- sources count: 0
- claim_support: {}
- grounding_failure: {}
- answer preview: I couldn't identify the requested scheme from the trusted sources available right now.
- hallucinated (legacy): False

### `gsb1-0078`

- Question: N/A
- HTTP ok: True
- validated: True
- reason: evidence_sufficient
- eligibility_status: None
- sources count: 1
- claim_support: {}
- grounding_failure: {}
- answer preview: According to the evidence, PMSBY does not cover crop yield loss for farmers. The scheme's benefits are related to death, such as the nominee receiving Rs. 2 Lakhs in case of total and irrecoverable loss of certain body parts. There is no mention of crop yield loss or any provision for farmers in the provided evidence.
- hallucinated (legacy): False


## 13. Eligibility regression analysis

- Total eligibility cases: 25
- Third-person scenarios inspected: 0

## 14. Over-blocking / false-positive analysis

No Phase 2 grounding refusals detected by reason-code scan.

## 15. v1 baseline vs Benchmark v2 comparison

| Metric | v1 baseline (pre-Phase-2 API, v2 eval) | Benchmark v2 (Phase-2 API, v2 eval) | Delta type |
|--------|---------------------------------------:|------------------------------------:|------------|
| HTTP success | 1.0 | 1.0 | execution |
| Retrieval P@1 | 0.78125 | 0.78125 | unchanged |
| Factual correctness | 0.6574074074074074 | 0.6018518518518519 | regression |
| Eligibility accuracy | 0.32 | 0.56 | improved |
| Unsupported detection | 0.4666666666666667 | 0.5333333333333333 | improved |
| Hallucination rate | 0.2 | 0.13333333333333333 | regression |
| Avg latency ms | 23407.377742002136 | 18571.816390999957 | execution |

**Legend:** metric correction = evaluator fix only; improved/regression = Phase 2 API behavior change.

## 16. Remaining limitations

- v2 retrieval uses scheme_id identity, not chunk relevance.
- Eligibility polarity extraction is deterministic.
- Unsupported/hallucination metrics use legacy v1 detector.
- Local Ollama latency not production representative.

## 17. Final recommendation

**NEEDS TARGETED FIXES**

Evidence: HTTP success=1.0, hallucinations=['gsb1-0066', 'gsb1-0069'], grounding_blocked=0, eligibility_accuracy=0.56.


---

## Phase 3B/3B.1 post-run extensions

Generated: 2026-09-15T16:31:59.362203+00:00

### Executive summary

Measurement-only run after Phase 3B (RAG/evidence/grounding) and Phase 3B.1 (PMFBY eligibility).
Baseline for comparison: Phase 3A.1 full benchmark (`benchmark_v2_phase3a1.json`).

### Eligibility API / deterministic coverage

```json
{
  "eligibility_cases": 25,
  "api_status_populated": 16,
  "deterministic_eval_populated": 16,
  "null_eligibility_status": 9
}
```


### Phase 3B regression spot-checks

- `gsb1-0074` validated=True reason=evidence_sufficient elig_api=None halluc=False sources=2
- `gsb1-0075` validated=False reason=live_evidence_insufficient elig_api=None halluc=False sources=0
- `gsb1-0076` validated=False reason=no_trusted_information elig_api=None halluc=False sources=0
- `gsb1-0078` validated=True reason=evidence_sufficient elig_api=None halluc=False sources=1
- `gsb1-0059` validated=True reason=scenario_eligibility_evaluation elig_api=ineligible halluc=False sources=3

### Baseline comparison (Phase 3A.1 vs Phase 3B/3B.1)

| Metric | Phase 3A.1 | Phase 3B/3B.1 | Abs Δ | Rel Δ |
|--------|----------:|--------------:|------:|------:|
| HTTP success | 1.0 | 1.0 | +0.0000 | +0.0% |
| Retrieval P@1 | 0.7604166666666666 | 0.78125 | +0.0208 | +2.7% |
| Retrieval Recall@5 | 0.7708333333333334 | 0.78125 | +0.0104 | +1.4% |
| Factual correctness | 0.5925925925925926 | 0.6018518518518519 | +0.0093 | +1.6% |
| Eligibility accuracy | 0.56 | 0.56 | +0.0000 | +0.0% |
| Eligibility F1 | 0.6666666666666665 | 0.7058823529411764 | +0.0392 | +5.9% |
| Eligibility uncertain rate | 0.36 | 0.4 | +0.0400 | lower-is-better |
| Unsupported detection | 0.5333333333333333 | 0.5333333333333333 | +0.0000 | — |
| Hallucination rate | 0.13333333333333333 | 0.13333333333333333 | +0.0000 | lower-is-better |
| Avg latency ms | 17930.899329999665 | 18571.816390999957 | +640.9171 | — |
| P95 latency ms | 39833.27088500661 | 42258.353240001605 | +2425.0824 | — |

Artifacts: `C:\Users\tarun\Downloads\Gramasakhi\evaluation\results\benchmark_v2_phase3b.json` and `C:\Users\tarun\Downloads\Gramasakhi\evaluation\reports\benchmark_v2_phase3b.md`.
