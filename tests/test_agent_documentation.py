from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AgentDocumentationTests(unittest.TestCase):
    def test_readme_documents_entry_points(self) -> None:
        body = (ROOT / "README.md").read_text(encoding="utf-8")
        for phrase in ("Standalone CLI", "Claude Code", "Codex", "uv tool install", "claude --plugin-dir .", ".agents/skills/tailor-cv"):
            self.assertIn(phrase, body)

    def test_docs_preserve_approval_boundary(self) -> None:
        for path in (ROOT / "docs/agent-adapters.md", ROOT / "integrations/claude-code.md", ROOT / "integrations/codex.md"):
            self.assertIn("explicit approval", path.read_text(encoding="utf-8").lower())
