from __future__ import annotations

import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_agent_bundles import build_bundles

ROOT = Path(__file__).resolve().parents[1]


class AgentBundleBuildTests(unittest.TestCase):
    def test_reproducible_archives(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            first = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in build_bundles(ROOT, output)}
            second = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in build_bundles(ROOT, output)}
            self.assertEqual(first, second)
            with zipfile.ZipFile(output / "tailor-cv-agent-skill-v1.0.0-beta.4.zip") as archive:
                self.assertIn("tailor-cv/SKILL.md", archive.namelist())
            with zipfile.ZipFile(output / "tailoring-ats-cvs-claude-plugin-v1.0.0-beta.4.zip") as archive:
                self.assertIn("tailoring-ats-cvs/.claude-plugin/plugin.json", archive.namelist())
