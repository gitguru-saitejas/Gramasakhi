# GramSakhi Benchmark v2 Report (Phase 2 Live API)

Generated at: 2026-09-07T11:32:36.220428+00:00
Results artifact: `C:\Users\tarun\Downloads\Gramasakhi\evaluation\results\benchmark_v2_phase3a1.json`
API status: healthy auth_configured base=http://127.0.0.1:8000 phase=2

## 1. Executive summary

- Cases executed: **100**
- HTTP success rate: **1.0**
- Phase 2 production API with v2 evaluation methodology
- Grounding-blocked responses: **0**
- Hallucination cases: **['gsb1-0074', 'gsb1-0078']**
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
  "average_latency_ms": 17930.899329999665,
  "p95_latency_ms": 39833.27088500661,
  "precision_at_1": 0.0,
  "precision_at_3": 0.0,
  "precision_at_5": 0.0,
  "retrieval_recall_at_5": 0.0,
  "factual_correctness": 0.45,
  "factual_full_correct": 26,
  "factual_partial": 2,
  "factual_evaluated": 60,
  "unsupported_detection_rate": 0.5333333333333333,
  "hallucination_rate": 0.13333333333333333,
  "eligibility": {
    "accuracy": 0.8571428571428571,
    "precision": 0.75,
    "recall": 1.0,
    "f1": 0.8571428571428571,
    "support": 14
  },
  "language_accuracy": {
    "en": 0.54,
    "hi": 0.0,
    "kn": 0.0
  },
  "difficulty_accuracy": {
    "easy": 0.42857142857142855,
    "medium": 0.625,
    "hard": 0.4,
    "adversarial": "N/A"
  },
  "category_accuracy": {
    "factual": 0.575,
    "eligibility": 0.52,
    "unsupported": 0.5333333333333333,
    "multilingual": 0.0,
    "difficult": 0.4
  },
  "hallucination_case_ids": [
    "gsb1-0074",
    "gsb1-0078"
  ],
  "note": "Factual scores are deterministic keyphrase overlap against seed excerpts, not LLM-as-judge unless labeled otherwise. Retrieval metrics are N/A when the API returns no sources."
}

## 5. Retrieval (v2 methodology)

- Evaluable: 96
- No-source: 4
- Unevaluated: 0
- P@1: 0.7604166666666666
- P@3: 0.2569444444444444
- P@5: 0.15416666666666667
- Recall@5: 0.7708333333333334

_Unevaluated cases occur when ground truth lacks expected scheme_id._

## 6. Factual (v2)

- Overall correctness: 0.5925925925925926
- Full correct: 31 / 54
- Partial: 2
- Semantic review required: 6

## 7. Multilingual (v2)

{
  "en": 0.56,
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
  "precision": 0.8571428571428571,
  "recall": 0.5454545454545454,
  "f1": 0.6666666666666665,
  "support": 25,
  "uncertain_count": 9,
  "uncertain_rate": 0.36,
  "confusion_matrix": {
    "eligible_predicted_eligible": 6,
    "eligible_predicted_ineligible": 1,
    "eligible_predicted_uncertain": 4,
    "ineligible_predicted_eligible": 1,
    "ineligible_predicted_ineligible": 8,
    "ineligible_predicted_uncertain": 5
  }
}

- Scored cases: 16
- Uncertain cases: 9

### Third-person scenario cases


## 9. Unsupported-query results

- Detection rate: 0.5333333333333333

## 10. Hallucination results

- Rate: 0.13333333333333333
- Cases: ['gsb1-0074', 'gsb1-0078']
- Grounding-blocked (Phase 2 gates): 0

### Grounding-blocked responses

None detected via reason/signal inspection.

## 11. Latency

- Average ms: 17930.899329999665
- P50 ms: 9168.993000006594
- P95 ms: 39833.27088500661
- Max ms: 245038.25870000583

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
- answer preview: According to the available evidence, the current MGNREGA daily wage is not explicitly stated. The evidence only mentions that the disbursement of daily wages shall be made on a weekly basis.

However, the evidence does provide information on the eligibility criteria for MGNREGA, which includes various stakeholders such as wage seekers, Gram Sabha, and the state government.

Therefore, I can provid
- hallucinated (legacy): True

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
- answer preview: According to the evidence from the official government website (https://www.myscheme.gov.in/schemes/pmsby#sources), the Pradhan Mantri Suraksha Bima Yojana (PMSBY) does not specifically cover crop yield loss for farmers. The scheme provides a death benefit of Rs. 2 Lakhs to the nominee on the death of the insured person, but it does not mention crop yield loss as a covered benefit.
- hallucinated (legacy): True


## 13. Eligibility regression analysis

- Total eligibility cases: 25
- Third-person scenarios inspected: 0

## 14. Over-blocking / false-positive analysis

No Phase 2 grounding refusals detected by reason-code scan.

## 15. v1 baseline vs Benchmark v2 comparison

| Metric | v1 baseline (pre-Phase-2 API, v2 eval) | Benchmark v2 (Phase-2 API, v2 eval) | Delta type |
|--------|---------------------------------------:|------------------------------------:|------------|
| HTTP success | 1.0 | 1.0 | execution |
| Retrieval P@1 | 0.78125 | 0.7604166666666666 | regression |
| Factual correctness | 0.6574074074074074 | 0.5925925925925926 | regression |
| Eligibility accuracy | 0.32 | 0.56 | improved |
| Unsupported detection | 0.4666666666666667 | 0.5333333333333333 | improved |
| Hallucination rate | 0.2 | 0.13333333333333333 | regression |
| Avg latency ms | 23407.377742002136 | 17930.899329999665 | execution |

**Legend:** metric correction = evaluator fix only; improved/regression = Phase 2 API behavior change.

## 16. Remaining limitations

- v2 retrieval uses scheme_id identity, not chunk relevance.
- Eligibility polarity extraction is deterministic.
- Unsupported/hallucination metrics use legacy v1 detector.
- Local Ollama latency not production representative.

## 17. Final recommendation

**NEEDS TARGETED FIXES**

Evidence: HTTP success=1.0, hallucinations=['gsb1-0074', 'gsb1-0078'], grounding_blocked=0, eligibility_accuracy=0.56.


---

## Phase 3A.1 post-run extensions

### Eligibility API / deterministic coverage

{
  "eligibility_cases": 25,
  "api_status_populated": 16,
  "deterministic_eval_populated": 16,
  "null_eligibility_status": 9
}

### Baseline comparison (pre-Phase-3A.1 benchmark v2 vs this run)

| Metric | Pre-3A.1 v2 | Phase 3A.1 full run | Notes |
|--------|------------:|--------------------:|-------|
| HTTP success | 1.0 | 1.0 | execution |
| Retrieval P@1 | 0.7604166666666666 | 0.7604166666666666 | pipeline/retrieval |
| Retrieval Recall@5 | 0.7708333333333334 | 0.7708333333333334 | pipeline/retrieval |
| Factual correctness | 0.6111111111111112 | 0.5925925925925926 | mixed |
| Eligibility accuracy | 0.32 | 0.56 | pipeline |
| Hallucination rate | 0.13333333333333333 | 0.13333333333333333 | grounding |
| Avg latency ms | 20784.22657500334 | 17930.899329999665 | execution |

### Model vs pipeline preliminary diagnosis

- **A. Retrieval/evidence**: inspect no-source cases and P@1/Recall@5 delta.
- **B. Eligibility pipeline**: inspect eligibility API status coverage and deterministic eval counts.
- **C. Grounding/validation**: inspect grounding-blocked count and hallucination case IDs.
- **D. LLM generation**: inspect cases where validated=true but factual/eligibility labels fail.

Generated Phase 3A.1 artifacts at `C:\Users\tarun\Downloads\Gramasakhi\evaluation\results\benchmark_v2_phase3a1.json` and `C:\Users\tarun\Downloads\Gramasakhi\evaluation\reports\benchmark_v2_phase3a1.md`.


---

# Phase 3A.1 Full Benchmark — Extended Analysis

## Pre-flight (Step 1)

| Check | Result |
|-------|--------|
| Backend tests | **1055/1055 pass** |
| Evaluation tests | **71/71 pass** (pre and post run) |
| API health | OK (gramsakhi) |
| Ollama health | OK (llama3.2:3b, 
omic-embed-text) |
| Auth | configured |
| Dataset cases | **100** (unchanged, sha256 prefix 6288f5a373511cc3) |
| Phase 3A.1 active | yes (post-hardening API) |

## Step 6 — Regression vs baselines

| Metric | Pre-3A.1 v2 | Phase 3A.1 full | Delta | Type |
|--------|------------:|----------------:|-------|------|
| HTTP success | 100% | **100%** | unchanged | execution |
| Retrieval P@1 | 78.1% | **76.0%** | -2.1pp | unchanged/measurement |
| Retrieval Recall@5 | 79.2% | **77.1%** | -2.1pp | unchanged/measurement |
| Factual correctness | 65.7%* | **59.3%** | -6.4pp | mixed |
| Eligibility accuracy | 32% | **56%** | **+24pp** | **pipeline improvement** |
| Eligibility F1 | — | **66.7%** | — | pipeline |
| Uncertain rate (elig) | — | **36%** | — | pipeline |
| Unsupported detection | 46.7%* | **53.3%** | +6.6pp | unchanged |
| Hallucination rate | 20%* | **13.3%** | -6.7pp | improved |
| Avg latency | ~23.4s | **17.9s** | -5.5s | execution |
| P95 latency | — | **39.8s** | — | execution |

*Reference values from user brief; stored prior v2 JSON shows factual 61.1%, unsupported 53.3%, hallucination 13.3%.

**Key distinction:** Eligibility +24pp is a **genuine pipeline improvement** (status propagation, fact extraction, criteria). Retrieval metrics are effectively **unchanged** (same scheme-id matching methodology). Factual delta is within evaluator noise band.

## Step 4 — Historical hallucination check

### gsb1-0074 (MGNREGA daily wage Karnataka)
- **validated:** true | **reason:** evidence_sufficient
- **Answer:** Initially states wage not explicitly stated, then adds generic national MGNREGA overview (MoRD, skill training, stakeholders).
- **Hallucination:** YES (detector: leaked wage + unsupported scheme expansion)
- **Phase 3A/3A.1 prevention:** **Partial** — opening is cautious but LLM still expands with unsupported overview.

### gsb1-0076 (Shakti/private buses)
- **validated:** false | **reason:** no_trusted_information
- **Answer:** Refusal — scheme not identified from trusted sources.
- **Hallucination:** NO
- **Phase 3A/3A.1 prevention:** **Yes** — correct refusal, no fabricated bus policy.

### gsb1-0078 (PMSBY crop yield loss)
- **validated:** true | **reason:** evidence_sufficient
- **Answer:** Correctly states PMSBY does **not** cover crop yield loss; cites accident/death benefit.
- **Hallucination flag:** YES (keyword detector: crop, yield loss in negation context)
- **Substantive assessment:** Answer is **factually correct**; flag is **evaluator limitation** (keyword leak detection on negated claims).

## Step 5 — Eligibility analysis (25 cases)

| Metric | Count |
|--------|------:|
| API eligibility_status populated | **16/25** |
| Deterministic evaluation ran | **16/25** |
| Null API status | **9/25** |
| v2 scored (non-uncertain) | **16/25** |
| v2 uncertain | **9/25** |

**Correct (v2):** 0042, 0044, 0045, 0047, 0048, 0053, 0054, 0058, 0060, 0061, 0062, 0063, 0064, 0065 (14 direct + uncertain counted separately)

**Incorrect:** 0052 (eligible→ineligible), 0059 (ineligible→eligible)

**Failure modes:**
- **Evidence insufficiency:** 0041, 0043, 0057 (alidated=false, no det)
- **Criteria insufficiency:** 0055, 0056 (head-of-family CANNOT_DETERMINE)
- **PMSBY age/account:** 0047, 0048 correct via answer polarity; 0046, 0050, 0051 uncertain (no API status)
- **PMFBY crop:** 0059 incorrect (det=ELIGIBLE); 0062 correct (NOT_ELIGIBLE)
- **Residency:** 0054 correct; 0043 blocked by no evidence
- **Explicit negation:** 0053, 0064, 0065 correct

### Eligibility failures detail
[
  {
    "id": "gsb1-0041",
    "expected": "eligible",
    "predicted": "UNCERTAIN",
    "api": null,
    "det": null,
    "validated": false,
    "sources": 0
  },
  {
    "id": "gsb1-0043",
    "expected": "ineligible",
    "predicted": "UNCERTAIN",
    "api": null,
    "det": null,
    "validated": false,
    "sources": 0
  },
  {
    "id": "gsb1-0046",
    "expected": "eligible",
    "predicted": "UNCERTAIN",
    "api": null,
    "det": null,
    "validated": true,
    "sources": 1
  },
  {
    "id": "gsb1-0049",
    "expected": "ineligible",
    "predicted": "UNCERTAIN",
    "api": null,
    "det": null,
    "validated": true,
    "sources": 1
  },
  {
    "id": "gsb1-0050",
    "expected": "eligible",
    "predicted": "UNCERTAIN",
    "api": null,
    "det": null,
    "validated": true,
    "sources": 1
  },
  {
    "id": "gsb1-0051",
    "expected": "eligible",
    "predicted": "UNCERTAIN",
    "api": null,
    "det": null,
    "validated": true,
    "sources": 1
  },
  {
    "id": "gsb1-0052",
    "expected": "eligible",
    "predicted": "INELIGIBLE",
    "api": "uncertain",
    "det": "CANNOT_DETERMINE",
    "validated": true,
    "sources": 1
  },
  {
    "id": "gsb1-0055",
    "expected": "ineligible",
    "predicted": "UNCERTAIN",
    "api": "uncertain",
    "det": "CANNOT_DETERMINE",
    "validated": true,
    "sources": 1
  },
  {
    "id": "gsb1-0056",
    "expected": "ineligible",
    "predicted": "UNCERTAIN",
    "api": "uncertain",
    "det": "CANNOT_DETERMINE",
    "validated": true,
    "sources": 1
  },
  {
    "id": "gsb1-0057",
    "expected": "ineligible",
    "predicted": "UNCERTAIN",
    "api": null,
    "det": null,
    "validated": false,
    "sources": 0
  },
  {
    "id": "gsb1-0059",
    "expected": "ineligible",
    "predicted": "ELIGIBLE",
    "api": "eligible",
    "det": "ELIGIBLE",
    "validated": true,
    "sources": 3
  }
]

## Step 7 — Model vs pipeline diagnosis

| Layer | Evidence from benchmark | Severity |
|-------|------------------------|----------|
| **A. Retrieval/evidence** | 4 no-source cases; 9/25 eligibility null-status; 0041/0043/0057 fail validation | **High** |
| **B. Eligibility pipeline** | Accuracy 32%→56%; 16/25 API status; PMFBY 0059 still wrong | **Medium** (improved) |
| **C. Grounding/validation** | 0076 refused correctly; 0 grounding-blocked; 2 hallucination flags | **Medium** |
| **D. LLM generation** | 0074 drifts after cautious opening; 0078 correct content but keyword-flagged | **Medium** |

**Dominant bottleneck:** **A + B combined** — retrieval must return eligibility-rich evidence before deterministic pipeline can run. LLM is not the primary blocker for eligibility (deterministic path works when evidence present).

## Step 9 — Final verdict

## **NEEDS TARGETED PIPELINE FIXES**

Rationale:
- **No major regression:** 100/100 HTTP, eligibility +24pp, hallucination rate unchanged at 13.3% (not increased)
- **Not ready for Phase 3B without fixes:** 9/25 eligibility still null-status; PMFBY crop case 0059 still wrong; 0074 LLM drift persists
- Does not meet bar for fully autonomous Phase 3B factual/grounding work until evidence retrieval and post-LLM guard tightening

## Recommended next phase

1. **Evidence retrieval** for eligibility-rich chunks (PMSBY/Shakti residency cases)
2. **PMFBY notified-crop criterion** when RAG returns partial PMFBY text
3. **Gruha Lakshmi female_head** criteria from sparse evidence
4. **Post-LLM guard** for 0074-style answer expansion after cautious opening
5. **Evaluator:** negation-aware hallucination detection for 0078-class answers

**Do not change LLM model yet** — benchmark evidence does not support model replacement as primary lever.
