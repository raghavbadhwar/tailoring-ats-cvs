from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ats_agent.cli import main
from ats_agent.hashing import verify_proposal_digest
from ats_agent.job_research import _job_list, research_jobs
from ats_agent.workflow import _validate_research_freshness


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
            proposal = json.loads(Path(job["proposal"]).read_text(encoding="utf-8"))
            self.assertEqual(
                verify_proposal_digest(proposal), proposal["proposal_digest"]
            )
            self.assertTrue(all(item["source_url"] == "https://jobs.example.com/analyst" for item in proposal["requirements"]))
            self.assertTrue(all(item["capture_sha256"] for item in proposal["requirements"]))
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

    def test_capture_cleanup_removes_chrome_and_rejects_insufficient_text(self) -> None:
        from ats_agent.job_research import _clean_capture

        self.assertEqual(
            _clean_capture("Cookie\nPython is required.\nPython is required.\n"),
            "Python is required.\n",
        )

    def test_labelled_fallback_survives_a_failed_direct_capture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume, jobs = root / "resume.txt", root / "jobs.json"
            resume.write_text("PROJECTS\nBuilt Python analysis workflows.\n", encoding="utf-8")
            jobs.write_text(
                json.dumps(
                    [{
                        "id": "fallback-role",
                        "job_url": "https://jobs.example.com/role",
                        "fallback": {
                            "description": "Python is required for this role.",
                            "source_url": "https://listing.example.com/role",
                            "provider": "Example Listings",
                            "fetched_at": "2026-08-17T00:00:00Z",
                        },
                    }]
                ),
                encoding="utf-8",
            )
            with patch("ats_agent.job_research.socket.getaddrinfo", self._resolver), patch(
                "ats_agent.job_research.shutil.which", return_value="/usr/bin/scrapling"
            ), patch(
                "ats_agent.job_research.subprocess.run",
                return_value=SimpleNamespace(returncode=1, stdout="", stderr="empty capture"),
            ):
                result = research_jobs(resume, jobs, root / "run")

            self.assertEqual(result["jobs"][0]["status"], "draft")
            sources = json.loads(
                Path(result["jobs"][0]["capture_manifest"]).read_text(encoding="utf-8")
            )["sources"]
            self.assertEqual(sources[0]["extraction_status"], "failed")
            self.assertEqual(sources[1]["source_type"], "aggregator_fallback")
            self.assertEqual(sources[1]["extraction_status"], "fallback_used")

    def test_sourced_role_dossier_is_merged_and_unsourced_clause_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume, jobs = root / "resume.txt", root / "jobs.json"
            resume.write_text("PROJECTS\nBuilt Python workflows.\n", encoding="utf-8")
            captured = "Build golden datasets for reliable AI response evaluation today."
            jobs.write_text(
                json.dumps([{
                    "id": "dossier-role",
                    "job_url": "https://jobs.example.com/role",
                    "role_dossier": [{
                        "text": "Build golden datasets for reliable AI response evaluation today.",
                        "source_span": {"start": 0, "end": len(captured)},
                        "normalized_terms": ["golden datasets", "ai response quality"],
                        "kind": "responsibility",
                        "importance": "mandatory",
                    }],
                }]),
                encoding="utf-8",
            )
            with patch("ats_agent.job_research.socket.getaddrinfo", self._resolver), patch(
                "ats_agent.job_research.shutil.which", return_value="/usr/bin/scrapling"
            ), patch(
                "ats_agent.job_research.subprocess.run",
                side_effect=lambda command, **_kwargs: (
                    Path(command[4]).write_text(captured, encoding="utf-8"),
                    SimpleNamespace(returncode=0, stdout="", stderr=""),
                )[1],
            ):
                result = research_jobs(resume, jobs, root / "run")
            proposal = json.loads(Path(result["jobs"][0]["proposal"]).read_text(encoding="utf-8"))
            requirement = next(item for item in proposal["requirements"] if item.get("dossier_source"))
            self.assertEqual(requirement["source_excerpt"], captured)
            self.assertEqual(requirement["source_type"], "official_job_page")
            from ats_agent.job_research import _validate_role_dossier

            with self.assertRaisesRegex(ValueError, "match captured source"):
                _validate_role_dossier(
                    [{
                        "text": "Invented requirement.",
                        "source_span": {"start": 0, "end": 21},
                        "normalized_terms": ["invented"],
                    }],
                    captured,
                    {
                        "url": "https://jobs.example.com/role",
                        "sha256": "a" * 64,
                        "source_type": "official_job_page",
                    },
                )

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
            self.assertEqual(result["jobs"][0]["status"], "blocked_capture")
            self.assertIn("install it separately", result["jobs"][0]["reason"])

    def test_expired_and_eligibility_warning_rows_remain_visible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume, jobs = root / "resume.txt", root / "jobs.json"
            resume.write_text("PROJECTS\nBuilt Python workflows.\n", encoding="utf-8")
            jobs.write_text(
                json.dumps([{"id": "old", "job_url": "https://jobs.example.com/old", "status": "expired"}]),
                encoding="utf-8",
            )
            with patch("ats_agent.job_research.socket.getaddrinfo", self._resolver):
                result = research_jobs(resume, jobs, root / "run")
            self.assertEqual(result["jobs"][0]["status"], "expired")

    def test_stale_research_cannot_be_applied_without_refresh(self) -> None:
        with self.assertRaisesRegex(ValueError, "stale"):
            _validate_research_freshness({"research": {"captured_at": "2000-01-01T00:00:00+00:00"}})

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
            research.assert_called_once_with(
                resume,
                jobs,
                out,
                candidate_id="candidate",
                evidence_paths=[],
                context_urls=[],
                provider=None,
            )
