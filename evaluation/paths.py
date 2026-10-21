"""Filesystem locations for the evaluation package and repo data sources."""

from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parent
REPO_ROOT = EVAL_ROOT.parent
BACKEND_DATA = REPO_ROOT / "backend" / "data"

DATASETS_DIR = EVAL_ROOT / "datasets"
GROUND_TRUTH_DIR = EVAL_ROOT / "ground_truth"
EVIDENCE_DIR = EVAL_ROOT / "evidence"
RESULTS_DIR = EVAL_ROOT / "results"
REPORTS_DIR = EVAL_ROOT / "reports"

SOURCE_INVENTORY_PATH = DATASETS_DIR / "source_inventory.json"
SCHEMES_PATH = GROUND_TRUTH_DIR / "schemes.json"
EXCERPTS_PATH = EVIDENCE_DIR / "excerpts.json"
BENCHMARK_PATH = DATASETS_DIR / "benchmark_v1.json"
VALIDATION_REPORT_PATH = DATASETS_DIR / "validation_report.json"
RESULTS_PATH = RESULTS_DIR / "benchmark_results.json"
CHECKPOINT_PATH = RESULTS_DIR / "benchmark_checkpoint.json"
RUN_REPORT_PATH = REPORTS_DIR / "benchmark_report.md"
RE_EVALUATED_RESULTS_PATH = RESULTS_DIR / "benchmark_v1_re_evaluated.json"
RE_EVALUATED_REPORT_PATH = REPORTS_DIR / "benchmark_v1_re_evaluated.md"
BENCHMARK_V2_RESULTS_PATH = RESULTS_DIR / "benchmark_v2.json"
BENCHMARK_V2_CHECKPOINT_PATH = RESULTS_DIR / "benchmark_v2_checkpoint.json"
BENCHMARK_V2_REPORT_PATH = REPORTS_DIR / "benchmark_v2.md"
BUILD_REPORT_PATH = REPORTS_DIR / "benchmark_build_report.md"

SEED_DOCUMENTS = [
    {
        "id": "seed-pmfby",
        "scheme_id": "pmfby",
        "scheme_name": "Pradhan Mantri Fasal Bima Yojana",
        "path": "backend/data/demo_seeds/pmfby_scheme.txt",
        "authority": "seed_document",
    },
    {
        "id": "seed-shakti",
        "scheme_id": "shakti",
        "scheme_name": "Shakti Scheme (Free Bus Travel)",
        "path": "backend/data/demo_seeds/shakti_scheme.txt",
        "authority": "seed_document",
    },
    {
        "id": "seed-anna-bhagya",
        "scheme_id": "anna-bhagya",
        "scheme_name": "Anna Bhagya",
        "path": "backend/data/seed_schemes/anna_bhagya_overview.txt",
        "authority": "seed_document",
    },
    {
        "id": "seed-pmsby",
        "scheme_id": "pmsby",
        "scheme_name": "Pradhan Mantri Suraksha Bima Yojana",
        "path": "backend/data/seed_schemes/pmsby_overview.txt",
        "authority": "seed_document",
    },
    {
        "id": "seed-gruha-lakshmi",
        "scheme_id": "gruha-lakshmi",
        "scheme_name": "Gruha Lakshmi",
        "path": "backend/data/seed_schemes/gruha_lakshmi_overview.txt",
        "authority": "seed_document",
    },
]

CATALOG_PATH = "backend/data/scheme_catalog.json"
REGISTRY_PATH = "backend/data/trusted_gov_registry.json"

CATEGORIES = ("factual", "eligibility", "unsupported", "multilingual", "difficult")
DIFFICULTIES = ("easy", "medium", "hard", "adversarial")
LANGUAGES = ("en", "hi", "kn")
EXPECTED_BEHAVIORS = (
    "answer_from_evidence",
    "eligible",
    "ineligible",
    "unsupported",
    "insufficient_evidence",
    "check_official_notification",
)

TARGET_QUOTAS = {
    "factual": 40,
    "eligibility": 25,
    "unsupported": 15,
    "multilingual": 10,
    "difficult": 10,
}
