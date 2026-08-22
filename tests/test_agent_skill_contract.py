from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AgentRepositoryContractTests(unittest.TestCase):
    def test_repository_instructions_and_design_exist(self) -> None:
        body = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("ats-agent is the source of truth", body)
        self.assertIn("never silently install", body.lower())
        self.assertTrue((ROOT / "docs/superpowers/specs/2026-08-17-agent-native-adapters-design.md").is_file())

    def test_portable_skill_has_resources(self) -> None:
        skill = ROOT / ".agents/skills/tailor-cv/SKILL.md"
        body = skill.read_text(encoding="utf-8")
        self.assertTrue(body.startswith("---\n"))
        self.assertIn("name: tailor-cv", body)
        self.assertIn("scripts/ensure_cli.py", body)
        self.assertIn("scripts/run_cli.py", body)
        self.assertIn("CODEX_HOME", body)
        self.assertIn("explicit approval", body.lower())
        self.assertIn("## Chat-first output", body)
        self.assertIn("Do not require the candidate to open JSON", body)
        for path in ("references/approval-policy.md", "references/cli-contract.md", "references/installation.md", "references/proposal-fields.md", "references/troubleshooting.md", "scripts/ensure_cli.py", "scripts/run_cli.py", "scripts/summarize_proposal.py", "assets/bootstrap-policy.json"):
            self.assertTrue((skill.parent / path).is_file(), path)
