from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AgentReleaseContractTests(unittest.TestCase):
    def test_release_contract(self) -> None:
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        self.assertRegex(project, r'(?m)^version\s*=\s*"1.0.0b3"$')
        for value in ("tailor-cv-agent-skill", "tailoring-ats-cvs-claude-plugin", "SHA256SUMS", "pypa/gh-action-pypi-publish", "id-token: write", "PRIVATE_HOLDOUT_B64"):
            self.assertIn(value, workflow)
