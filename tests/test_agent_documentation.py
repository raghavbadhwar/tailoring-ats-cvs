from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AgentDocumentationTests(unittest.TestCase):
    def test_agent_contract_and_soul_preserve_core_boundaries(self) -> None:
        instructions = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        contract = " ".join((ROOT / "agent.md").read_text(encoding="utf-8").split())
        soul = (ROOT / "soul.md").read_text(encoding="utf-8")

        self.assertIn("[agent.md](agent.md)", instructions)
        self.assertIn("[soul.md](soul.md)", instructions)
        for phrase in (
            "DISCOVER -> CAPTURE -> ANALYSE -> PROPOSE -> EXPLICIT APPROVAL -> APPLY -> VALIDATE",
            "AI Job Search",
            "it does not supply candidate facts.",
            "not a claim that every milestone is already implemented",
            "never candidate evidence",
            "proposal digest",
            "Never mutate the source CV, AI Job Search export, or application tracker.",
        ):
            self.assertIn(phrase, contract)
        self.assertIn("more willing to say \"not supported\"", soul)

    def test_readme_documents_entry_points(self) -> None:
        body = (ROOT / "README.md").read_text(encoding="utf-8")
        for phrase in ("Standalone CLI", "Claude Code", "Codex", "uv tool install", "claude --plugin-dir .", ".agents/skills/tailor-cv"):
            self.assertIn(phrase, body)

    def test_docs_preserve_approval_boundary(self) -> None:
        for path in (ROOT / "docs/agent-adapters.md", ROOT / "integrations/claude-code.md", ROOT / "integrations/codex.md"):
            self.assertIn("explicit approval", path.read_text(encoding="utf-8").lower())
