import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ats_agent.reporting import write_review_artifacts
from ats_agent.workflow import build_proposal


class ReportingTests(unittest.TestCase):
    def test_review_artifacts_include_changes_and_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume = root / "resume.txt"
            jd = root / "job.md"
            resume.write_text("PROJECTS\n- Helped build automated order workflows with 42 tests.\n", encoding="utf-8")
            jd.write_text("Workflow automation is required.", encoding="utf-8")
            proposal = build_proposal(resume, jd, candidate_id="candidate-a")
            paths = write_review_artifacts(proposal, root / "run")
            self.assertTrue(Path(paths["markdown"]).exists())
            self.assertTrue(Path(paths["html"]).exists())
            self.assertIn("Evidence", Path(paths["markdown"]).read_text(encoding="utf-8"))
            self.assertIn("approval-manifest", Path(paths["html"]).read_text(encoding="utf-8"))

    def test_prepare_cli_writes_run_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume = root / "resume.txt"
            jd = root / "job.md"
            out = root / "run"
            resume.write_text("PROJECTS\n- Helped build automated order workflows with 42 tests.\n", encoding="utf-8")
            jd.write_text("Workflow automation is required.", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "ats_agent.cli", "prepare", str(resume), str(jd), "--candidate-id", "candidate-a", "--out", str(out)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(Path(payload["proposal"]).exists())
            self.assertTrue(Path(payload["review_html"]).exists())


if __name__ == "__main__":
    unittest.main()
