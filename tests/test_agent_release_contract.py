from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AgentReleaseContractTests(unittest.TestCase):
    def test_release_contract(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        self.assertEqual(project["version"], "1.0.0b2")
        for value in ("tailor-cv-agent-skill", "tailoring-ats-cvs-claude-plugin", "SHA256SUMS", "pypa/gh-action-pypi-publish", "id-token: write", "PRIVATE_HOLDOUT_B64"):
            self.assertIn(value, workflow)
