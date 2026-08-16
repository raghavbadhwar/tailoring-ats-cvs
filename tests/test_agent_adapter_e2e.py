from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / ".agents/skills/tailor-cv/scripts/run_cli.py"
SUMMARIZER = RUNNER.with_name("summarize_proposal.py")
FAKE = ROOT / "tests/fixtures/fake_ats_agent.py"


class AgentAdapterE2ETests(unittest.TestCase):
    def test_prepare_and_summary_do_not_apply(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log, run = root / "commands.log", root / "run"
            env = {**os.environ, "FAKE_ATS_AGENT_LOG": str(log), "ATS_AGENT_EXECUTABLE_OVERRIDE": str(FAKE)}
            subprocess.run([sys.executable, str(RUNNER), "--", "prepare", "resume.docx", "job.md", "--out", str(run)], env=env, check=True)
            subprocess.run([sys.executable, str(SUMMARIZER), str(run / "proposal.json")], env=env, check=True)
            self.assertEqual(log.read_text(encoding="utf-8").splitlines(), ["prepare"])
            self.assertFalse((run / "tailored-resume.docx").exists())

    def test_explicit_selection_allows_following_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log, run = root / "commands.log", root / "run"
            env = {**os.environ, "FAKE_ATS_AGENT_LOG": str(log), "ATS_AGENT_EXECUTABLE_OVERRIDE": str(FAKE)}
            commands = [["prepare", "resume.docx", "job.md", "--out", str(run)], ["approve", str(run / "proposal.json"), "--select", "C1:balanced", "--output", str(run / "approval.json"), "--output-document", str(run / "tailored-resume.docx")], ["apply", str(run / "approval.json")], ["validate", str(run / "tailored-resume.docx")]]
            for command in commands:
                subprocess.run([sys.executable, str(RUNNER), "--", *command], env=env, check=True)
            self.assertEqual(log.read_text(encoding="utf-8").splitlines(), ["prepare", "approve", "apply", "validate"])
