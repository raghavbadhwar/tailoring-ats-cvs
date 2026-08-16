from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PATHS = (".upgrade", ".release-v090")
FORBIDDEN_WORKFLOW_TOKENS = (
    "base64 --decode",
    "payload.part",
    "git push origin HEAD:",
)


def _workflow_text() -> str:
    workflows = ROOT / ".github" / "workflows"
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(workflows.glob("*.yml"))
    )


class ReleaseIntegrityTests(unittest.TestCase):
    def test_release_tree_contains_no_hidden_source_or_self_replacement(self) -> None:
        self.assertFalse(any((ROOT / path).exists() for path in FORBIDDEN_PATHS))
        workflow_text = _workflow_text()
        for token in FORBIDDEN_WORKFLOW_TOKENS:
            self.assertNotIn(token, workflow_text)

    def test_ci_uses_current_node24_actions(self) -> None:
        workflow_text = _workflow_text()
        self.assertIn("actions/checkout@v7", workflow_text)
        self.assertIn("actions/setup-python@v7", workflow_text)
        self.assertNotIn("actions/checkout@v4", workflow_text)
        self.assertNotIn("actions/setup-python@v5", workflow_text)


if __name__ == "__main__":
    unittest.main()
