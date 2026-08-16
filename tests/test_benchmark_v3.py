from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ats_agent.benchmark import (
    BenchmarkGateError,
    SUITE_FILENAMES,
    load_cases,
    run_suite,
    validate_cases,
    wilson_interval,
)
from ats_agent.cli import _error_exit_code, main as cli_main


ROOT = Path(__file__).resolve().parents[1]


class BenchmarkV3Tests(unittest.TestCase):
    def test_suite_registry_exposes_frozen_release_suites(self) -> None:
        self.assertEqual(
            set(SUITE_FILENAMES),
            {"smoke", "public", "adversarial", "documents", "human"},
        )
        for suite in ("public", "adversarial", "documents", "human"):
            self.assertTrue((ROOT / SUITE_FILENAMES[suite]).is_file(), suite)

    def test_public_suite_is_balanced_static_and_semantically_distinct(self) -> None:
        cases = load_cases(ROOT / SUITE_FILENAMES["public"])
        self.assertEqual(len(cases), 180)
        families: dict[str, int] = {}
        for case in cases:
            families[case["role_family"]] = families.get(case["role_family"], 0) + 1
        self.assertEqual(
            families,
            {
                "ai-automation": 36,
                "finance-analytics": 36,
                "consulting-operations": 36,
                "product-program": 36,
                "software-data": 36,
            },
        )
        diagnostics = validate_cases(cases, suite="public")
        self.assertEqual(diagnostics["duplicate_pairs"], [])
        self.assertEqual(diagnostics["numeric_only_duplicates"], [])
        self.assertEqual(diagnostics["overrepresented_templates"], {})
        self.assertEqual(diagnostics["overrepresented_role_families"], {})
        self.assertEqual(diagnostics["missing_required_fields"], [])

    def test_adversarial_and_document_suites_have_release_scale(self) -> None:
        adversarial = load_cases(ROOT / SUITE_FILENAMES["adversarial"])
        documents = load_cases(ROOT / SUITE_FILENAMES["documents"])
        self.assertGreaterEqual(len(adversarial), 60)
        self.assertGreaterEqual(len(documents), 30)
        self.assertGreaterEqual(len({case["scenario"] for case in adversarial}), 18)
        self.assertTrue(
            {"docx", "pdf", "rtf", "html"}
            <= {case["format"] for case in documents}
        )

    def test_report_contains_denominators_intervals_hashes_and_baselines(self) -> None:
        result = run_suite("smoke", root=ROOT)
        self.assertEqual(result["schema_version"], 3)
        self.assertGreater(result["case_count"], 0)
        self.assertRegex(result["dataset_sha256"], r"^[0-9a-f]{64}$")
        self.assertIn("code_sha", result)
        self.assertIn("environment", result)
        self.assertIn("generated_at", result)
        self.assertIn("metrics", result)
        self.assertIn("baselines", result)
        for metric in result["metrics"].values():
            if metric["status"] == "measured":
                self.assertIn("numerator", metric)
                self.assertIn("denominator", metric)
                self.assertIn("value", metric)
                self.assertIn("confidence_interval_95", metric)
        self.assertEqual(
            result["measurement_status"]["human_preference"],
            "not_measured",
        )
        self.assertEqual(
            result["measurement_status"]["parser_risk_delta"],
            "not_measured",
        )

    def test_wilson_interval_is_bounded_and_contains_observed_rate(self) -> None:
        low, high = wilson_interval(90, 100)
        self.assertGreaterEqual(low, 0.0)
        self.assertLessEqual(high, 1.0)
        self.assertLessEqual(low, 0.9)
        self.assertGreaterEqual(high, 0.9)

    def test_numeric_only_duplicates_are_rejected(self) -> None:
        cases = [
            {
                "id": "a",
                "suite": "public",
                "role_family": "software-data",
                "semantic_template": "one",
                "resume": "Built 10 Python tests.",
                "job_description": "Python is required for 10 workflows.",
                "expected_requirements": [],
                "expected_matches": [],
                "expected_hard_gates": [],
                "forbidden_rewrite_terms": [],
                "expected_section": "projects",
                "expected_safety": "pass",
            },
            {
                "id": "b",
                "suite": "public",
                "role_family": "software-data",
                "semantic_template": "two",
                "resume": "Built 20 Python tests.",
                "job_description": "Python is required for 20 workflows.",
                "expected_requirements": [],
                "expected_matches": [],
                "expected_hard_gates": [],
                "forbidden_rewrite_terms": [],
                "expected_section": "projects",
                "expected_safety": "pass",
            },
        ]
        diagnostics = validate_cases(cases, suite="public")
        self.assertEqual(diagnostics["numeric_only_duplicates"], [["a", "b"]])

    def test_report_can_be_written_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.json"
            result = run_suite("smoke", root=ROOT, report_path=report)
            self.assertEqual(json.loads(report.read_text(encoding="utf-8")), result)

    def test_cli_runs_named_suite_and_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "smoke.json"
            code = cli_main(
                ["benchmark", "--suite", "smoke", "--report", str(report)]
            )
            self.assertEqual(code, 0)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["suite"], "smoke")

    def test_benchmark_gate_failures_use_exit_code_seven(self) -> None:
        self.assertEqual(
            _error_exit_code(BenchmarkGateError("benchmark gate failed")),
            7,
        )


if __name__ == "__main__":
    unittest.main()
