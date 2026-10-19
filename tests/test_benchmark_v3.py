from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from ats_agent.benchmark import (
    BenchmarkGateError,
    SUITE_FILENAMES,
    load_cases,
    run_suite,
    run_cases,
    validate_cases,
    wilson_interval,
)
from ats_agent.cli import _error_exit_code, main as cli_main
from ats_agent._benchmark_validate import _code_revision
from ats_agent._benchmark_runner import _packaged_smoke_path


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
        self.assertEqual(result["source_dataset_sha256"], result["dataset_sha256"])
        self.assertRegex(result["expanded_dataset_sha256"], r"^[0-9a-f]{64}$")
        self.assertIn("code_sha", result)
        self.assertEqual(result["code_revision"]["commit"], result["code_sha"])
        self.assertIn(result["code_revision"]["tree_state"], {"clean", "dirty", "unknown"})
        if result["code_revision"]["tree_state"] != "unknown":
            self.assertRegex(
                result["code_revision"]["working_tree_sha256"],
                r"^[0-9a-f]{64}$",
            )
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

    def test_all_automated_release_suites_execute_with_passing_cases(self) -> None:
        """Exercise every shipped non-human suite in the in-process release path.

        The benchmark gate is part of the safety contract, so this protects the
        adversarial and document dispatch paths rather than leaving them to a
        separate script invocation that coverage cannot observe.
        """

        reports = {
            suite: run_suite(suite, root=ROOT)
            for suite in ("public", "adversarial", "documents")
        }

        self.assertTrue(all(report["case_count"] > 0 for report in reports.values()))
        self.assertEqual(
            reports["adversarial"]["metrics"]["adversarial_scenario_pass_rate"][
                "value"
            ],
            1.0,
        )
        self.assertEqual(
            reports["documents"]["metrics"]["document_case_pass_rate"]["value"],
            1.0,
        )
        self.assertEqual(
            reports["documents"]["metrics"]["output_reparse_rate"]["value"],
            1.0,
        )
        self.assertTrue(
            all(case["passed"] for case in reports["adversarial"]["cases"])
        )
        self.assertTrue(
            all(case["passed"] for case in reports["documents"]["cases"])
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

    def test_packaged_smoke_fixture_is_available_while_consumed(self) -> None:
        with _packaged_smoke_path() as dataset:
            self.assertTrue(dataset.is_file())
            self.assertEqual(len(load_cases(dataset)), 8)

    def test_expanded_dataset_hash_binds_canonical_expanded_cases(self) -> None:
        dataset = ROOT / SUITE_FILENAMES["smoke"]
        cases = load_cases(dataset)
        original = run_cases(
            cases,
            suite="smoke",
            dataset_path=dataset,
            root=ROOT,
        )
        changed = json.loads(json.dumps(cases))
        changed[0]["provenance_probe"] = "changed"
        modified = run_cases(
            changed,
            suite="smoke",
            dataset_path=dataset,
            root=ROOT,
        )

        self.assertEqual(
            original["source_dataset_sha256"],
            modified["source_dataset_sha256"],
        )
        self.assertNotEqual(
            original["expanded_dataset_sha256"],
            modified["expanded_dataset_sha256"],
        )

    @unittest.skipIf(os.name == "nt", "executable mode is not portable on Windows")
    def test_working_tree_digest_binds_executable_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "tool.sh"
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            script.chmod(0o644)
            subprocess.run(["git", "add", "tool.sh"], cwd=root, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Benchmark Test",
                    "-c",
                    "user.email=benchmark@example.invalid",
                    "commit",
                    "-qm",
                    "fixture",
                ],
                cwd=root,
                check=True,
            )
            before = _code_revision(root)
            script.chmod(0o755)
            after = _code_revision(root)
            script.unlink()
            deleted = _code_revision(root)

            self.assertEqual(before["tree_state"], "clean")
            self.assertEqual(after["tree_state"], "dirty")
            self.assertNotEqual(
                before["working_tree_sha256"],
                after["working_tree_sha256"],
            )
            self.assertEqual(deleted["tree_state"], "dirty")
            self.assertNotEqual(
                after["working_tree_sha256"],
                deleted["working_tree_sha256"],
            )

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
