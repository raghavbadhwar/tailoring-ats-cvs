from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor as StandardThreadPoolExecutor
from pathlib import Path
from threading import Barrier, BrokenBarrierError, Event, Lock
from types import SimpleNamespace
from unittest.mock import patch

from ats_agent.cli import main
from ats_agent.hashing import verify_proposal_digest
from ats_agent.job_research import (
    MAX_JOBS,
    _gap_recommendations,
    _job_list,
    _research_input_digest,
    _research_input_identity,
    research_jobs,
)
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
            with patch.dict(__import__("os").environ, {"ATS_CAPTURE_FAST_PACE": "1"}), patch("ats_agent.job_research.socket.getaddrinfo", self._resolver), patch(
                "ats_agent.capture.shutil.which", return_value="/usr/bin/scrapling"
            ), patch("ats_agent.capture.subprocess.run", side_effect=self._scrapling) as run:
                result = research_jobs(resume, jobs, root / "run", candidate_id="student")
            job = result["jobs"][0]
            self.assertEqual(job["status"], "draft")
            self.assertEqual(job["lifecycle_status"], "proposal_draft")
            self.assertEqual(job["warnings"], [])
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
            self.assertTrue(all(item["source_type"] == "third_party_job_page" for item in proposal["requirements"]))
            command = run.call_args.args[0]
            self.assertIn("allow_redirects=False", command[2])
            self.assertIn("impersonate=None", command[2])
            self.assertIn("CurlOpt.RESOLVE", command[2])
            self.assertFalse(run.call_args.kwargs["shell"])

    def test_private_job_urls_are_rejected_before_scrapling_runs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume, jobs = root / "resume.txt", root / "jobs.json"
            resume.write_text("Python\n", encoding="utf-8")
            jobs.write_text('[{"job_url": "https://127.0.0.1/private"}]', encoding="utf-8")
            with patch("ats_agent.job_research.socket.getaddrinfo", self._resolver), \
                 patch("ats_agent.capture.require_scrapling") as capture:
                result = research_jobs(resume, jobs, root / "run")
            self.assertEqual(result["jobs"][0]["status"], "blocked_import")
            self.assertIn("public IP", result["jobs"][0]["reason"])
            capture.assert_not_called()

    def test_explicit_internship_is_visible_but_not_captured_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume, jobs = root / "resume.txt", root / "jobs.json"
            resume.write_text("Python\n", encoding="utf-8")
            jobs.write_text(
                json.dumps(
                    [
                        {
                            "id": "intern-role",
                            "role": "Product Operations Intern",
                            "employment_type": "internship",
                            "job_url": "https://jobs.example.com/intern",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            with patch("ats_agent.job_research.socket.getaddrinfo", self._resolver), \
                 patch("ats_agent.capture.require_scrapling") as capture:
                result = research_jobs(resume, jobs, root / "run")

            row = result["jobs"][0]
            self.assertEqual(row["status"], "excluded_scope")
            self.assertEqual(row["lifecycle_status"], "excluded_scope")
            self.assertIn("full-time jobs-only", row["reason"])
            capture.assert_not_called()

    def test_research_identity_hashes_provider_configuration(self) -> None:
        class SecretProvider:
            provider_id = "secret-test"
            provider_version = "1"

            def __init__(self, token: str) -> None:
                self.token = token

            def generate(self, _context):
                return []

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume, jobs_path = root / "resume.txt", root / "jobs.json"
            resume.write_text("Python\n", encoding="utf-8")
            jobs_path.write_text("[]", encoding="utf-8")
            jobs = [{"id": "role", "job_url": "https://jobs.example.com/role"}]
            first = _research_input_identity(
                resume=resume,
                job_list=jobs_path,
                jobs=jobs,
                candidate_id="candidate",
                evidence_paths=[],
                context_urls=[],
                provider=SecretProvider("not-for-manifests"),
                selected_job_ids=None,
                constraint_text=None,
            )
            second = _research_input_identity(
                resume=resume,
                job_list=jobs_path,
                jobs=jobs,
                candidate_id="candidate",
                evidence_paths=[],
                context_urls=[],
                provider=SecretProvider("changed-token"),
                selected_job_ids=None,
                constraint_text=None,
            )

        self.assertNotIn("not-for-manifests", json.dumps(first))
        self.assertIn("configuration_sha256", first["provider"])
        self.assertNotEqual(_research_input_digest(first), _research_input_digest(second))

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
            with patch.dict(__import__("os").environ, {"ATS_CAPTURE_FAST_PACE": "1"}), patch("ats_agent.job_research.socket.getaddrinfo", self._resolver), patch(
                "ats_agent.capture.shutil.which", return_value="/usr/bin/scrapling"
            ), patch(
                "ats_agent.capture.subprocess.run",
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
            with patch.dict(__import__("os").environ, {"ATS_CAPTURE_FAST_PACE": "1"}), patch("ats_agent.job_research.socket.getaddrinfo", self._resolver), patch(
                "ats_agent.capture.shutil.which", return_value="/usr/bin/scrapling"
            ), patch(
                "ats_agent.capture.subprocess.run",
                side_effect=lambda command, **_kwargs: (
                    Path(command[4]).write_text(captured, encoding="utf-8"),
                    SimpleNamespace(returncode=0, stdout="", stderr=""),
                )[1],
            ):
                result = research_jobs(resume, jobs, root / "run")
            proposal = json.loads(Path(result["jobs"][0]["proposal"]).read_text(encoding="utf-8"))
            requirement = next(item for item in proposal["requirements"] if item.get("dossier_source"))
            self.assertEqual(requirement["source_excerpt"], captured)
            self.assertEqual(requirement["source_type"], "third_party_job_page")
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
            with patch.dict(__import__("os").environ, {"ATS_CAPTURE_FAST_PACE": "1"}), patch("ats_agent.job_research.socket.getaddrinfo", self._resolver), patch(
                "ats_agent.capture.shutil.which", return_value="/usr/bin/scrapling"
            ), patch("ats_agent.capture.subprocess.run", side_effect=self._scrapling):
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
            with patch.dict(__import__("os").environ, {"ATS_CAPTURE_FAST_PACE": "1"}), patch("ats_agent.job_research.socket.getaddrinfo", self._resolver), patch(
                "ats_agent.capture.shutil.which", return_value=None
            ):
                result = research_jobs(resume, jobs, root / "run")
            self.assertEqual(result["jobs"][0]["status"], "blocked_capture")
            self.assertIn("install it separately", result["jobs"][0]["reason"])
            recovery = json.loads(
                Path(result["jobs"][0]["capture_recovery"]).read_text(encoding="utf-8")
            )
            self.assertEqual(recovery["original_url"], "https://example.com")
            self.assertEqual(recovery["status"], "blocked_capture")
            self.assertTrue(recovery["accepted_inputs"])

    def test_legacy_seen_export_retains_invalid_rows_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume, jobs = root / "resume.txt", root / "seen_jobs.json"
            resume.write_text("SKILLS\nPython\n", encoding="utf-8")
            payload = {
                "seen": {
                    "linkedin-good": {
                        "title": "Data Analyst",
                        "company": "Example Co",
                        "url": "https://www.linkedin.com/jobs/view/123",
                        "portal": "linkedin",
                        "status": "ranked",
                    },
                    "unsafe": {
                        "title": "Unsafe",
                        "url": "http://unsafe.example.com/private",
                        "portal": "linkedin",
                    },
                    "malformed": ["not a job object"],
                }
            }
            jobs.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            before = jobs.read_bytes()
            with patch.dict(__import__("os").environ, {"ATS_CAPTURE_FAST_PACE": "1"}), patch("ats_agent.job_research.socket.getaddrinfo", self._resolver), patch(
                "ats_agent.capture.shutil.which", return_value="/usr/bin/scrapling"
            ), patch("ats_agent.capture.subprocess.run", side_effect=self._scrapling):
                result = research_jobs(resume, jobs, root / "run")

            self.assertEqual(jobs.read_bytes(), before)
            self.assertEqual(result["job_count"], 3)
            good, unsafe, malformed = result["jobs"]
            self.assertEqual(good["id"], _job_list(jobs)[0]["id"])
            self.assertEqual(good["discovery"]["portal"], "linkedin")
            self.assertEqual(good["status"], "draft")
            self.assertEqual(unsafe["status"], "blocked_import")
            self.assertEqual(malformed["status"], "blocked_import")
            self.assertNotIn("job_url", malformed)

    def test_legacy_export_missing_seen_is_a_visible_import_block(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            jobs = Path(directory) / "seen_jobs.json"
            jobs.write_text("{}", encoding="utf-8")
            imported = _job_list(jobs)
        self.assertEqual(imported[0]["import_status"], "blocked_import")
        self.assertIn("'seen' object", str(imported[0]["reason"]))

    def test_legacy_import_caps_default_capture_and_allows_explicit_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume, jobs = root / "resume.txt", root / "seen_jobs.json"
            resume.write_text("SKILLS\nPython\n", encoding="utf-8")
            jobs.write_text(
                json.dumps(
                    {
                        "seen": {
                            f"role-{index}": {
                                "title": f"Role {index}",
                                "company": "Example Co",
                                "url": f"https://www.linkedin.com/jobs/view/{index}",
                                "portal": "linkedin",
                            }
                            for index in range(MAX_JOBS + 1)
                        }
                    }
                ),
                encoding="utf-8",
            )
            selected = [job["id"] for job in _job_list(jobs)]
            submitted: list[int] = []

            class RecordingExecutor(StandardThreadPoolExecutor):
                def submit(self, *args, **kwargs):
                    submitted.append(1)
                    return super().submit(*args, **kwargs)

            with patch.dict(__import__("os").environ, {"ATS_CAPTURE_FAST_PACE": "1"}), patch("ats_agent.job_research.socket.getaddrinfo", self._resolver), patch(
                "ats_agent.capture.shutil.which", return_value="/usr/bin/scrapling"
            ), patch("ats_agent.capture.subprocess.run", side_effect=self._scrapling) as capture, patch(
                "ats_agent.job_research.ThreadPoolExecutor", RecordingExecutor
            ):
                default = research_jobs(resume, jobs, root / "default")

            self.assertEqual(capture.call_count, MAX_JOBS)
            self.assertEqual(len(submitted), MAX_JOBS)
            self.assertEqual(default["job_count"], MAX_JOBS + 1)
            self.assertEqual(default["jobs"][-1]["lifecycle_status"], "imported")
            self.assertIn("default", default["jobs"][-1]["reason"])

            submitted.clear()
            with patch.dict(__import__("os").environ, {"ATS_CAPTURE_FAST_PACE": "1"}), patch("ats_agent.job_research.socket.getaddrinfo", self._resolver), patch(
                "ats_agent.capture.shutil.which", return_value="/usr/bin/scrapling"
            ), patch("ats_agent.capture.subprocess.run", side_effect=self._scrapling) as capture, patch(
                "ats_agent.job_research.ThreadPoolExecutor", RecordingExecutor
            ):
                explicit = research_jobs(
                    resume, jobs, root / "explicit", selected_job_ids=selected
                )

            self.assertEqual(capture.call_count, MAX_JOBS + 1)
            self.assertEqual(len(submitted), MAX_JOBS + 1)
            self.assertTrue(all(job["lifecycle_status"] == "proposal_draft" for job in explicit["jobs"]))

    def test_non_capture_rows_do_not_consume_worker_futures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume, jobs = root / "resume.txt", root / "jobs.json"
            resume.write_text("SKILLS\nPython\n", encoding="utf-8")
            jobs.write_text(
                json.dumps(
                    [
                        {"id": "capture", "job_url": "https://jobs.example.com/capture"},
                        {"id": "expired", "job_url": "https://jobs.example.com/expired", "status": "expired"},
                        {"id": "private", "job_url": "http://127.0.0.1/private"},
                    ]
                ),
                encoding="utf-8",
            )
            submitted: list[int] = []

            class RecordingExecutor(StandardThreadPoolExecutor):
                def submit(self, *args, **kwargs):
                    submitted.append(1)
                    return super().submit(*args, **kwargs)

            with patch.dict(__import__("os").environ, {"ATS_CAPTURE_FAST_PACE": "1"}), patch(
                "ats_agent.job_research.socket.getaddrinfo", self._resolver
            ), patch("ats_agent.capture.shutil.which", return_value="/usr/bin/scrapling"), patch(
                "ats_agent.capture.subprocess.run", side_effect=self._scrapling
            ) as capture, patch("ats_agent.job_research.ThreadPoolExecutor", RecordingExecutor):
                result = research_jobs(resume, jobs, root / "run")

        self.assertEqual(capture.call_count, 1)
        self.assertEqual(len(submitted), 1)
        self.assertEqual(
            [job["lifecycle_status"] for job in result["jobs"]],
            ["proposal_draft", "expired", "blocked_import"],
        )

    def test_official_provenance_requires_matching_job_and_verification_hosts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume, jobs = root / "resume.txt", root / "jobs.json"
            resume.write_text("SKILLS\nPython\n", encoding="utf-8")
            jobs.write_text(
                json.dumps(
                    [
                        {
                            "id": "official",
                            "job_url": "https://jobs.example.com/role",
                            "official_job_host": "jobs.example.com",
                            "official_host_verification_url": "https://jobs.example.com/careers",
                        },
                        {
                            "id": "mismatch",
                            "job_url": "https://www.linkedin.com/jobs/view/123",
                            "official_job_host": "jobs.example.com",
                            "official_host_verification_url": "https://jobs.example.com/careers",
                        },
                    ]
                ),
                encoding="utf-8",
            )
            with patch.dict(__import__("os").environ, {"ATS_CAPTURE_FAST_PACE": "1"}), patch("ats_agent.job_research.socket.getaddrinfo", self._resolver), patch(
                "ats_agent.capture.shutil.which", return_value="/usr/bin/scrapling"
            ), patch("ats_agent.capture.subprocess.run", side_effect=self._scrapling):
                result = research_jobs(resume, jobs, root / "run")

            official = json.loads(Path(result["jobs"][0]["proposal"]).read_text(encoding="utf-8"))
            mismatch = json.loads(Path(result["jobs"][1]["proposal"]).read_text(encoding="utf-8"))
            self.assertTrue(all(item["source_type"] == "official_job_page" for item in official["requirements"]))
            self.assertTrue(all(item["source_type"] == "third_party_job_page" for item in mismatch["requirements"]))

    def test_gap_recommendations_deduplicate_and_exclude_generic_gates(self) -> None:
        coverage = [
            {
                "requirement_id": "R2",
                "keywords": ["python"],
                "category": "technical",
                "importance": "preferred",
                "coverage": "unsupported",
                "source_quality": {},
            },
            {
                "requirement_id": "R1",
                "keywords": ["python", "golden datasets"],
                "category": "technical",
                "importance": "mandatory",
                "coverage": "unsupported",
                "source_quality": {},
            },
            {
                "requirement_id": "R3",
                "keywords": ["work authorization", "master", "remote", "professional experience"],
                "category": "eligibility",
                "importance": "mandatory",
                "coverage": "unsupported",
                "source_quality": {},
            },
        ]
        gaps = _gap_recommendations(coverage)
        self.assertEqual([gap["keywords"] for gap in gaps], [["golden datasets"], ["python"]])
        self.assertEqual([gap["requirement_id"] for gap in gaps], ["R1", "R1"])

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
            self.assertEqual(result["jobs"][0]["lifecycle_status"], "expired")

    def test_eligibility_warning_is_a_warning_not_a_lifecycle_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume, jobs = root / "resume.txt", root / "jobs.json"
            resume.write_text("SKILLS\nPython\n", encoding="utf-8")
            jobs.write_text(
                '[{"job_url": "https://jobs.example.com/role"}]', encoding="utf-8"
            )
            with patch.dict(__import__("os").environ, {"ATS_CAPTURE_FAST_PACE": "1"}), patch("ats_agent.job_research.socket.getaddrinfo", self._resolver), patch(
                "ats_agent.capture.shutil.which", return_value="/usr/bin/scrapling"
            ), patch(
                "ats_agent.capture.subprocess.run",
                side_effect=lambda command, **_kwargs: (
                    Path(command[4]).write_text(
                        "Python is required. Candidates must be authorized to work in India.",
                        encoding="utf-8",
                    ),
                    SimpleNamespace(returncode=0, stdout="", stderr=""),
                )[1],
            ):
                result = research_jobs(resume, jobs, root / "run")

            job = result["jobs"][0]
            self.assertEqual(job["status"], "eligibility_warning")
            self.assertEqual(job["lifecycle_status"], "proposal_draft")
            self.assertEqual(job["warnings"], ["eligibility_warning"])

    def test_stale_research_cannot_be_applied_without_refresh(self) -> None:
        with self.assertRaisesRegex(ValueError, "stale"):
            _validate_research_freshness({"research": {"captured_at": "2000-01-01T00:00:00+00:00"}})

    def test_concurrent_jobs_load_candidate_inputs_once(self) -> None:
        from ats_agent import job_research as research_module
        from ats_agent import workflow as workflow_module

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume, jobs = root / "resume.txt", root / "jobs.json"
            resume.write_text(
                "PROJECTS\n- Helped build workflow automation with 42 tests.\n",
                encoding="utf-8",
            )
            jobs.write_text(
                json.dumps([
                    {"id": f"role-{index}", "job_url": f"https://jobs.example.com/{index}"}
                    for index in range(4)
                ]),
                encoding="utf-8",
            )
            captures_ready = Barrier(4)
            source_loads = Barrier(4)
            count_lock = Lock()
            resume_loads = 0
            original_load = workflow_module.load

            def captured(url, destination, *, source_type, **_kwargs):
                destination.write_text(
                    "Python workflow automation is required for this role today.\n",
                    encoding="utf-8",
                )
                captures_ready.wait(timeout=1)
                return {
                    "url": url,
                    "path": str(destination),
                    "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                    "captured_at": "2026-09-06T00:00:00+00:00",
                    "method": "test",
                    "source_type": source_type,
                    "extraction_status": "captured",
                }

            def counted_load(path):
                nonlocal resume_loads
                if Path(path).resolve() == resume.resolve():
                    with count_lock:
                        resume_loads += 1
                    try:
                        source_loads.wait(timeout=0.25)
                    except BrokenBarrierError:
                        pass
                return original_load(path)

            with patch("ats_agent.job_research.socket.getaddrinfo", self._resolver), \
                 patch.object(research_module, "_capture", side_effect=captured), \
                 patch.object(workflow_module, "load", side_effect=counted_load):
                result = research_jobs(resume, jobs, root / "run")

            self.assertEqual(result["job_count"], 4)
            self.assertEqual(resume_loads, 1)

    def test_interrupted_run_resumes_verified_research_without_recapture_or_rewrite(self) -> None:
        from ats_agent import job_research as research_module

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume, jobs, out = root / "resume.txt", root / "jobs.json", root / "run"
            resume.write_text("SKILLS\nPython\n", encoding="utf-8")
            jobs.write_text(
                json.dumps([
                    {"id": "slow", "job_url": "https://jobs.example.com/slow"},
                    {"id": "healthy", "job_url": "https://jobs.example.com/healthy"},
                ]),
                encoding="utf-8",
            )
            healthy_recorded = Event()
            original_build = research_module.build_proposal
            original_checkpoint = research_module._write_research_manifest

            def interrupted_build(resume_path, job_path, **kwargs):
                if job_path.parent.name == "slow":
                    if not healthy_recorded.wait(2):
                        raise AssertionError("healthy result was not checkpointed before interruption")
                    raise RuntimeError("simulated interruption")
                return original_build(resume_path, job_path, **kwargs)

            def checkpoint(*args, **kwargs):
                original_checkpoint(*args, **kwargs)
                if any(item.get("id") == "healthy" for item in kwargs["results"]):
                    healthy_recorded.set()

            with patch.dict(__import__("os").environ, {"ATS_CAPTURE_FAST_PACE": "1"}), \
                 patch("ats_agent.job_research.socket.getaddrinfo", self._resolver), \
                 patch("ats_agent.capture.shutil.which", return_value="/usr/bin/scrapling"), \
                 patch("ats_agent.capture.subprocess.run", side_effect=self._scrapling), \
                 patch("ats_agent.job_research.build_proposal", side_effect=interrupted_build), \
                 patch("ats_agent.job_research._write_research_manifest", side_effect=checkpoint):
                with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                    research_jobs(resume, jobs, out)

            interrupted = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(interrupted["status"], "in_progress")
            self.assertEqual([item["id"] for item in interrupted["jobs"]], ["healthy"])
            healthy_proposal = Path(interrupted["jobs"][0]["proposal"])
            healthy_bytes = healthy_proposal.read_bytes()

            def resumed_build(resume_path, job_path, **kwargs):
                if job_path.parent.name == "healthy":
                    raise AssertionError("verified healthy proposal was rebuilt")
                return original_build(resume_path, job_path, **kwargs)

            with patch("ats_agent.job_research.socket.getaddrinfo", self._resolver), \
                 patch("ats_agent.capture.capture_url", side_effect=AssertionError("recaptured")), \
                 patch("ats_agent.job_research.build_proposal", side_effect=resumed_build):
                resumed = research_jobs(resume, jobs, out)

            self.assertEqual(resumed["resumed_jobs"], 1)
            self.assertEqual([item["id"] for item in resumed["jobs"]], ["slow", "healthy"])
            self.assertEqual(healthy_proposal.read_bytes(), healthy_bytes)
            self.assertEqual(json.loads((out / "manifest.json").read_text())["status"], "draft")

    def test_corrupt_resumable_draft_is_visible_and_never_silently_rebuilt(self) -> None:
        from ats_agent import job_research as research_module

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume, jobs, out = root / "resume.txt", root / "jobs.json", root / "run"
            resume.write_text("SKILLS\nPython\n", encoding="utf-8")
            jobs.write_text(
                json.dumps([
                    {
                        "id": "corrupt",
                        "company": "Example Co",
                        "role": "Data Analyst",
                        "job_url": "https://jobs.example.com/corrupt",
                    }
                ]),
                encoding="utf-8",
            )
            with patch.dict(__import__("os").environ, {"ATS_CAPTURE_FAST_PACE": "1"}), \
                 patch("ats_agent.job_research.socket.getaddrinfo", self._resolver), \
                 patch("ats_agent.capture.shutil.which", return_value="/usr/bin/scrapling"), \
                 patch("ats_agent.capture.subprocess.run", side_effect=self._scrapling):
                original = research_jobs(resume, jobs, out)

            Path(original["jobs"][0]["proposal"]).write_text("{}", encoding="utf-8")
            with patch("ats_agent.job_research.socket.getaddrinfo", self._resolver), \
                 patch("ats_agent.capture.capture_url", side_effect=AssertionError("recaptured")), \
                 patch.object(research_module, "build_proposal", side_effect=AssertionError("rebuilt")):
                resumed = research_jobs(resume, jobs, out)

            row = resumed["jobs"][0]
            self.assertEqual(row["status"], "blocked_recovery")
            self.assertEqual(row["company"], "Example Co")
            self.assertEqual(row["role"], "Data Analyst")
            self.assertEqual(row["job_url"], "https://jobs.example.com/corrupt")
            self.assertEqual(resumed["resumed_jobs"], 0)

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
                selected_job_ids=None,
                constraint_text=None,
                include_internships=False,
            )
