"""Frozen real-JD corpus integrity and the recorded ESCO decision."""

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "benchmarks" / "real-jd" / "corpus.jsonl"
REPORT = ROOT / "benchmarks" / "real-jd" / "coverage-report.json"


class RealJDCorpusTests(unittest.TestCase):
    def test_corpus_exists_and_is_frozen(self):
        self.assertTrue(CORPUS.exists(), "run scripts/build_jd_corpus.py first")
        payload = json.loads(CORPUS.read_text(encoding="utf-8"))
        self.assertGreaterEqual(payload["entry_count"], 10)
        for entry in payload["entries"]:
            digest = entry["provenance"]["sha256"]
            computed = hashlib.sha256(entry["description"].encode("utf-8")).hexdigest()
            self.assertEqual(digest, computed, f"{entry['corpus_id']} drifted")
            self.assertRegex(entry["role"], r"(?i)intern")

    def test_coverage_report_records_esco_decision(self):
        self.assertTrue(REPORT.exists(), "run scripts/measure_alias_coverage.py")
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertIn(report["esco_decision"],
                      {"keep_hand_alias_table", "adopt_esco_enrichment"})
        if report["esco_decision"] == "keep_hand_alias_table":
            self.assertLessEqual(report["aggregate_gap"], report["esco_threshold"])


if __name__ == "__main__":
    unittest.main()
