# GramSakhi Benchmark v1 report

Generated at: 2026-09-02T11:00:41.923549+00:00
API status: healthy auth_configured preflight_ok http=200 base=http://127.0.0.1:8000

## Dataset composition

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

## Source coverage

{
  "authoritative_seed_documents": [
    {
      "id": "seed-pmfby",
      "scheme_id": "pmfby",
      "path": "backend/data/demo_seeds/pmfby_scheme.txt",
      "present": true,
      "line_count": 37
    },
    {
      "id": "seed-shakti",
      "scheme_id": "shakti",
      "path": "backend/data/demo_seeds/shakti_scheme.txt",
      "present": true,
      "line_count": 47
    },
    {
      "id": "seed-anna-bhagya",
      "scheme_id": "anna-bhagya",
      "path": "backend/data/seed_schemes/anna_bhagya_overview.txt",
      "present": true,
      "line_count": 20
    },
    {
      "id": "seed-pmsby",
      "scheme_id": "pmsby",
      "path": "backend/data/seed_schemes/pmsby_overview.txt",
      "present": true,
      "line_count": 26
    },
    {
      "id": "seed-gruha-lakshmi",
      "scheme_id": "gruha-lakshmi",
      "path": "backend/data/seed_schemes/gruha_lakshmi_overview.txt",
      "present": true,
      "line_count": 28
    }
  ],
  "catalog_schemes_without_seed": [
    "pm-kisan",
    "ayushman-bharat",
    "mgnrega",
    "pmjjby",
    "ujjwala",
    "jal-jeevan",
    "pmay",
    "national-portal",
    "myscheme-hub",
    "seva-sindhu",
    "gruha-jyothi",
    "yuva-nidhi",
    "karnataka-rdpr",
    "karnataka-ahvs",
    "karnataka-food",
    "bhagyalakshmi",
    "ysr-vahana-mitra"
  ],
  "n_excerpts": 80,
  "n_structured_schemes": 5
}

## Validation

{
  "rejected": [],
  "duplicates": []
}

## Overall metrics

{
  "n_cases": 100,
  "success_rate": 1.0,
  "error_rate": 0.0,
  "n_errors": 0,
  "average_latency_ms": 23407.377742002136,
  "p95_latency_ms": 78614.96981497911,
  "precision_at_1": 0.0,
  "precision_at_3": 0.0,
  "precision_at_5": 0.0,
  "retrieval_recall_at_5": 0.0,
  "factual_correctness": 0.5083333333333333,
  "factual_full_correct": 29,
  "factual_partial": 3,
  "factual_evaluated": 60,
  "unsupported_detection_rate": 0.4666666666666667,
  "hallucination_rate": 0.2,
  "eligibility": {
    "accuracy": "N/A",
    "precision": "N/A",
    "recall": "N/A",
    "f1": "N/A",
    "support": 0
  },
  "language_accuracy": {
    "en": 0.61,
    "hi": 0.0,
    "kn": 0.0
  },
  "difficulty_accuracy": {
    "easy": 0.44047619047619047,
    "medium": 0.625,
    "hard": 0.7,
    "adversarial": "N/A"
  },
  "category_accuracy": {
    "factual": 0.5875,
    "eligibility": 0.4,
    "unsupported": 0.4666666666666667,
    "multilingual": 0.0,
    "difficult": 0.7
  },
  "note": "Factual scores are deterministic keyphrase overlap against seed excerpts, not LLM-as-judge unless labeled otherwise. Retrieval metrics are N/A when the API returns no sources."
}

## Category metrics

{
  "factual": 0.5875,
  "eligibility": 0.4,
  "unsupported": 0.4666666666666667,
  "multilingual": 0.0,
  "difficult": 0.7
}

## Language metrics

{
  "en": 0.61,
  "hi": 0.0,
  "kn": 0.0
}

## Difficulty metrics

{
  "easy": 0.44047619047619047,
  "medium": 0.625,
  "hard": 0.7,
  "adversarial": "N/A"
}

## Latency

- average_ms: 23407.377742002136
- p95_ms: 78614.96981497911

## Failed cases

None.

## Unsupported / hallucination cases

- `gsb1-0074` leaked=['wage']
- `gsb1-0076` leaked=['private bus', 'all private']
- `gsb1-0078` leaked=['crop', 'yield loss']

## Limitations

- Ground truth is limited to five seed/overview documents in this repository.
- Catalog/registry URLs are not treated as scheme facts.
- Factual correctness is deterministic keyphrase overlap, not human adjudication.
- Retrieval Precision@k is N/A when the API returns no sources.
- Live competitor systems were not tested.
- If the API or model is unavailable, execution metrics reflect errors rather than answer quality.

