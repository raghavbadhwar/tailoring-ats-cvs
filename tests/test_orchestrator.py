"""Tests for the tailor orchestrator and ATS/intake layers."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

from ats_agent.intake import classify_text, parse_url_lines  # noqa: E402
from ats_agent.boards import detect_board, html_to_text  # noqa: E402


class IntakeTests(unittest.TestCase):
    def test_classify_all_shapes(self):
        self.assertEqual(classify_text('{"jobs": [{"id": "a", "job_url": "https://x"}]}'), "json_export")
        self.assertEqual(
            classify_text("- [ ] https://boards.greenhouse.io/acme | Acme | Intern"),
            "career_ops",
        )
        self.assertEqual(
            classify_text("https://jobs.lever.co/ramp\nhttps://jobs.ashbyhq.com/openai"),
            "url_list",
        )
        self.assertEqual(classify_text("We need SQL skills.\nBachelor's required."), "jd_text")

    def test_url_lines_parse_company_and_role(self):
        entries = parse_url_lines(
            "# my list\n"
            "https://jobs.lever.co/ramp | Ramp | SWE Intern\n"
            "https://boards.greenhouse.io/stripe\n"
        )
        self.assertEqual(entries[0], ("https://jobs.lever.co/ramp", "Ramp", "SWE Intern"))
        self.assertEqual(entries[1], ("https://boards.greenhouse.io/stripe", "", ""))

    def test_detect_board_patterns(self):
        self.assertEqual(detect_board("https://boards.greenhouse.io/stripe/jobs/9"), ("greenhouse", "stripe"))
        self.assertEqual(detect_board("https://jobs.eu.lever.co/acme"), ("lever", "acme"))
        self.assertIsNone(detect_board("https://careers.example.com/job"))

    def test_html_to_text_strips_script(self):
        text = html_to_text("<p>Build <b>dashboards</b></p><script>evil()</script>")
        self.assertIn("Build dashboards", text.replace("\n", " "))
        self.assertNotIn("evil()", text)


class GreenhouseFixtureTests(unittest.TestCase):
    """Normalize vendor payload shapes using captured real structures."""

    def test_greenhouse_shape(self):
        from ats_agent.boards import fetch_greenhouse
        payload = {
            "jobs": [{
                "id": 127817,
                "title": "Software Engineer, Intern",
                "absolute_url": "https://boards.greenhouse.io/vaulttec/jobs/127817",
                "location": {"name": "NYC"},
                "content": "&lt;p&gt;Build payment dashboards with SQL.&lt;/p&gt;" * 3,
            }]
        }
        with patch("ats_agent.boards._polite_get_json", return_value=payload):
            jobs = fetch_greenhouse("vaulttec")
        self.assertEqual(jobs[0]["provider"], "greenhouse")
        self.assertEqual(jobs[0]["role"], "Software Engineer, Intern")
        self.assertIn("dashboards", jobs[0]["description"])

    def test_lever_shape(self):
        from ats_agent.boards import fetch_lever
        payload = [{
            "id": "abc",
            "text": "Data Analyst Intern",
            "hostedUrl": "https://jobs.lever.co/ramp/abc",
            "categories": {"location": "Remote"},
            "descriptionPlain": "<p>Strong SQL required</p>" * 3,
        }]
        with patch("ats_agent.boards._polite_get_json", return_value=payload):
            jobs = fetch_lever("ramp")
        self.assertEqual(jobs[0]["provider"], "lever")
        self.assertEqual(jobs[0]["role"], "Data Analyst Intern")


class OrchestratorE2ETests(unittest.TestCase):
    """Full tailor runs against repository example fixtures."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run_dir = Path(self.tmp.name) / "run"
        self.approvals = Path(self.tmp.name) / "approvals.json"
        self.approvals.write_text(json.dumps({"*": ["*"]}), encoding="utf-8")
        self.writer_lines: list[str] = []

    def _writer(self, text: str) -> None:
        self.writer_lines.append(text)

    def _run(self, **kwargs):
        from ats_agent.orchestrator import tailor

        return tailor(
            EXAMPLES / "sample_resume.txt",
            str(EXAMPLES / "sample_job.md"),
            candidate_id="qa-candidate",
            run_dir=self.run_dir,
            evidence_paths=[EXAMPLES / "sample_project_bank.md"],
            approve_from=self.approvals,
            writer=self._writer,
            verify_live=False,
            **kwargs,
        )

    def test_full_agent_run_tailors_and_validates(self):
        payload = self._run()
        self.assertEqual(payload["status"], "completed")
        outcome = payload["outcomes"][0]
        self.assertEqual(outcome["status"], "tailored")
        self.assertTrue(Path(outcome["output_document"]).exists())

    def test_idempotent_rerun_short_circuits(self):
        self._run()
        second = self._run()
        outcome = second["outcomes"][0]
        self.assertEqual(outcome["status"], "already_tailored")

    def test_journal_resume_after_crash(self):
        first = self._run()
        output = Path(first["outcomes"][0]["output_document"])
        output.unlink()
        journal_path = self.run_dir / "journal.json"
        data = json.loads(journal_path.read_text(encoding="utf-8"))
        entry = next(iter(data["roles"].values()))
        entry["stage"] = "approved"  # simulate crash right after approval write
        entry.pop("output_document", None)
        journal_path.write_text(json.dumps(data), encoding="utf-8")
        resumed = self._run()
        outcome = resumed["outcomes"][0]
        self.assertEqual(outcome["status"], "tailored")
        self.assertTrue(Path(outcome["output_document"]).exists())

    def test_mode_conflict_is_rejected(self):
        from ats_agent.orchestrator import TailorBlocked
        with self.assertRaisesRegex(TailorBlocked, "either --interactive"):
            self._run(interactive=True)

    def test_interactive_defaults_token(self):
        from ats_agent.orchestrator import tailor

        payload = tailor(
            EXAMPLES / "sample_resume.txt",
            str(EXAMPLES / "sample_job.md"),
            candidate_id="qa-candidate",
            run_dir=self.run_dir,
            evidence_paths=[EXAMPLES / "sample_project_bank.md"],
            interactive=True,
            reader=lambda _prompt="": "defaults\n",
            writer=self._writer,
            verify_live=False,
        )
        self.assertEqual(payload["outcomes"][0]["status"], "tailored")

    def test_delivery_card_is_outcome_first_and_plain(self):
        payload = self._run()
        card = payload["card"]
        first_content_line = card.splitlines()[1]
        self.assertTrue(first_content_line.startswith(("✔", "✖")), first_content_line)
        for jargon in ("digest", "provenance", "liveness"):
            self.assertNotIn(jargon, card.lower())


class OrchestratorLivenessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_dead_posting_blocks_apply(self):
        from ats_agent.capture import CaptureError
        from ats_agent.orchestrator import _liveness_check

        capture = {"url": "https://example.com/posting", "sha256": "old",
                   "path": str(Path(self.tmp.name) / "orig.txt")}
        Path(capture["path"]).write_text("original posting text " * 10)
        with patch("ats_agent.orchestrator.capture_url",
                   side_effect=CaptureError("HTTP 404 for https://example.com/posting")):
            verdict = _liveness_check(capture, Path(self.tmp.name))
        self.assertEqual(verdict, "dead")

    def test_changed_posting_detected_by_overlap(self):
        from ats_agent.orchestrator import _liveness_check

        capture = {"url": "https://example.com/posting", "sha256": "old",
                   "path": str(Path(self.tmp.name) / "orig.txt")}
        original = "sql power bi dashboards reporting internship " * 5
        Path(capture["path"]).write_text(original)
        fresh = original + " updated salary section"
        def fake_capture(url, dest, *, source_type):
            dest.write_text(fresh, encoding="utf-8")
            import hashlib
            return {"path": str(dest), "sha256": hashlib.sha256(fresh.encode()).hexdigest()}
        with patch("ats_agent.orchestrator.capture_url", side_effect=fake_capture):
            verdict = _liveness_check(capture, Path(self.tmp.name))
        self.assertEqual(verdict, "changed")

    def test_infra_failure_warns_only(self):
        from ats_agent.capture import CaptureError
        from ats_agent.orchestrator import _liveness_check

        capture = {"url": "https://example.com/posting", "sha256": "x",
                   "path": str(Path(self.tmp.name) / "o.txt")}
        Path(capture["path"]).write_text("text")
        with patch("ats_agent.orchestrator.capture_url",
                   side_effect=CaptureError("connection reset by peer")):
            verdict = _liveness_check(capture, Path(self.tmp.name))
        self.assertEqual(verdict, "infra")


if __name__ == "__main__":
    unittest.main()
