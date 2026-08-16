from __future__ import annotations

import argparse
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ats_agent.benchmark import BenchmarkGateError
from ats_agent.cli import (
    _error_exit_code,
    _existing,
    _run_benchmark,
    _selection,
    main as cli_main,
)
from ats_agent.providers import (
    CommandRewriteProvider,
    DeterministicRewriteProvider,
    RewriteContext,
    _balanced_structure,
    _compact,
    _safe_ownership_language,
    _surface_term,
    generate_with_fallback,
)
from ats_agent.workflow import (
    _default_output,
    _ledger_from_proposal,
    _materialize_change,
    _resolve_from,
    _selections,
    _temporary_output,
    _validate_output_path,
)


class ProviderContractCoverageTests(unittest.TestCase):
    def context(self, text: str = "Helped build automated workflows, with 42 tests.") -> RewriteContext:
        return RewriteContext(
            original_text=text,
            terms=("workflow automation",),
            max_characters=180,
        )

    def test_rewrite_context_rejects_blank_and_tiny_budgets(self) -> None:
        with self.assertRaisesRegex(ValueError, "original_text"):
            RewriteContext(original_text="   ")
        with self.assertRaisesRegex(ValueError, "max_characters"):
            RewriteContext(original_text="Evidence", max_characters=19)

    def test_safe_ownership_rules_and_unchanged_text(self) -> None:
        cases = {
            "Helped build a workflow": "Contributed to building a workflow",
            "Helped validate a workflow": "Contributed to validate a workflow",
            "Worked on a workflow": "Contributed to a workflow",
            "Supported a workflow": "Contributed to a workflow",
            "Contributed to building a workflow": "Helped build a workflow",
            "Contributed to a workflow": "Supported a workflow",
            "Assisted with a workflow": "Supported a workflow",
            "Assisted validation": "Supported validation",
            "Participated in validation": "Contributed to validation",
            "Collaborated on validation": "Contributed to validation",
            "Responsible for validation": "Contributed to validation",
            "Built a workflow": "Built a workflow",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(_safe_ownership_language(source), expected)

    def test_term_surface_rules_cover_each_supported_alias(self) -> None:
        cases = (
            (
                "Contributed to building automated order workflows.",
                "workflow automation",
                "workflow automation for orders",
            ),
            (
                "Contributed to building automated procurement workflows.",
                "workflow automation",
                "workflow automation for procurement",
            ),
            (
                "Contributed to automated workflows.",
                "workflow automation",
                "workflow automation",
            ),
            (
                "Contributed to workflow systems.",
                "workflow automation",
                "workflow automation systems",
            ),
            ("Used an approval-first process.", "human-in-the-loop", "human-in-the-loop"),
            ("Used approval-gated review.", "human-in-the-loop", "human-in-the-loop"),
            ("Required human approval.", "human-in-the-loop", "human-in-the-loop approval"),
            ("Drafted a PRD.", "product requirements", "product requirements document"),
            ("Built a RAG pipeline.", "retrieval-augmented generation", "retrieval-augmented"),
            ("Published on GitHub.", "git", "Git/GitHub"),
        )
        for source, term, expected in cases:
            with self.subTest(source=source, term=term):
                self.assertIn(expected, _surface_term(source, term))
        self.assertEqual(_surface_term("Python analysis.", "python"), "Python analysis.")
        self.assertEqual(_surface_term("Python analysis.", "unknown"), "Python analysis.")

    def test_balanced_and_compact_structure_paths(self) -> None:
        self.assertEqual(
            _balanced_structure("Built checks for procurement."),
            "Built checks to support procurement.",
        )
        self.assertEqual(
            _balanced_structure("Built checks, with 42 tests."),
            "Built checks; with 42 tests.",
        )
        self.assertEqual(_balanced_structure("Built checks."), "Built checks.")
        self.assertEqual(
            _compact("Contributed to building workflow automation for orders, with 42 tests."),
            "Contributed to order-workflow automation.",
        )
        self.assertEqual(
            _compact("Contributed to workflow automation for procurement; with 42 tests."),
            "Contributed to procurement-workflow automation.",
        )

    def test_deterministic_provider_drops_invalid_and_duplicate_variants(self) -> None:
        provider = DeterministicRewriteProvider()
        variants = provider.generate(
            RewriteContext(
                original_text="Built Python checks.",
                terms=("python",),
                max_characters=180,
            )
        )
        self.assertEqual(variants, [{"id": "conservative", "text": "Built Python checks."}])
        self.assertEqual(
            provider.generate(
                RewriteContext(
                    original_text="Results-driven Helped build automated workflows, with 42 tests.",
                    terms=("workflow automation",),
                    max_characters=20,
                )
            ),
            [],
        )

    def test_command_provider_validates_configuration_and_json_contract(self) -> None:
        with self.assertRaisesRegex(ValueError, "command is required"):
            CommandRewriteProvider(())
        with self.assertRaisesRegex(ValueError, "timeout_seconds"):
            CommandRewriteProvider(("provider",), timeout_seconds=0)

        provider = CommandRewriteProvider(("provider", "--json"), timeout_seconds=3)
        completed = SimpleNamespace(
            stdout=json.dumps(
                [
                    {"id": "conservative", "text": "Supported Python checks."},
                    {"id": "balanced", "text": "Supported Python validation."},
                ]
            )
        )
        with patch("ats_agent.providers.subprocess.run", return_value=completed) as mocked:
            variants = provider.generate(self.context("Supported Python checks."))
        self.assertEqual(len(variants), 2)
        kwargs = mocked.call_args.kwargs
        self.assertEqual(kwargs["timeout"], 3)
        self.assertFalse(kwargs.get("shell", False))
        self.assertIn("original_text", json.loads(kwargs["input"]))

    def test_command_provider_rejects_invalid_payload_shapes(self) -> None:
        provider = CommandRewriteProvider(("provider",))
        invalid_payloads = (
            ({"id": "conservative"}, "JSON list"),
            (["not-an-object"], "objects"),
            ([{"id": "unsafe", "text": "Text"}], "unsupported variant"),
            ([{"id": "balanced", "text": ""}], "invalid variant text"),
        )
        for payload, message in invalid_payloads:
            with self.subTest(payload=payload):
                completed = SimpleNamespace(stdout=json.dumps(payload))
                with patch("ats_agent.providers.subprocess.run", return_value=completed):
                    with self.assertRaisesRegex(ValueError, message):
                        provider.generate(self.context())

        completed = SimpleNamespace(
            stdout=json.dumps(
                [{"id": "balanced", "text": "x" * 181}]
            )
        )
        with patch("ats_agent.providers.subprocess.run", return_value=completed):
            with self.assertRaisesRegex(ValueError, "invalid variant text"):
                provider.generate(self.context())

    def test_generate_with_fallback_covers_success_empty_and_subprocess_failure(self) -> None:
        context = self.context()
        deterministic = DeterministicRewriteProvider()
        variants, provider_id, version, reason = generate_with_fallback(
            deterministic,
            context,
        )
        self.assertTrue(variants)
        self.assertEqual(provider_id, "deterministic")
        self.assertEqual(version, deterministic.provider_version)
        self.assertIsNone(reason)

        class EmptyProvider:
            provider_id = "empty"
            provider_version = "1"

            def generate(self, context: RewriteContext) -> list[dict]:
                del context
                return []

        variants, provider_id, _version, reason = generate_with_fallback(
            EmptyProvider(),
            context,
        )
        self.assertTrue(variants)
        self.assertEqual(provider_id, "deterministic")
        self.assertIn("ValueError", str(reason))

        failing = CommandRewriteProvider(("provider",))
        with patch(
            "ats_agent.providers.subprocess.run",
            side_effect=subprocess.TimeoutExpired("provider", 20),
        ):
            variants, provider_id, _version, reason = generate_with_fallback(
                failing,
                context,
            )
        self.assertTrue(variants)
        self.assertEqual(provider_id, "deterministic")
        self.assertIn("TimeoutExpired", str(reason))


class CliAndWorkflowContractCoverageTests(unittest.TestCase):
    def test_cli_input_and_selection_parsers(self) -> None:
        with self.assertRaisesRegex(argparse.ArgumentTypeError, "file not found"):
            _existing("missing-file-for-contract-test.txt")
        with self.assertRaisesRegex(argparse.ArgumentTypeError, "selection"):
            _selection(":balanced")
        self.assertEqual(_selection("C1"), ("C1", None))
        self.assertEqual(_selection(" C1 : balanced "), ("C1", "balanced"))
        self.assertEqual(_selection("C1:"), ("C1", None))

    def test_cli_error_codes_cover_each_public_failure_category(self) -> None:
        cases = (
            (BenchmarkGateError("failed"), 7),
            (ValueError("stale proposal artifact"), 3),
            (ValueError("proposal digest mismatch"), 3),
            (ValueError("ownership escalation"), 4),
            (ValueError("metric binding failed"), 4),
            (ValueError("unknown approved change"), 4),
            (ValueError("unsupported output format"), 5),
            (ValueError("document anchor is ambiguous"), 5),
            (ValueError("ordinary invalid input"), 2),
        )
        for exc, expected in cases:
            with self.subTest(exc=exc):
                self.assertEqual(_error_exit_code(exc), expected)

    def test_custom_benchmark_dataset_writes_report_and_rejects_suite_mix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "cases.jsonl"
            report = root / "report.json"
            dataset.write_text(
                json.dumps(
                    {
                        "id": "coverage-case",
                        "resume": "Built Python workflows with 42 tests.",
                        "job_description": "Python is required.",
                        "expected_supported_terms": ["python"],
                        "expected_unsupported_terms": [],
                        "expected_hard_gates": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            result = _run_benchmark(str(dataset), "smoke", str(report))
            self.assertEqual(result["case_count"], 1)
            self.assertEqual(json.loads(report.read_text())["case_count"], 1)
            with self.assertRaisesRegex(BenchmarkGateError, "cannot be combined"):
                _run_benchmark(str(dataset), "public", None)

    def test_prepare_redacted_and_json_error_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume = root / "resume.txt"
            job = root / "job.txt"
            out = root / "run"
            resume.write_text(
                "PROJECTS\n- Helped build automated workflows with 42 tests.\n",
                encoding="utf-8",
            )
            job.write_text("Workflow automation is required.\n", encoding="utf-8")
            self.assertEqual(
                cli_main(
                    [
                        "prepare",
                        str(resume),
                        str(job),
                        "--out",
                        str(out),
                        "--redacted",
                    ]
                ),
                0,
            )
            self.assertTrue((out / "proposal.json").is_file())
            self.assertTrue((out / "review.html").is_file())

            invalid = root / "invalid.json"
            invalid.write_text("{invalid", encoding="utf-8")
            error = io.StringIO()
            with patch("sys.stderr", error):
                code = cli_main(
                    [
                        "review",
                        str(invalid),
                        "--markdown",
                        str(root / "invalid.md"),
                        "--html",
                        str(root / "invalid.html"),
                    ]
                )
            self.assertEqual(code, 2)
            self.assertIn("blocked", error.getvalue())

    def test_workflow_path_selection_and_materialization_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            absolute = (root / "absolute.txt").resolve()
            self.assertIsNone(_resolve_from(root, None))
            self.assertEqual(_resolve_from(root, "relative.txt"), root / "relative.txt")
            self.assertEqual(_resolve_from(root, str(absolute)), absolute)

            self.assertEqual(_default_output(root / "resume.pdf").suffix, ".docx")
            self.assertEqual(_default_output(root / "resume").suffix, ".txt")
            self.assertEqual(_default_output(root / "resume.md").suffix, ".md")
            temporary = _temporary_output(root / "tailored.docx")
            self.assertEqual(temporary.suffix, ".docx")
            self.assertIn(".tmp-", temporary.name)

            with self.assertRaisesRegex(ValueError, "no evidence ledger"):
                _ledger_from_proposal({})
            ledger = _ledger_from_proposal(
                {"candidate_id": "candidate-a", "evidence_ledger": []}
            )
            self.assertEqual(ledger.candidate_id, "candidate-a")

            changes = {"C1": {"id": "C1"}}
            self.assertEqual(
                _selections({}, ["C1"], changes),
                [{"change_id": "C1", "variant_id": None}],
            )
            self.assertEqual(
                _selections(
                    {"selections": [{"change_id": "C1", "variant_id": "balanced"}]},
                    [],
                    changes,
                ),
                [{"change_id": "C1", "variant_id": "balanced"}],
            )
            with self.assertRaisesRegex(ValueError, "selections must be a list"):
                _selections({"selections": "C1"}, [], changes)
            with self.assertRaisesRegex(ValueError, "requires change_id"):
                _selections({"selections": [{}]}, [], changes)

            change = {
                "id": "C1",
                "default_variant": "balanced",
                "variants": [
                    {"id": "conservative", "text": "One"},
                    {"id": "balanced", "text": "Two"},
                ],
            }
            self.assertEqual(
                _materialize_change(change, None)["replacement_text"],
                "Two",
            )
            self.assertEqual(
                _materialize_change(change, "conservative")["replacement_text"],
                "One",
            )
            with self.assertRaisesRegex(ValueError, "has no variant"):
                _materialize_change(change, "compact")
            self.assertEqual(
                _materialize_change({"id": "C2", "replacement_text": "Text"}, None),
                {"id": "C2", "replacement_text": "Text"},
            )

    def test_output_path_helper_rejects_each_unsafe_case(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "resume.txt"
            source.write_text("Resume", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must not overwrite"):
                _validate_output_path(source, source, force=False)
            with self.assertRaisesRegex(ValueError, "PDF output"):
                _validate_output_path(source, root / "out.pdf", force=False)
            with self.assertRaisesRegex(ValueError, "unsupported output format"):
                _validate_output_path(source, root / "out.rtf", force=False)

            existing = root / "out.txt"
            existing.write_text("Existing", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "already exists"):
                _validate_output_path(source, existing, force=False)
            _validate_output_path(source, existing, force=True)
            _validate_output_path(source, root / "fresh.md", force=False)


if __name__ == "__main__":
    unittest.main()
