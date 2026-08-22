from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
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
    def test_version_key_handles_beta_and_trailing_zeroes(self) -> None:
        module = load_module()
        self.assertLess(module.version_key("1.0.0b2"), module.version_key("1.0.0"))
        self.assertEqual(module.version_key("1.0"), module.version_key("1.0.0"))

    def test_check_runs_without_site_packages(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-S", str(SCRIPT), "--check"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertIn(completed.returncode, (0, 20, 21))
        self.assertIn(
            json.loads(completed.stdout)["status"],
            {"ready", "bootstrap_required", "upgrade_required"},
        )

    def test_missing_cli_never_installs_during_check(self) -> None:
        module = load_module()
        with patch.object(module.shutil, "which", return_value=None), patch.object(module.subprocess, "run") as run:
            result = module.check_cli(POLICY)
        self.assertEqual(result["status"], "bootstrap_required")
        run.assert_not_called()

    def test_healthy_cli_is_ready(self) -> None:
        module = load_module()
        doctor = {"package": {"version": "1.0.0b3"}, "strict_check": {"status": "passed"}}
        with patch.object(module.shutil, "which", return_value="/usr/bin/ats-agent"), patch.object(module.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(doctor), stderr="")) as run:
            result = module.check_cli(POLICY)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["version"], "1.0.0b3")
        self.assertFalse(run.call_args.kwargs.get("shell", False))

    def test_install_uses_pinned_uv_spec(self) -> None:
        module = load_module()
        with patch.object(module.shutil, "which", side_effect=lambda name: "/usr/bin/uv" if name == "uv" else None), patch.object(module.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")) as run, patch.object(module, "check_cli", return_value={"status": "ready"}):
            result = module.install_cli(POLICY, "uv")
        self.assertEqual(result["status"], "installed")
        self.assertIn("tailoring-ats-cvs[documents]==1.0.0b3", run.call_args.args[0])

    def test_check_enumerates_full_attempt_chain(self) -> None:
        module = load_module()
        with patch.object(module.shutil, "which", return_value=None):
            result = module.check_cli(POLICY)
        tiers = [item["tier"] for item in result["attempts"]]
        self.assertEqual(
            tiers,
            ["uv-pypi", "pipx-pypi", "uv-git", "pipx-git", "venv-pip"],
        )
        self.assertTrue(result["requires_user_approval"])
        self.assertIn("approval", result["message"].lower())

    def test_install_falls_through_failed_tiers_in_order(self) -> None:
        module = load_module()
        attempted: list[list[str]] = []

        def fake_run(argv, **_kwargs):
            attempted.append(list(argv))
            joined = " ".join(str(part) for part in argv)
            if "uv tool install" in joined and "[documents]" in joined:
                return SimpleNamespace(returncode=1, stdout="", stderr="pypi 404")
            if "pipx install" in joined:
                return SimpleNamespace(returncode=1, stdout="", stderr="no pipx pkg")
            if ("uv tool install" in joined
                    and "git+https://github.com/raghavbadhwar/tailoring-ats-cvs.git@v1.0.0-beta.3" in joined):
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            raise AssertionError(f"unexpected tier executed: {argv}")

        with patch.object(module.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}" if name in {"uv", "pipx"} else None), \
             patch.object(module.subprocess, "run", side_effect=fake_run), \
             patch.dict(module.os.environ, {}, clear=False), \
             patch.object(module, "read_manifest", return_value={}), \
             patch.object(module, "write_manifest", return_value=None), \
             patch.object(module, "check_cli", return_value={
                 "status": "ready",
                 "executable": "/opt/uv-tools/ats-agent",
                 "version": "1.0.0b3",
             }):
            result = module.install_cli(POLICY, "auto")
        self.assertEqual(result["status"], "installed")
        self.assertEqual(result["tier"], "uv-git")
        self.assertIn("git+https://github.com/raghavbadhwar/tailoring-ats-cvs.git@v1.0.0-beta.3",
                      attempted[2][-1])

    def test_manifest_resolves_executable_without_path(self) -> None:
        import tempfile
        module = load_module()
        recorded = {
            "schema_version": 1,
            "tier": "venv-pip",
            "executable": "/opt/engine/ats-agent",
            "version": "1.0.0b3",
        }
        doctor = {"package": {"version": "1.0.0b3"}, "strict_check": {"status": "passed"}}
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "install.json"
            policy = dict(load_module().load_policy(POLICY))
            policy["state_file"] = str(state)
            state.write_text(json.dumps(recorded), encoding="utf-8")
            with patch.object(Path, "is_file", lambda self: True), \
                 patch.object(module.shutil, "which", return_value=None), \
                 patch.object(module.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(doctor), stderr="")):
                result = module.check_cli.__wrapped__(module, policy) if hasattr(module.check_cli, "__wrapped__") else _check_with_policy(module, policy)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["resolved_from"], "venv-pip install manifest")

    def test_policy_v1_rejected_with_guidance(self) -> None:
        import tempfile
        module = load_module()
        legacy = json.loads(POLICY.read_text(encoding="utf-8"))
        legacy["schema_version"] = 1
        legacy.pop("install_attempts", None)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            path.write_text(json.dumps(legacy), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "regenerate"):
                module.load_policy(path)


def _check_with_policy(module, policy):
    from pathlib import Path as _Path

    original = module.load_policy
    module.load_policy = lambda _path: policy
    try:
        return module.check_cli(_Path("policy.json"))
    finally:
        module.load_policy = original
