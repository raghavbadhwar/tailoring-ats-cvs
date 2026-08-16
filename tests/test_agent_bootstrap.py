from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents/skills/tailor-cv/scripts/ensure_cli.py"
POLICY = SCRIPT.parents[1] / "assets/bootstrap-policy.json"


def load_module():
    spec = importlib.util.spec_from_file_location("ensure_cli", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BootstrapTests(unittest.TestCase):
    def test_missing_cli_never_installs_during_check(self) -> None:
        module = load_module()
        with patch.object(module.shutil, "which", return_value=None), patch.object(module.subprocess, "run") as run:
            result = module.check_cli(POLICY)
        self.assertEqual(result["status"], "bootstrap_required")
        run.assert_not_called()

    def test_healthy_cli_is_ready(self) -> None:
        module = load_module()
        doctor = {"package": {"version": "1.0.0b2"}, "strict_check": {"status": "passed"}}
        with patch.object(module.shutil, "which", return_value="/usr/bin/ats-agent"), patch.object(module.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(doctor), stderr="")) as run:
            result = module.check_cli(POLICY)
        self.assertEqual(result["status"], "ready")
        self.assertFalse(run.call_args.kwargs.get("shell", False))

    def test_install_uses_pinned_uv_spec(self) -> None:
        module = load_module()
        with patch.object(module.shutil, "which", side_effect=lambda name: "/usr/bin/uv" if name == "uv" else None), patch.object(module.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")) as run, patch.object(module, "check_cli", return_value={"status": "ready"}):
            result = module.install_cli(POLICY, "uv")
        self.assertEqual(result["status"], "installed")
        self.assertIn("tailoring-ats-cvs[documents]==1.0.0b2", run.call_args.args[0])
