# GramSakhi Benchmark v1 — Re-evaluated Report (Methodology v2)

Generated at: 2026-09-02T11:16:51.437319+00:00
Source results: `C:\Users\tarun\Downloads\Gramasakhi\evaluation\results\benchmark_results.json`
Source generated at: 2026-09-02T11:00:41.915616+00:00

## 1. Executive summary

This report re-scores the **unchanged** 100 saved API responses using methodology-fixed v2 evaluators.
Legacy v1 metrics are preserved for academic reproducibility.

- Cases: **100**
- HTTP success (legacy): **1.0**
- Classification changes vs legacy: **80** cases

## 2. Dataset

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

## 3. Execution integrity

- 100/100 genuine authenticated responses (unchanged raw runs)
- Raw API responses were **not** modified
- Unique case IDs verified during re-evaluation

## 4. Retrieval

### Legacy v1

- P@1: 0.0
- P@3: 0.0
- P@5: 0.0
- Recall@5: 0.0

_Legacy comparison used literal path/URL string equality; often 0.0 despite correct scheme content._

### Re-evaluated v2 (canonical scheme_id)

- P@1: 0.78125
- P@3: 0.2638888888888889
- P@5: 0.15833333333333335
- Recall@5: 0.7916666666666666
- Evaluable cases: 96
- No-source cases: 4
- Unevaluated cases: 0
- Hit@1 cases: 75
- Miss@1 cases: 21

Normalization: API source `scheme_id`, metadata, seed paths, demo_seed URLs, and myScheme slugs → canonical scheme_id.

## 5. Factual

- Legacy keyphrase correctness: 0.5083333333333333
- Re-evaluated correctness: 0.6574074074074074
- Full correct: 34 / 54
- Partial: 3
- Semantic review required: 6

### Language breakdown (v2)

{
  "en": 0.63,
  "hi": 1.0,
  "kn": 1.0
}

{
  "en": 0,
  "hi": 3,
  "kn": 3
}

## 6. Eligibility

- Legacy accuracy: 0.4
- Re-evaluated accuracy: 0.32
- Precision: 0.6666666666666666
- Recall: 0.36363636363636365
- F1: 0.4705882352941177
- Uncertain rate: 0.52
- Uncertain cases: 13

### Confusion matrix

{
  "eligible_predicted_eligible": 4,
  "eligible_predicted_ineligible": 2,
  "eligible_predicted_uncertain": 5,
  "ineligible_predicted_eligible": 2,
  "ineligible_predicted_ineligible": 4,
  "ineligible_predicted_uncertain": 8
}

## 7. Multilingual

See language breakdown above. Hindi/Kannada numeric normalization uses Devanagari/Kannada digit mapping.
Non-numeric Indic keyphrases may be marked `semantic_review_required` rather than auto-scored.

## 8. Unsupported / hallucination (unchanged legacy)

- Unsupported detection: 0.4666666666666667
- Hallucination rate: 0.2
- Hallucination cases: ['gsb1-0074', 'gsb1-0076', 'gsb1-0078']

## 9. Latency (unchanged)

- Average ms: 23407.377742002136
- P50 ms: 8670.426850003423
- P95 ms: 78614.96981497911
- Min ms: 2365.10300001828
- Max ms: 233095.70090001216

## 10. Methodological limitations

- v2 retrieval uses scheme_id identity, not chunk-level relevance.
- Multilingual non-numeric phrases may require manual review.
- Eligibility polarity extraction is deterministic, not a full semantic engine.
- No LLM-as-judge; no human adjudication.
- Local CPU inference latency is not production representative.

## 11. Before vs after

| Metric | Legacy v1 | Re-evaluated v2 | Why different |
|--------|----------:|----------------:|---------------|
| Retrieval P@1 | 0.0 | 0.78125 | scheme_id normalization |
| Retrieval P@5 | 0.0 | 0.15833333333333335 | scheme_id normalization |
| Recall@5 | 0.0 | 0.7916666666666666 | scheme_id normalization |
| Factual correctness | 0.5083333333333333 | 0.6574074074074074 | numeric + language normalization |
| Eligibility accuracy | 0.4 | 0.32 | polarity extraction |
| Hindi factual | 0.0 | 1.0 | Indic digit normalization |
| Kannada factual | 0.0 | 1.0 | Indic digit normalization |
| Unsupported detection | 0.4666666666666667 | 0.4666666666666667 | unchanged |
| Hallucination rate | 0.2 | 0.2 | unchanged |

## 12. Classification changes

- `gsb1-0001` (factual): correct → correct — retrieval_scheme_id_method
- `gsb1-0002` (factual): correct → correct — retrieval_scheme_id_method
- `gsb1-0003` (factual): incorrect → incorrect — retrieval_scheme_id_method
- `gsb1-0004` (factual): partial → partial — retrieval_scheme_id_method
- `gsb1-0005` (factual): incorrect → incorrect — retrieval_scheme_id_method
- `gsb1-0006` (factual): correct → correct — retrieval_scheme_id_method
- `gsb1-0007` (factual): correct → correct — retrieval_scheme_id_method
- `gsb1-0008` (factual): correct → correct — retrieval_scheme_id_method
- `gsb1-0009` (factual): correct → correct — retrieval_scheme_id_method
- `gsb1-0010` (factual): incorrect → incorrect — retrieval_scheme_id_method
- `gsb1-0011` (factual): correct → correct — retrieval_scheme_id_method
- `gsb1-0012` (factual): incorrect → incorrect — retrieval_scheme_id_method
- `gsb1-0013` (factual): partial → partial — retrieval_scheme_id_method
- `gsb1-0014` (factual): partial → partial — retrieval_scheme_id_method
- `gsb1-0015` (factual): correct → correct — retrieval_scheme_id_method
- `gsb1-0016` (factual): correct → correct — retrieval_scheme_id_method
- `gsb1-0017` (factual): correct → correct — retrieval_scheme_id_method
- `gsb1-0018` (factual): correct → correct — retrieval_scheme_id_method
- `gsb1-0020` (factual): correct → correct — retrieval_scheme_id_method
- `gsb1-0022` (factual): incorrect → incorrect — retrieval_scheme_id_method
- `gsb1-0025` (factual): correct → correct — retrieval_scheme_id_method
- `gsb1-0027` (factual): correct → correct — retrieval_scheme_id_method
- `gsb1-0028` (factual): correct → correct — retrieval_scheme_id_method
- `gsb1-0029` (factual): correct → correct — retrieval_scheme_id_method
- `gsb1-0030` (factual): correct → correct — retrieval_scheme_id_method
- `gsb1-0031` (factual): correct → correct — retrieval_scheme_id_method
- `gsb1-0032` (factual): incorrect → incorrect — retrieval_scheme_id_method
- `gsb1-0033` (factual): incorrect → incorrect — retrieval_scheme_id_method
- `gsb1-0034` (factual): correct → correct — retrieval_scheme_id_method
- `gsb1-0035` (factual): incorrect → correct — factual_keyphrase_method, retrieval_scheme_id_method
- `gsb1-0036` (factual): correct → correct — retrieval_scheme_id_method
- `gsb1-0037` (factual): correct → correct — retrieval_scheme_id_method
- `gsb1-0038` (factual): incorrect → incorrect — retrieval_scheme_id_method
- `gsb1-0039` (factual): incorrect → incorrect — retrieval_scheme_id_method
- `gsb1-0040` (factual): correct → correct — retrieval_scheme_id_method
- `gsb1-0041` (eligibility): incorrect → uncertain — eligibility_polarity_method
- `gsb1-0042` (eligibility): correct → correct — retrieval_scheme_id_method
- `gsb1-0043` (eligibility): incorrect → uncertain — eligibility_polarity_method
- `gsb1-0044` (eligibility): correct → incorrect — eligibility_polarity_method, retrieval_scheme_id_method
- `gsb1-0045` (eligibility): correct → correct — retrieval_scheme_id_method
- `gsb1-0046` (eligibility): incorrect → uncertain — eligibility_polarity_method, retrieval_scheme_id_method
- `gsb1-0047` (eligibility): incorrect → uncertain — eligibility_polarity_method, retrieval_scheme_id_method
- `gsb1-0048` (eligibility): correct → correct — retrieval_scheme_id_method
- `gsb1-0049` (eligibility): incorrect → uncertain — eligibility_polarity_method, retrieval_scheme_id_method
- `gsb1-0050` (eligibility): incorrect → uncertain — eligibility_polarity_method, retrieval_scheme_id_method
- `gsb1-0051` (eligibility): incorrect → uncertain — eligibility_polarity_method, retrieval_scheme_id_method
- `gsb1-0052` (eligibility): incorrect → uncertain — eligibility_polarity_method, retrieval_scheme_id_method
- `gsb1-0053` (eligibility): incorrect → incorrect — retrieval_scheme_id_method
- `gsb1-0054` (eligibility): incorrect → uncertain — eligibility_polarity_method, retrieval_scheme_id_method
- `gsb1-0055` (eligibility): incorrect → incorrect — retrieval_scheme_id_method
- `gsb1-0056` (eligibility): incorrect → uncertain — eligibility_polarity_method, retrieval_scheme_id_method
- `gsb1-0057` (eligibility): incorrect → uncertain — eligibility_polarity_method, retrieval_scheme_id_method
- `gsb1-0058` (eligibility): correct → correct — retrieval_scheme_id_method
- `gsb1-0059` (eligibility): correct → correct — retrieval_scheme_id_method
- `gsb1-0060` (eligibility): correct → correct — retrieval_scheme_id_method
- `gsb1-0061` (eligibility): correct → correct — retrieval_scheme_id_method
- `gsb1-0062` (eligibility): correct → correct — retrieval_scheme_id_method
- `gsb1-0063` (eligibility): incorrect → incorrect — retrieval_scheme_id_method
- `gsb1-0064` (eligibility): incorrect → uncertain — eligibility_polarity_method, retrieval_scheme_id_method
- `gsb1-0065` (eligibility): correct → uncertain — eligibility_polarity_method, retrieval_scheme_id_method
- `gsb1-0081` (multilingual): incorrect → correct — factual_keyphrase_method
- `gsb1-0082` (multilingual): incorrect → correct — factual_keyphrase_method
- `gsb1-0083` (multilingual): incorrect → correct — factual_keyphrase_method, retrieval_scheme_id_method
- `gsb1-0084` (multilingual): incorrect → correct — factual_keyphrase_method, retrieval_scheme_id_method
- `gsb1-0085` (multilingual): incorrect → semantic_review_required — factual_keyphrase_method, retrieval_scheme_id_method
- `gsb1-0086` (multilingual): incorrect → semantic_review_required — factual_keyphrase_method, retrieval_scheme_id_method
- `gsb1-0087` (multilingual): incorrect → semantic_review_required — factual_keyphrase_method, retrieval_scheme_id_method
- `gsb1-0088` (multilingual): incorrect → semantic_review_required — factual_keyphrase_method, retrieval_scheme_id_method
- `gsb1-0089` (multilingual): incorrect → semantic_review_required — factual_keyphrase_method
- `gsb1-0090` (multilingual): incorrect → semantic_review_required — factual_keyphrase_method
- `gsb1-0091` (difficult): correct → correct — retrieval_scheme_id_method
- `gsb1-0092` (difficult): correct → correct — retrieval_scheme_id_method
- `gsb1-0093` (difficult): correct → correct — retrieval_scheme_id_method
- `gsb1-0094` (difficult): correct → correct — retrieval_scheme_id_method
- `gsb1-0095` (difficult): correct → correct — retrieval_scheme_id_method
- `gsb1-0096` (difficult): incorrect → incorrect — retrieval_scheme_id_method
- `gsb1-0097` (difficult): incorrect → incorrect — retrieval_scheme_id_method
- `gsb1-0098` (difficult): incorrect → incorrect — retrieval_scheme_id_method
- `gsb1-0099` (difficult): correct → correct — retrieval_scheme_id_method
- `gsb1-0100` (difficult): correct → correct — retrieval_scheme_id_method
