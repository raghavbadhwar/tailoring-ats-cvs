import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "src.ats_agent.cli", *args], cwd=ROOT, text=True, capture_output=True)

    def test_audit_validates_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            resume, job = Path(directory) / "resume.txt", Path(directory) / "job.md"
            resume.write_text("resume", encoding="utf-8")
            job.write_text("job", encoding="utf-8")
            result = self.run_cli("audit", str(resume), str(job))
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["status"], "ready")

    def test_apply_requires_string_change_ids(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as manifest:
            json.dump({"approved_change_ids": ["C1"]}, manifest)
            path = manifest.name
        result = self.run_cli("apply", path)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(json.loads(result.stdout)["source_overwrite"])

    def test_format_reports_layout_risks(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as resume:
            resume.write("EDUCATION\n" + "A" * 121 + "\n\tEXPERIENCE\nSKILLS\n")
            path = resume.name
        result = self.run_cli("format", path, "--json")
        self.assertEqual(result.returncode, 0)
        findings = {item["id"] for item in json.loads(result.stdout)["findings"]}
        self.assertTrue({"F2", "F3"}.issubset(findings))

    def test_propose_emits_named_agent_report_without_editing_source(self):
        with tempfile.TemporaryDirectory() as directory:
            resume, job = Path(directory) / "resume.txt", Path(directory) / "job.md"
            resume.write_text("SUMMARY\n2026\n- Built Python workflow automation with 42 tests.\n", encoding="utf-8")
            job.write_text("Required Python and workflow automation for AI agents.", encoding="utf-8")
            before = resume.read_text(encoding="utf-8")
            result = self.run_cli("propose", str(resume), str(job))
            payload = json.loads(result.stdout)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(payload["status"], "draft")
            self.assertIn("ats", payload["report"]["agents"])
            self.assertIn("hiring_manager", payload["report"]["agents"])
            self.assertEqual(resume.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
