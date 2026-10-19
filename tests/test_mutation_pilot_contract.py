from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.summarize_mutation_session import summarize

ROOT = Path(__file__).resolve().parents[1]


class MutationPilotContractTests(unittest.TestCase):
    def test_config_and_runner_are_bounded_and_disposable(self) -> None:
        config = (ROOT / "cosmic-ray.toml").read_text(encoding="utf-8")
        runner = (ROOT / "scripts" / "run_mutation_pilot.sh").read_text(
            encoding="utf-8"
        )
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        for module in ("workflow.py", "evidence.py", "documents.py", "validation.py"):
            self.assertIn(module, config)
        self.assertIn("timeout = 120.0", config)
        self.assertIn("git -C \"$root\" worktree add --detach", runner)
        self.assertIn("worktree remove --force", runner)
        self.assertIn("export PYTHONPATH=\"$worktree/src\"", runner)
        self.assertIn("elapsed\" -gt 600", runner)
        self.assertIn("timeout-minutes: 15", workflow)
        self.assertIn("continue-on-error: true", workflow)
        self.assertIn("bash scripts/run_mutation_pilot.sh", workflow)
        self.assertIn("actions/upload-artifact@v6", workflow)

    def test_summary_requires_results_and_reports_killed_mutations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dump = root / "session.jsonl"
            work = {
                "mutations": [
                    {
                        "module_path": "src/ats_agent/workflow.py",
                        "definition_name": "_validate_research_freshness",
                        "operator_name": "core/ReplaceComparisonOperator_Gt_GtE",
                        "occurrence": 0,
                    }
                ]
            }
            dump.write_text(
                json.dumps(
                    [
                        work,
                        {
                            "worker_outcome": "normal",
                            "test_outcome": "killed",
                        },
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            result = summarize(dump)
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["outcomes"], {"killed": 1})
            dump.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "no results"):
                summarize(dump)


if __name__ == "__main__":
    unittest.main()
