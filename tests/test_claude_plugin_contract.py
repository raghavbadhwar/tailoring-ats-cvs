from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ClaudePluginContractTests(unittest.TestCase):
    def test_manifest_points_to_portable_skill(self) -> None:
        manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "tailoring-ats-cvs")
        self.assertEqual(manifest["version"], "1.0.0-beta.4")
        self.assertEqual(manifest["skills"], ["./.agents/skills/tailor-cv"])

    def test_launchers_exist(self) -> None:
        posix = ROOT / "bin/ats-cv"
        self.assertTrue(posix.is_file())
        self.assertTrue((ROOT / "bin/ats-cv.cmd").is_file())
        if os.name != "nt":
            self.assertTrue(posix.stat().st_mode & 0o111)
