"""Tests for the Codex native skill installer."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install_codex_skill.py"


def load_module():
    spec = importlib.util.spec_from_file_location("install_codex_skill", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CodexInstallerTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        patcher = patch.dict(self.module.os.environ,
                             {"CODEX_HOME": str(Path(self._tmp.name) / "codex")})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_install_is_idempotent_and_reports_up_to_date(self) -> None:
        first = self.module.install(force=False)
        self.assertEqual(first["status"], "installed")
        second = self.module.check()
        self.assertEqual(second["status"], "up_to_date")
        again = self.module.install(force=False)
        self.assertEqual(again["status"], "installed")

    def test_installed_tree_contains_skill_and_manifest(self) -> None:
        self.module.install(force=False)
        dest = Path(self.module.destination())
        self.assertTrue((dest / "SKILL.md").exists())
        self.assertTrue((dest / "scripts" / "ensure_cli.py").exists())
        manifest = json.loads((dest / "INSTALL_MANIFEST.json").read_text())
        self.assertEqual(manifest["skill"], "tailor-cv")

    def test_uninstall_removes_destination(self) -> None:
        self.module.install(force=False)
        removed = self.module.uninstall()
        self.assertEqual(removed["status"], "uninstalled")
        self.assertFalse(Path(self.module.destination()).exists())


if __name__ == "__main__":
    unittest.main()
