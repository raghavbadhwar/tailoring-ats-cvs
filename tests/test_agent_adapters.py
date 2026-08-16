import json
import os
import subprocess
import sys
import sysconfig
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECK_INSTALL = ROOT / ".agents/skills/tailor-cv/scripts/check-install.py"
CLI = Path(sysconfig.get_path("scripts")) / ("ats-agent.exe" if os.name == "nt" else "ats-agent")


class AgentAdapterTests(unittest.TestCase):
    def test_claude_plugin_manifest_and_skill_are_well_formed(self) -> None:
        plugin_root = ROOT / "adapters/claude-code"
        manifest = json.loads(
            (plugin_root / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
        )
        skill = (plugin_root / "skills/tailor-cv/SKILL.md").read_text(encoding="utf-8")

        self.assertEqual(manifest["name"], "tailoring-ats-cvs")
        self.assertEqual(manifest["version"], "1.0.0b1")
        self.assertTrue(skill.startswith("---\n"))
        self.assertIn("ats-agent doctor", skill)
        self.assertIn("PROPOSE → EXPLICIT APPROVAL → APPLY → VALIDATE", skill)
        self.assertIn("ask for exact", skill.lower())

    def test_codex_skill_is_explicitly_approval_first(self) -> None:
        skill = (ROOT / ".agents/skills/tailor-cv/SKILL.md").read_text(encoding="utf-8")

        self.assertTrue(skill.startswith("---\nname: tailor-cv\n"))
        self.assertIn("Never run `ats-agent apply`", skill)
        self.assertIn("never overwrite the source cv", skill.lower())
        self.assertIn("install.sh --approved", skill)
        self.assertIn("install.ps1 -Approved", skill)

    def test_install_check_reports_missing_cli_without_installing(self) -> None:
        environment = os.environ.copy()
        environment["PATH"] = ""
        result = subprocess.run(
            [sys.executable, str(CHECK_INSTALL), "--json"],
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "missing")
        self.assertIn("uv tool install", payload["install_commands"]["uv"])
        self.assertIn("pipx install", payload["install_commands"]["pipx"])

    def test_install_check_verifies_the_existing_cli(self) -> None:
        self.assertTrue(CLI.is_file())
        environment = os.environ.copy()
        environment["PATH"] = f"{CLI.parent}{os.pathsep}{environment['PATH']}"
        result = subprocess.run(
            [sys.executable, str(CHECK_INSTALL), "--json"],
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "healthy")
        self.assertEqual(payload["checks"], {"doctor": 0, "help": 0, "smoke": 0})

    def test_cli_reports_the_package_version(self) -> None:
        self.assertTrue(CLI.is_file())
        result = subprocess.run(
            [str(CLI), "--version"],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "1.0.0b1")

    def test_bundle_builder_is_reproducible_and_complete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            command = [
                sys.executable,
                "scripts/build_adapter_bundles.py",
                "--output-dir",
                str(output),
            ]
            first = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
            self.assertEqual(first.returncode, 0, first.stderr)
            contents = {
                path.name: path.read_bytes()
                for path in sorted(output.glob("*.zip"))
            }
            second = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(
                contents,
                {path.name: path.read_bytes() for path in sorted(output.glob("*.zip"))},
            )

            with zipfile.ZipFile(output / "tailoring-ats-cvs-codex-skill-1.0.0b1.zip") as archive:
                self.assertIn("tailor-cv/SKILL.md", archive.namelist())
                self.assertIn("tailor-cv/scripts/check-install.py", archive.namelist())
            with zipfile.ZipFile(output / "tailoring-ats-cvs-claude-plugin-1.0.0b1.zip") as archive:
                self.assertIn("tailoring-ats-cvs/.claude-plugin/plugin.json", archive.namelist())
                self.assertIn("tailoring-ats-cvs/skills/tailor-cv/SKILL.md", archive.namelist())


if __name__ == "__main__":
    unittest.main()
