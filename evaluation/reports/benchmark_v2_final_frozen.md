# GramSakhi Benchmark v2 Report (Phase 2 Live API)

Generated at: 2026-09-23T09:04:08.624845+00:00
Results artifact: `C:\Users\tarun\Downloads\Gramasakhi\evaluation\results\benchmark_v2.json`
API status: healthy auth_configured base=http://127.0.0.1:8000 phase=2

## 1. Executive summary

- Cases executed: **100**
- HTTP success rate: **1.0**
- Phase 2 production API with v2 evaluation methodology
- Grounding-blocked responses: **0**
- Hallucination cases: **['gsb1-0066']**
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
  "average_latency_ms": 17805.404778999997,
  "p95_latency_ms": 93929.84346499984,
  "precision_at_1": 0.0,
  "precision_at_3": 0.0,
  "precision_at_5": 0.0,
  "retrieval_recall_at_5": 0.0,
  "factual_correctness": 0.2,
  "factual_full_correct": 12,
  "factual_partial": 0,
  "factual_evaluated": 60,
  "unsupported_detection_rate": 0.4,
  "hallucination_rate": 0.06666666666666667,
  "eligibility": {
    "accuracy": 1.0,
    "precision": 1.0,
    "recall": 1.0,
    "f1": 1.0,
    "support": 8
  },
  "language_accuracy": {
    "en": 0.24,
    "hi": 0.0,
    "kn": 0.0
  },
  "difficulty_accuracy": {
    "easy": 0.2619047619047619,
    "medium": 0.0,
    "hard": 0.1,
    "adversarial": "N/A"
  },
  "category_accuracy": {
    "factual": 0.275,
    "eligibility": 0.64,
    "unsupported": 0.4,
    "multilingual": 0.0,
    "difficult": 0.1
  },
  "hallucination_case_ids": [
    "gsb1-0066"
  ],
  "note": "Factual scores are deterministic keyphrase overlap against seed excerpts, not LLM-as-judge unless labeled otherwise. Retrieval metrics are N/A when the API returns no sources."
}

## 5. Retrieval (v2 methodology)

- Evaluable: 50
- No-source: 50
- Unevaluated: 0
- P@1: 0.72
- P@3: 0.24
- P@5: 0.14400000000000002
- Recall@5: 0.72

_Unevaluated cases occur when ground truth lacks expected scheme_id._

## 6. Factual (v2)

- Overall correctness: 0.35185185185185186
- Full correct: 19 / 54
- Partial: 0
- Semantic review required: 6

## 7. Multilingual (v2)

{
  "en": 0.3,
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
  "accuracy": 0.64,
  "precision": 0.625,
  "recall": 0.9090909090909091,
  "f1": 0.7407407407407406,
  "support": 25,
  "uncertain_count": 3,
  "uncertain_rate": 0.12,
  "confusion_matrix": {
    "eligible_predicted_eligible": 10,
    "eligible_predicted_ineligible": 0,
    "eligible_predicted_uncertain": 1,
    "ineligible_predicted_eligible": 6,
    "ineligible_predicted_ineligible": 6,
    "ineligible_predicted_uncertain": 2
  }
}

- Scored cases: 22
- Uncertain cases: 3

### Third-person scenario cases


## 9. Unsupported-query results

- Detection rate: 0.4

## 10. Hallucination results

- Rate: 0.06666666666666667
- Cases: ['gsb1-0066']
- Grounding-blocked (Phase 2 gates): 0

### Grounding-blocked responses

None detected via reason/signal inspection.

## 11. Latency

- Average ms: 17805.404778999997
- P50 ms: 4278.986250000116
- P95 ms: 93929.84346499984
- Max ms: 252785.23579999455

## 12. Historical hallucination regression

### `gsb1-0074`

- Question: N/A
- HTTP ok: True
- validated: False
- reason: live_evidence_insufficient
- eligibility_status: None
- sources count: 0
- claim_support: {}
- grounding_failure: {}
- answer preview: I found information about the scheme, but the available verified sources did not contain enough information to answer that specific question.
- hallucinated (legacy): False

### `gsb1-0076`

- Question: N/A
- HTTP ok: True
- validated: True
- reason: nlu_clarification
- eligibility_status: None
- sources count: 0
- claim_support: {}
- grounding_failure: {}
- answer preview: Do you want to know how to apply, what documents are needed, whether you are eligible, or the benefit amount?
- hallucinated (legacy): False

### `gsb1-0078`

- Question: N/A
- HTTP ok: True
- validated: True
- reason: nlu_clarification
- eligibility_status: None
- sources count: 0
- claim_support: {}
- grounding_failure: {}
- answer preview: Do you want to know how to apply, what documents are needed, whether you are eligible, or the benefit amount?
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
| Retrieval P@1 | 0.78125 | 0.72 | regression |
| Factual correctness | 0.6574074074074074 | 0.35185185185185186 | regression |
| Eligibility accuracy | 0.32 | 0.64 | improved |
| Unsupported detection | 0.4666666666666667 | 0.4 | regression |
| Hallucination rate | 0.2 | 0.06666666666666667 | regression |
| Avg latency ms | 23407.377742002136 | 17805.404778999997 | execution |

**Legend:** metric correction = evaluator fix only; improved/regression = Phase 2 API behavior change.

## 16. Remaining limitations

- v2 retrieval uses scheme_id identity, not chunk relevance.
- Eligibility polarity extraction is deterministic.
- Unsupported/hallucination metrics use legacy v1 detector.
- Local Ollama latency not production representative.

## 17. Final recommendation

**NEEDS TARGETED FIXES**

Evidence: HTTP success=1.0, hallucinations=['gsb1-0066'], grounding_blocked=0, eligibility_accuracy=0.64.

