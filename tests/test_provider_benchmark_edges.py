from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ats_agent._benchmark_runner import _resolve_suite_path
from ats_agent.benchmark import (
    BenchmarkGateError,
    SUITE_FILENAMES,
    load_cases,
    run,
    run_cases,
    run_suite,
    validate_cases,
    wilson_interval,
)
from ats_agent.providers import (
    CommandRewriteProvider,
    DeterministicRewriteProvider,
    RewriteContext,
    generate_with_fallback,
)

ROOT = Path(__file__).resolve().parents[1]


class ProviderEdgeContractTests(unittest.TestCase):
    def test_rewrite_context_rejects_missing_text_and_tiny_budget(self) -> None:
        with self.assertRaisesRegex(ValueError, "original_text"):
            RewriteContext(original_text="   ")
        with self.assertRaisesRegex(ValueError, "at least 20"):
            RewriteContext(original_text="Supported Python checks.", max_characters=19)

    def test_deterministic_provider_covers_cleanup_compaction_and_deduplication(self) -> None:
        provider = DeterministicRewriteProvider()
        cleaned = provider.generate(
            RewriteContext(
                original_text=(
                    "Results-driven Leveraged AI for support, with various controls."
                ),
                max_characters=180,
            )
        )
        self.assertTrue(cleaned)
        self.assertTrue(all("Results-driven" not in item["text"] for item in cleaned))
        self.assertTrue(any("used AI" in item["text"] for item in cleaned))

        semicolon = provider.generate(
            RewriteContext(
                original_text="Supported analytics; with traceable controls.",
                max_characters=120,
            )
        )
        self.assertTrue(any(item["text"].endswith("analytics.") for item in semicolon))

        duplicate_safe = provider.generate(
            RewriteContext(original_text="Built systems.", max_characters=80)
        )
        self.assertEqual(duplicate_safe, [{"id": "conservative", "text": "Built systems."}])

        over_budget = provider.generate(
            RewriteContext(
                original_text="Helped build an intentionally long workflow description.",
                max_characters=20,
            )
        )
        self.assertEqual(over_budget, [])

    def test_command_provider_validates_configuration(self) -> None:
        with self.assertRaisesRegex(ValueError, "command"):
            CommandRewriteProvider(())
        with self.assertRaisesRegex(ValueError, "positive"):
            CommandRewriteProvider((sys.executable,), timeout_seconds=0)

    @staticmethod
    def _completed(payload: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=(sys.executable,),
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )

    def test_command_provider_accepts_valid_json_variants(self) -> None:
        provider = CommandRewriteProvider((sys.executable, "provider.py"))
        payload = [
            {"id": "conservative", "text": "Supported Python checks."},
            {"id": "balanced", "text": "Supported Python validation."},
            {"id": "compact", "text": "Python validation support."},
        ]
        with patch(
            "ats_agent.providers.subprocess.run",
            return_value=self._completed(payload),
        ) as mocked:
            variants = provider.generate(
                RewriteContext(
                    original_text="Supported Python checks.",
                    max_characters=100,
                )
            )
        self.assertEqual(variants, payload)
        self.assertTrue(mocked.call_args.kwargs["check"])
        self.assertTrue(mocked.call_args.kwargs["text"])
        submitted = json.loads(mocked.call_args.kwargs["input"])
        self.assertEqual(submitted["original_text"], "Supported Python checks.")

    def test_command_provider_rejects_malformed_results(self) -> None:
        context = RewriteContext(
            original_text="Supported Python checks.",
            max_characters=40,
        )
        cases = (
            ({"not": "a list"}, "JSON list"),
            (["not-an-object"], "objects"),
            ([{"id": "unsafe", "text": "Supported checks."}], "unsupported variant"),
            ([{"id": "balanced", "text": ""}], "invalid variant text"),
            ([{"id": "balanced", "text": "x" * 41}], "invalid variant text"),
        )
        for payload, message in cases:
            with self.subTest(payload=payload):
                provider = CommandRewriteProvider((sys.executable, "provider.py"))
                with patch(
                    "ats_agent.providers.subprocess.run",
                    return_value=self._completed(payload),
                ):
                    with self.assertRaisesRegex(ValueError, message):
                        provider.generate(context)

    def test_generate_with_fallback_is_fail_safe(self) -> None:
        class EmptyProvider:
            provider_id = "empty"
            provider_version = "0.0.1"

            def generate(self, context: RewriteContext) -> list[dict]:
                del context
                return []

        variants, provider_id, provider_version, reason = generate_with_fallback(
            EmptyProvider(),
            RewriteContext(
                original_text="Helped build automated workflows.",
                terms=("workflow automation",),
                max_characters=120,
            ),
        )
        self.assertTrue(variants)
        self.assertEqual(provider_id, "deterministic")
        self.assertEqual(provider_version, "1.0.0")
        self.assertIn("ValueError", str(reason))


class BenchmarkEdgeContractTests(unittest.TestCase):
    @staticmethod
    def _human_case(case_id: str, *, ratings: object = None) -> dict:
        return {
            "id": case_id,
            "suite": "human",
            "role_family": "software-data",
            "semantic_template": f"human-{case_id}",
            "resume": "PROJECTS\n- Supported Python validation.\n",
            "job_description": "Python is required.",
            "outputs": {
                "original": "PROJECTS\n- Supported Python validation.\n",
                "legacy_v0_9": None,
                "v1_deterministic_balanced": None,
                "optional_provider_balanced": None,
            },
            "ratings": ratings,
            "label_source": "curated-static",
        }

    def test_load_cases_expands_human_specs_and_preserves_raw_cases(self) -> None:
        human = load_cases(ROOT / SUITE_FILENAMES["human"])
        self.assertGreaterEqual(len(human), 50)
        self.assertEqual(human[0]["suite"], "human")
        self.assertEqual(human[0]["measurement_status"], "awaiting_blinded_human_review")
        self.assertIn("original", human[0]["outputs"])

        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory) / "raw.jsonl"
            dataset.write_text(
                json.dumps({"id": "raw", "value": 7}) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(load_cases(dataset), [{"id": "raw", "value": 7}])

    def test_load_cases_rejects_empty_missing_and_duplicate_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixtures = (
                ("empty.jsonl", "\n", "empty"),
                ("missing.jsonl", json.dumps({"suite": "human"}) + "\n", "without id"),
                (
                    "duplicates.jsonl",
                    json.dumps({"id": "same"})
                    + "\n"
                    + json.dumps({"id": "same"})
                    + "\n",
                    "duplicate",
                ),
            )
            for name, content, message in fixtures:
                with self.subTest(name=name):
                    path = root / name
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, message):
                        load_cases(path)

    def test_human_suite_and_custom_rated_dataset_report_measurement_state(self) -> None:
        unrated = run_suite("human", root=ROOT)
        self.assertEqual(
            unrated["metrics"]["human_evaluation_completion"]["value"],
            0.0,
        )
        self.assertEqual(
            unrated["measurement_status"]["human_preference"],
            "not_measured",
        )
        self.assertTrue(
            all(case["status"] == "awaiting_review" for case in unrated["cases"])
        )

        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory) / "rated.jsonl"
            case = self._human_case(
                "rated-one",
                ratings={"preference": "v1_deterministic_balanced"},
            )
            dataset.write_text(json.dumps(case) + "\n", encoding="utf-8")
            rated = run(dataset)
        self.assertEqual(
            rated["metrics"]["human_evaluation_completion"]["value"],
            1.0,
        )
        self.assertEqual(rated["cases"][0]["status"], "rated")
        self.assertEqual(
            rated["measurement_status"]["human_preference"],
            "measured",
        )
        self.assertEqual(
            rated["baselines"]["human_preference"]["status"],
            "partially_measured",
        )

    def test_suite_resolution_and_diversity_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown benchmark suite"):
            _resolve_suite_path("unknown", ROOT)
        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory) / "duplicates.jsonl"
            first = self._human_case("one")
            second = self._human_case("two")
            second["semantic_template"] = "human-two"
            dataset.write_text(
                json.dumps(first) + "\n" + json.dumps(second) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(BenchmarkGateError, "diversity"):
                run_cases(
                    [first, second],
                    suite="human",
                    dataset_path=dataset,
                    root=ROOT,
                )

    def test_validation_reports_missing_labels_spans_and_overrepresentation(self) -> None:
        cases = []
        for index in range(4):
            cases.append(
                {
                    "id": f"case-{index}",
                    "suite": "public",
                    "role_family": "software-data",
                    "semantic_template": "repeated-template",
                    "resume": f"Resume {index}",
                    "job_description": f"Job {index}",
                    "expected_requirements": [
                        {
                            "kind": "skill",
                            "term": "python",
                            "importance": "mandatory",
                        }
                    ],
                    "expected_matches": [],
                    "expected_hard_gates": [],
                    "forbidden_rewrite_terms": [],
                    "expected_section": "projects",
                    "expected_safety": "pass",
                    "label_source": (
                        "engine-generated" if index == 0 else "curated-static"
                    ),
                }
            )
        diagnostics = validate_cases(cases, suite="public")
        self.assertEqual(
            diagnostics["overrepresented_templates"],
            {"repeated-template": 4},
        )
        self.assertEqual(
            diagnostics["overrepresented_role_families"],
            {"software-data": 4},
        )
        self.assertTrue(diagnostics["missing_required_fields"])
        flattened = {
            missing
            for item in diagnostics["missing_required_fields"]
            for missing in item["missing"]
        }
        self.assertIn("expected_requirements[].source_span", flattened)
        self.assertIn("label_source must not be engine-generated", flattened)

    def test_zero_sample_wilson_interval_is_bounded(self) -> None:
        self.assertEqual(wilson_interval(0, 0), (0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
