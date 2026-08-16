from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ats_agent.cli import main
from ats_agent.job_research import _job_list, research_jobs


class JobResearchTests(unittest.TestCase):
    @staticmethod
    def _resolver(*_args, **_kwargs):
        return [(2, 1, 6, "", ("93.184.216.34", 0))]

    @staticmethod
    def _scrapling(command, **_kwargs):
        Path(command[4]).write_text(
            "Python, SQL, and Tableau are required for this analyst role.", encoding="utf-8"
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def test_batch_captures_each_job_and_keeps_keyword_coverage_evidence_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume = root / "resume.txt"
            jobs = root / "jobs.json"
            resume.write_text("SKILLS\nPython, SQL\n", encoding="utf-8")
            jobs.write_text(
                json.dumps(
                    {
                        "jobs": [
                            {
                                "id": "analyst",
                                "job_url": "https://jobs.example.com/analyst",
                                "context_urls": ["https://www.example.com/careers"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with patch("ats_agent.job_research.socket.getaddrinfo", self._resolver), patch(
                "ats_agent.job_research.shutil.which", return_value="/usr/bin/scrapling"
            ), patch("ats_agent.job_research.subprocess.run", side_effect=self._scrapling) as run:
                result = research_jobs(resume, jobs, root / "run", candidate_id="student")
            job = result["jobs"][0]
            self.assertEqual(job["status"], "draft")
            self.assertTrue((root / "run" / "manifest.json").is_file())
            self.assertTrue((root / "run" / "jobs" / "analyst" / "company-context.md").is_file())
            self.assertEqual(
                {item["coverage"] for item in job["keyword_coverage"]},
                {"direct", "unsupported"},
            )
            self.assertEqual(job["gap_recommendations"][0]["keywords"], ["tableau"])
            command = run.call_args.args[0]
            self.assertIn("--no-follow-redirects", command)
            self.assertIn("--no-stealthy-headers", command)
            self.assertFalse(run.call_args.kwargs["shell"])

    def test_private_job_urls_are_rejected_before_scrapling_runs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume, jobs = root / "resume.txt", root / "jobs.json"
            resume.write_text("Python\n", encoding="utf-8")
            jobs.write_text('[{"job_url": "https://127.0.0.1/private"}]', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "public IP"):
                research_jobs(resume, jobs, root / "run")

    def test_career_ops_pipeline_reads_pending_jobs_and_ignores_processed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume, jobs = root / "cv.md", root / "pipeline.md"
            resume.write_text("SKILLS\nPython, SQL\n", encoding="utf-8")
            jobs.write_text(
                """# Pipeline

## Pending
- [ ] https://jobs.example.com/analyst | Example Co | Data Analyst
- [ ] https://jobs.example.com/consultant

## Processed
- [x] https://jobs.example.com/old | Old Co | Old Role
""",
                encoding="utf-8",
            )
            with patch("ats_agent.job_research.socket.getaddrinfo", self._resolver), patch(
                "ats_agent.job_research.shutil.which", return_value="/usr/bin/scrapling"
            ), patch("ats_agent.job_research.subprocess.run", side_effect=self._scrapling):
                result = research_jobs(resume, jobs, root / "run")

            self.assertEqual(result["job_count"], 2)
            self.assertEqual(result["jobs"][0]["company"], "Example Co")
            self.assertEqual(result["jobs"][0]["role"], "Data Analyst")
            self.assertNotIn("Old Co", (root / "run" / "manifest.json").read_text())

    def test_invalid_job_lists_and_unavailable_scrapling_are_safe_failures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jobs = root / "jobs.json"
            for payload, message in (
                ("{", "valid JSON or Career-Ops Markdown"),
                ("[]", "between 1"),
                ("[1]", "must be an object"),
                ('[{"job_url": "http://example.com"}]', "public HTTPS"),
                ('[{"job_url": "https://example.com", "context_urls": "bad"}]', "context_urls"),
            ):
                jobs.write_text(payload, encoding="utf-8")
                with self.subTest(payload=payload), self.assertRaisesRegex(ValueError, message):
                    _job_list(jobs)

            resume = root / "resume.txt"
            resume.write_text("Python\n", encoding="utf-8")
            jobs.write_text('[{"job_url": "https://example.com"}]', encoding="utf-8")
            with patch("ats_agent.job_research.socket.getaddrinfo", self._resolver), patch(
                "ats_agent.job_research.shutil.which", return_value=None
            ):
                result = research_jobs(resume, jobs, root / "run")
            self.assertEqual(result["jobs"][0]["status"], "blocked")
            self.assertIn("install it separately", result["jobs"][0]["reason"])

    def test_cli_dispatches_job_research(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume, jobs, out = root / "resume.txt", root / "jobs.json", root / "run"
            resume.write_text("Python\n", encoding="utf-8")
            jobs.write_text("[]", encoding="utf-8")
            with patch("ats_agent.cli.research_jobs", return_value={"status": "draft"}) as research:
                self.assertEqual(
                    main(["research-jobs", str(resume), str(jobs), "--out", str(out)]),
                    0,
                )
            research.assert_called_once_with(resume, jobs, out, candidate_id="candidate")
