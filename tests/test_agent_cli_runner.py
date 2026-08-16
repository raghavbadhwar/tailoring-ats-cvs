from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents/skills/tailor-cv/scripts/run_cli.py"


def load_module():
    spec = importlib.util.spec_from_file_location("run_cli", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AgentCliRunnerTests(unittest.TestCase):
    def test_runner_preserves_arguments_without_shell(self) -> None:
        module = load_module()
        with patch.object(module, "resolve_cli", return_value="/tmp/fake-ats-agent"), patch.object(module.subprocess, "run") as run:
            run.return_value.returncode = 0
            self.assertEqual(module.run_agent_cli(["prepare", "resume with spaces.docx"], module.DEFAULT_POLICY), 0)
        self.assertEqual(run.call_args.args[0], ["/tmp/fake-ats-agent", "prepare", "resume with spaces.docx"])
        self.assertFalse(run.call_args.kwargs.get("shell", False))

    def test_runner_blocks_unready_cli(self) -> None:
        module = load_module()
        with patch.object(module, "check_cli", return_value={"status": "bootstrap_required"}):
            with self.assertRaisesRegex(RuntimeError, "bootstrap_required"):
                module.resolve_cli(module.DEFAULT_POLICY)
