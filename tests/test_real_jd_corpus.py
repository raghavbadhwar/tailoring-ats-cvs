"""Frozen real-JD corpus integrity and the recorded ESCO decision."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import measure_alias_coverage

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
        self.assertEqual(report["schema_version"], 3)
        self.assertEqual(report["label_source"], "rule-derived")
        self.assertEqual(
            report["measurement_status"],
            "heuristic_diagnostic_not_human_validated",
        )
        self.assertIn("not human-labelled", report["interpretation"])
        self.assertGreater(report["total_expected_lines"], 0)
        self.assertEqual(report["measured_entries"], report["corpus_entries"])
        self.assertTrue(
            all(item["expected_requirement_lines"] > 0 for item in report["per_jd"])
        )
        self.assertEqual(
            report["total_expected_lines"],
            sum(item["expected_requirement_lines"] for item in report["per_jd"]),
        )
        self.assertEqual(
            report["total_missed_lines"],
            sum(item["missed_expected_lines"] for item in report["per_jd"]),
        )
        self.assertEqual(
            report["aggregate_gap"],
            round(report["total_missed_lines"] / report["total_expected_lines"], 4),
        )
        self.assertIn(report["esco_decision"],
                      {"keep_hand_alias_table", "adopt_esco_enrichment"})
        expected_decision = (
            "adopt_esco_enrichment"
            if report["aggregate_gap"] > report["esco_threshold"]
            else "keep_hand_alias_table"
        )
        self.assertEqual(report["esco_decision"], expected_decision)

    def test_committed_report_matches_fresh_measurement(self):
        committed = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(committed, measure_alias_coverage.measure())

    def test_measurement_rejects_zero_denominator(self):
        payload = {
            "entries": [
                {
                    "corpus_id": "empty-01",
                    "role": "Intern",
                    "description": "<h2>About us</h2><p>Welcome to Acme.</p>",
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp) / "corpus.json"
            corpus.write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(measure_alias_coverage, "CORPUS_PATH", corpus):
                with self.assertRaisesRegex(ValueError, "zero expected"):
                    measure_alias_coverage.measure()

    def test_paragraph_requirement_heading_is_measured(self):
        description = (
            "<p>ABOUT THE ROLE</p><p>Build useful products.</p>"
            "<p>WHAT WE'RE LOOKING FOR</p>"
            "<p>Experience building production Python services.</p>"
            "<p><strong>Benefits</strong></p>"
            "<p>Health insurance and generous paid leave.</p>"
        )

        text = measure_alias_coverage._measurement_text(description)

        self.assertEqual(
            measure_alias_coverage._expected_lines(text),
            ["Experience building production Python services."],
        )

    def test_small_html_heading_keeps_requirement_boundary(self):
        for tag in ("h5", "h6"):
            with self.subTest(tag=tag):
                text = measure_alias_coverage._measurement_text(
                    f"<{tag}>Requirements</{tag}>"
                    "<p>Python experience is required.</p>"
                )
                self.assertEqual(
                    measure_alias_coverage._expected_lines(text),
                    ["Python experience is required."],
                )


if __name__ == "__main__":
    unittest.main()
