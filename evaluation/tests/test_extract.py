import unittest

from evaluation.extract import extract_facts_from_document
from evaluation.inventory import inventory_sources


class TestExtractAndInventory(unittest.TestCase):
    def test_inventory_finds_seed_documents(self):
        inventory = inventory_sources()
        present = [d["scheme_id"] for d in inventory["authoritative_seed_documents"] if d.get("present")]
        self.assertEqual(set(present), {"pmfby", "shakti", "anna-bhagya", "pmsby", "gruha-lakshmi"})

    def test_pmsby_premium_extracted(self):
        facts, record = extract_facts_from_document(
            "pmsby",
            "seed-pmsby",
            "backend/data/seed_schemes/pmsby_overview.txt",
        )
        blob = " ".join(f["excerpt"] for f in facts)
        self.assertIn("Rs 20", blob)
        self.assertIn("2 lakh", blob)
        self.assertTrue(record["eligibility_rules"])
