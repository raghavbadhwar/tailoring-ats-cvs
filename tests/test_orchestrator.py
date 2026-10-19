"""Tests for the tailor orchestrator and ATS/intake layers."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import socket
from datetime import datetime, timezone


def setUpModule():
    dns = patch("ats_agent.capture.socket.getaddrinfo", return_value=[
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
    ])
    dns.start()
    unittest.addModuleCleanup(dns.stop)

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

        options = {
            "interactive": True,
            "reader": lambda _prompt="": "C1:balanced\n",
            "writer": self._writer,
            "verify_live": False,
        }
        options.update(kwargs)
        return tailor(
            EXAMPLES / "sample_resume.txt",
            str(EXAMPLES / "sample_job.md"),
            candidate_id="qa-candidate",
            run_dir=self.run_dir,
            evidence_paths=[EXAMPLES / "sample_project_bank.md"],
            **options,
        )

    def test_full_agent_run_tailors_and_validates(self):
        payload = self._run()
        self.assertEqual(payload["status"], "completed")
        outcome = payload["outcomes"][0]
        self.assertEqual(outcome["status"], "tailored")
        self.assertTrue(Path(outcome["output_document"]).exists())

    def test_noninteractive_run_stops_at_persisted_proposal(self):
        from ats_agent.orchestrator import tailor

        payload = tailor(
            EXAMPLES / "sample_resume.txt",
            str(EXAMPLES / "sample_job.md"),
            candidate_id="qa-candidate",
            run_dir=self.run_dir,
            evidence_paths=[EXAMPLES / "sample_project_bank.md"],
            writer=self._writer,
            verify_live=False,
        )
        outcome = payload["outcomes"][0]
        self.assertEqual(payload["status"], "awaiting_approval")
        self.assertEqual(outcome["status"], "awaiting_approval")
        self.assertTrue(Path(outcome["proposal_path"]).is_file())
        self.assertIsNone(outcome["output_document"])

    def test_persisted_manifest_resumes_exact_proposal(self):
        from ats_agent.orchestrator import tailor
        from ats_agent.review import build_approval_manifest

        prepared = tailor(
            EXAMPLES / "sample_resume.txt",
            str(EXAMPLES / "sample_job.md"),
            candidate_id="qa-candidate",
            run_dir=self.run_dir,
            evidence_paths=[EXAMPLES / "sample_project_bank.md"],
            writer=self._writer,
            verify_live=False,
        )
        proposal_path = Path(prepared["outcomes"][0]["proposal_path"])
        proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
        change = next(item for item in proposal["changes"] if item["supported"])
        manifest_path = proposal_path.with_name("approval.json")
        manifest_path.write_text(
            json.dumps(
                build_approval_manifest(
                    proposal,
                    proposal_filename="proposal.json",
                    selections=[(change["id"], change["default_variant"])],
                    output_document="tailored.txt",
                )
            ),
            encoding="utf-8",
        )
        resumed = tailor(
            EXAMPLES / "sample_resume.txt",
            str(EXAMPLES / "sample_job.md"),
            candidate_id="qa-candidate",
            run_dir=self.run_dir,
            evidence_paths=[EXAMPLES / "sample_project_bank.md"],
            approve_from=manifest_path,
            writer=self._writer,
            verify_live=False,
        )
        self.assertEqual(resumed["outcomes"][0]["status"], "tailored")

        proposal["changes"][0]["reason"] = "changed after review"
        proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
        blocked = tailor(
            EXAMPLES / "sample_resume.txt",
            str(EXAMPLES / "sample_job.md"),
            candidate_id="qa-candidate",
            run_dir=self.run_dir,
            evidence_paths=[EXAMPLES / "sample_project_bank.md"],
            approve_from=manifest_path,
            writer=self._writer,
            verify_live=False,
        )
        self.assertEqual(blocked["outcomes"][0]["status"], "blocked_recovery")

    def test_transient_interpreter_path_does_not_invalidate_approval_but_engine_change_does(self):
        from ats_agent.orchestrator import TailorBlocked, tailor
        from ats_agent.review import build_approval_manifest

        def doctor(interpreter: str, source_sha256: str) -> dict[str, object]:
            return {
                "status": "ready",
                "package": {"name": "tailoring-ats-cvs", "version": "1.0.0b4"},
                "python": "3.14.6",
                "runtime": {
                    "interpreter": interpreter,
                    "engine_path": str((ROOT / "src/ats_agent").resolve()),
                    "source_sha256": source_sha256,
                },
                "optional_dependencies": {"pypdf": True, "python_docx": True},
            }

        first = doctor("/tmp/ephemeral-a/bin/python", "a" * 64)
        second = doctor("/tmp/ephemeral-b/bin/python", "a" * 64)
        changed_engine = doctor("/tmp/ephemeral-c/bin/python", "b" * 64)
        options = {
            "candidate_id": "qa-candidate",
            "run_dir": self.run_dir,
            "evidence_paths": [EXAMPLES / "sample_project_bank.md"],
            "writer": self._writer,
            "verify_live": False,
        }
        with patch("ats_agent.orchestrator._doctor", return_value=first):
            prepared = tailor(EXAMPLES / "sample_resume.txt", str(EXAMPLES / "sample_job.md"), **options)
        proposal_path = Path(prepared["outcomes"][0]["proposal_path"])
        proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
        change = next(item for item in proposal["changes"] if item["supported"])
        approval_path = proposal_path.with_name("approval.json")
        approval_path.write_text(
            json.dumps(
                build_approval_manifest(
                    proposal,
                    proposal_filename="proposal.json",
                    selections=[(change["id"], change["default_variant"])],
                    output_document="tailored.txt",
                )
            ),
            encoding="utf-8",
        )

        with patch("ats_agent.orchestrator._doctor", return_value=second):
            resumed = tailor(
                EXAMPLES / "sample_resume.txt",
                str(EXAMPLES / "sample_job.md"),
                approve_from=approval_path,
                **options,
            )
        self.assertEqual(resumed["outcomes"][0]["status"], "tailored")

        with patch("ats_agent.orchestrator._doctor", return_value=changed_engine):
            with self.assertRaisesRegex(TailorBlocked, "inputs or engine changed"):
                tailor(
                    EXAMPLES / "sample_resume.txt",
                    str(EXAMPLES / "sample_job.md"),
                    approve_from=approval_path,
                    **options,
                )

    def test_legacy_selection_map_is_rejected(self):
        from ats_agent.orchestrator import TailorBlocked, tailor

        self.approvals.write_text(json.dumps({"*": ["*"]}), encoding="utf-8")
        with self.assertRaisesRegex(TailorBlocked, "legacy token selection maps"):
            tailor(
                EXAMPLES / "sample_resume.txt",
                str(EXAMPLES / "sample_job.md"),
                candidate_id="qa-candidate",
                run_dir=self.run_dir,
                approve_from=self.approvals,
                writer=self._writer,
                verify_live=False,
            )

    def test_idempotent_rerun_short_circuits(self):
        self._run()
        second = self._run()
        outcome = second["outcomes"][0]
        self.assertEqual(outcome["status"], "already_tailored")

    def test_company_context_remains_separate_from_candidate_evidence(self):
        context = Path(self.tmp.name) / "company-context.md"
        context.write_text(
            "Acme calls its internal reporting system Starbridge.",
            encoding="utf-8",
        )

        payload = self._run(context_paths=[context])
        proposal = json.loads(
            Path(payload["outcomes"][0]["proposal_path"]).read_text(encoding="utf-8")
        )

        self.assertEqual(proposal["company_context"], str(context.resolve()))
        self.assertEqual(
            proposal["evidence_files"],
            [str((EXAMPLES / "sample_project_bank.md").resolve())],
        )
        kinds = [artifact["kind"] for artifact in proposal["artifacts"]]
        self.assertEqual(kinds.count("company_context"), 1)
        self.assertEqual(kinds.count("candidate_evidence"), 1)
        evidence_sources = {
            item["source_file"] for item in proposal["evidence_ledger"]
        }
        self.assertNotIn(str(context.resolve()), evidence_sources)
        self.assertIn("company_alignment", proposal["report"]["agents"])

    def test_changed_company_context_invalidates_idempotency_digest(self):
        context = Path(self.tmp.name) / "company-context.md"
        context.write_text("Acme builds reporting tools.", encoding="utf-8")
        self._run(context_paths=[context])
        context.write_text("Acme builds fraud-detection tools.", encoding="utf-8")

        with patch(
            "ats_agent.orchestrator.build_proposal",
            side_effect=RuntimeError("proposal rebuilt"),
        ) as build:
            with self.assertRaisesRegex(RuntimeError, "proposal rebuilt"):
                self._run(context_paths=[context])
        build.assert_called_once()

    def test_company_context_path_invalidates_idempotency_digest(self):
        first = Path(self.tmp.name) / "company-context-a.md"
        second = Path(self.tmp.name) / "company-context-b.md"
        for path in (first, second):
            path.write_text("Acme builds reporting tools.", encoding="utf-8")
        self._run(context_paths=[first])

        with patch(
            "ats_agent.orchestrator.build_proposal",
            side_effect=RuntimeError("proposal rebuilt"),
        ) as build:
            with self.assertRaisesRegex(RuntimeError, "proposal rebuilt"):
                self._run(context_paths=[second])
        build.assert_called_once()

    def test_rewrite_provider_invalidates_idempotency_digest(self):
        from ats_agent.providers import CommandRewriteProvider

        script = (
            "import json,sys; c=json.load(sys.stdin); "
            "print(json.dumps([{'id':'conservative','text':c['original_text']}]))"
        )
        first = CommandRewriteProvider((sys.executable, "-c", script))
        second = CommandRewriteProvider((sys.executable, "-c", script + " "))
        self._run(
            rewrite_provider=first,
            reader=lambda _prompt="": "C1:conservative\n",
        )
        with patch(
            "ats_agent.orchestrator.build_proposal",
            side_effect=RuntimeError("proposal rebuilt"),
        ) as build:
            with self.assertRaisesRegex(RuntimeError, "proposal rebuilt"):
                self._run(
                    rewrite_provider=second,
                    reader=lambda _prompt="": "C1:conservative\n",
                )
        build.assert_called_once()

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
            self._run(approve_from=self.approvals)

    def test_interactive_blanket_token_is_rejected(self):
        payload = self._run(reader=lambda _prompt="": "defaults\n")
        self.assertEqual(payload["outcomes"][0]["status"], "blocked_recovery")
        self.assertIn("blanket approvals", payload["outcomes"][0]["message"])
        self.assertFalse(list(self.run_dir.rglob("*.docx")))

    def test_selection_eligibility_uses_supported_flag(self):
        from ats_agent.orchestrator import _normalize_selections

        proposal = {
            "changes": [
                {
                    "id": "C1",
                    "kind": "language-rewrite",
                    "supported": True,
                    "default_variant": "balanced",
                    "variants": [{"id": "balanced"}],
                },
                {
                    "id": "C2",
                    "kind": "surface-evidence",
                    "supported": False,
                    "default_variant": "balanced",
                    "variants": [{"id": "balanced"}],
                },
            ]
        }

        from ats_agent.orchestrator import TailorBlocked

        with self.assertRaisesRegex(TailorBlocked, "blanket approvals"):
            _normalize_selections(["*"], proposal, self._writer)
        with self.assertRaisesRegex(TailorBlocked, "explicit variant"):
            _normalize_selections(["C1"], proposal, self._writer)
        self.assertEqual(
            _normalize_selections(["C1:balanced"], proposal, self._writer)[0],
            ["C1:balanced"],
        )

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
        with patch("ats_agent.capture.capture_url",
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
        with patch("ats_agent.capture.capture_url", side_effect=fake_capture):
            verdict = _liveness_check(capture, Path(self.tmp.name))
        self.assertEqual(verdict, "changed")

    def test_infra_failure_warns_only(self):
        from ats_agent.capture import CaptureError
        from ats_agent.orchestrator import _liveness_check

        capture = {"url": "https://example.com/posting", "sha256": "x",
                   "path": str(Path(self.tmp.name) / "o.txt")}
        Path(capture["path"]).write_text("text")
        with patch("ats_agent.capture.capture_url",
                   side_effect=CaptureError("connection reset by peer")):
            verdict = _liveness_check(capture, Path(self.tmp.name))
        self.assertEqual(verdict, "infra")



class OrchestratorCollectionTests(unittest.TestCase):
    """_collect_roles across intake kinds with network fully mocked."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run_dir = Path(self.tmp.name)

    def test_url_list_collects_board_and_posting_roles(self):
        from ats_agent.orchestrator import _collect_roles
        source = {
            "kind": "url_list",
            "entries": [
                ("https://boards.greenhouse.io/acme", "Acme", "Eng Intern"),
                ("https://example.org/posting/1", "", ""),
            ],
        }
        board_job = {"company": "acme", "role": "Eng Intern",
                     "job_url": "https://jobs.greenhouse.io/x",
                     "description": "Build things", "provider": "greenhouse",
                     "fetched_at": "now"}
        capture_meta = {"url": "https://example.org/posting/1",
                        "path": str(self.run_dir / "c.txt"), "sha256": "s",
                        "captured_at": datetime.now(timezone.utc).isoformat()}
        with patch("ats_agent.orchestrator.fetch_board_url", return_value=[board_job]), \
             patch("ats_agent.capture.capture_url", side_effect=lambda u, d, **k: (
                 d.parent.mkdir(parents=True, exist_ok=True),
                 d.write_text("posting body text here", encoding="utf-8"),
                 capture_meta)[2]):
            roles = _collect_roles(source, self.run_dir, max_urls=5)
        self.assertEqual(len(roles), 2)
        self.assertEqual(roles[0].job_url, "https://jobs.greenhouse.io/x")
        self.assertTrue(roles[1].capture)

    def test_board_url_prefers_exact_match(self):
        from ats_agent.orchestrator import _collect_roles
        jobs = [
            {"company": "acme", "role": "Other Role", "job_url": "https://jobs.lever.co/acme/1",
             "description": "a" * 40, "provider": "greenhouse", "fetched_at": "now"},
            {"company": "acme", "role": "Target Intern", "job_url": "https://jobs.lever.co/acme/2",
             "description": "b" * 40, "provider": "greenhouse", "fetched_at": "now"},
        ]
        source = {"kind": "board_url", "url": "https://jobs.lever.co/acme/2", "board": ("greenhouse", "acme")}
        with patch("ats_agent.orchestrator.fetch_board_url", return_value=jobs):
            roles = _collect_roles(source, self.run_dir, 5)
        self.assertEqual(roles[0].title, "Target Intern")

    def test_missing_board_posting_is_retained_as_a_blocked_role(self):
        from ats_agent.orchestrator import _collect_roles

        source = {
            "kind": "board_url",
            "url": "https://boards.greenhouse.io/acme/jobs/missing",
            "board": ("greenhouse", "acme"),
        }
        with patch("ats_agent.orchestrator.fetch_board_url", return_value=[]):
            roles = _collect_roles(source, self.run_dir, 5)
        self.assertEqual(len(roles), 1)
        self.assertIn("not found", roles[0].capture_error or "")

    def test_capture_failure_does_not_drop_another_url(self):
        from ats_agent.capture import CaptureError
        from ats_agent.orchestrator import _collect_roles

        source = {
            "kind": "url_list",
            "entries": [
                ("https://example.org/one", "Acme", "One"),
                ("https://example.org/two", "Acme", "Two"),
            ],
        }

        def capture(url, destination, *, source_type):
            if url.endswith("two"):
                raise CaptureError("blocked test capture")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text("public role text", encoding="utf-8")
            return {"url": url, "path": str(destination), "sha256": "a" * 64}

        with patch("ats_agent.capture.capture_url", side_effect=capture):
            roles = _collect_roles(source, self.run_dir, 5)
        self.assertEqual([role.title for role in roles], ["One", "Two"])
        self.assertIsNone(roles[0].capture_error)
        self.assertIn("blocked test capture", roles[1].capture_error or "")

    def test_interactive_quit_ends_session(self):
        from ats_agent.orchestrator import tailor
        answers = iter(["quit"])
        payload = tailor(
            EXAMPLES / "sample_resume.txt",
            str(EXAMPLES / "sample_job.md"),
            candidate_id="qa",
            run_dir=Path(self.tmp.name) / "run",
            interactive=True,
            reader=lambda _p="": next(answers),
            writer=lambda _t: None,
            verify_live=False,
        )
        self.assertEqual(payload["outcomes"][0]["status"], "skipped")



class GapClosureTests(unittest.TestCase):
    """Final coverage: ashby shape, resolve_source network kinds, dead-block."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_ashby_shape_normalizes(self):
        from ats_agent.boards import fetch_ashby
        payload = {"jobs": [{
            "id": 9, "title": "Research Intern",
            "jobUrl": "https://jobs.ashbyhq.com/acme/9",
            "location": "Remote",
            "descriptionHtml": "<p>Market research support</p>" * 3,
        }]}
        with patch("ats_agent.boards._polite_get_json", return_value=payload):
            jobs = fetch_ashby("acme")
        self.assertEqual(jobs[0]["provider"], "ashby")
        self.assertEqual(jobs[0]["role"], "Research Intern")

    def test_resolve_source_network_kinds(self):
        from ats_agent.intake import resolve_source
        self.assertEqual(resolve_source("https://boards.greenhouse.io/acme")["kind"], "board_url")
        self.assertEqual(resolve_source("https://example.org/posting")["kind"], "posting_url")

    def test_dead_posting_blocks_apply_in_full_run(self):
        from ats_agent.orchestrator import tailor

        def fake_capture(url, destination, *, source_type):
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text((EXAMPLES / "sample_job.md").read_text(encoding="utf-8"), encoding="utf-8")
            import hashlib
            return {"url": url, "path": str(destination),
                    "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                    "captured_at": datetime.now(timezone.utc).isoformat(), "method": "scrapling_public_https",
                    "source_type": source_type, "extraction_status": "captured"}

        with patch("ats_agent.capture.capture_url", side_effect=fake_capture), \
             patch("ats_agent.orchestrator._liveness_check", return_value="dead"):
            payload = tailor(
                EXAMPLES / "sample_resume.txt",
                "https://example.org/dead-posting",
                candidate_id="qa",
                run_dir=Path(self.tmp.name) / "run",
                evidence_paths=[EXAMPLES / "sample_project_bank.md"],
                interactive=True,
                reader=lambda _prompt="": "C1:balanced\n",
                writer=lambda _t: None,
                verify_live=True,
            )
        self.assertEqual(payload["outcomes"][0]["status"], "blocked_liveness")


class ForceAndChangedAcceptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _fake_capture(self):
        def fake(url, destination, *, source_type):
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text((EXAMPLES / "sample_job.md").read_text(encoding="utf-8"),
                                   encoding="utf-8")
            import hashlib
            body = destination.read_text(encoding="utf-8")
            return {"url": url, "path": str(destination),
                    "sha256": hashlib.sha256(body.encode()).hexdigest(),
                    "captured_at": datetime.now(timezone.utc).isoformat(), "method": "scrapling_public_https",
                    "source_type": source_type, "extraction_status": "captured"}
        return fake

    def test_changed_posting_requires_a_fresh_proposal(self):
        from ats_agent.orchestrator import tailor

        common = dict(
            candidate_id="qa",
            evidence_paths=[EXAMPLES / "sample_project_bank.md"],
            interactive=True,
            reader=lambda _prompt="": "C1:balanced\n",
            writer=lambda _t: None,
            verify_live=True,
        )
        with patch("ats_agent.capture.capture_url", side_effect=self._fake_capture()), \
             patch("ats_agent.orchestrator._liveness_check", return_value="same"):
            first = tailor(EXAMPLES / "sample_resume.txt",
                           "https://example.org/p", run_dir=Path(self.tmp.name) / "run",
                           **common)
        self.assertEqual(first["outcomes"][0]["status"], "tailored")

        with patch("ats_agent.capture.capture_url", side_effect=self._fake_capture()), \
             patch("ats_agent.orchestrator._liveness_check", return_value="changed"):
            second = tailor(
                EXAMPLES / "sample_resume.txt",
                "https://example.org/p",
                run_dir=Path(self.tmp.name) / "run",
                candidate_id="qa",
                evidence_paths=[EXAMPLES / "sample_project_bank.md"],
                interactive=True,
                writer=lambda _t: None,
                verify_live=True,
                force=True,
                reader=lambda _prompt="": "C1:balanced\n",
            )
        outcome = second["outcomes"][0]
        self.assertEqual(outcome["status"], "blocked_liveness")


class ChangedPostingDeclineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_changed_posting_declined_in_interactive_mode(self):
        from ats_agent.orchestrator import tailor

        def fake_capture(url, destination, *, source_type):
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text((EXAMPLES / "sample_job.md").read_text(encoding="utf-8"),
                                   encoding="utf-8")
            import hashlib
            body = destination.read_text(encoding="utf-8")
            return {"url": url, "path": str(destination),
                    "sha256": hashlib.sha256(body.encode()).hexdigest(),
                    "captured_at": datetime.now(timezone.utc).isoformat(), "method": "scrapling_public_https",
                    "source_type": source_type, "extraction_status": "captured"}

        with patch("ats_agent.capture.capture_url", side_effect=fake_capture), \
             patch("ats_agent.orchestrator._liveness_check", return_value="changed"):
            payload = tailor(
                EXAMPLES / "sample_resume.txt",
                "https://example.org/changed-posting",
                candidate_id="qa",
                run_dir=Path(self.tmp.name) / "run",
                evidence_paths=[EXAMPLES / "sample_project_bank.md"],
                interactive=True,
                reader=lambda _prompt="": "C1:balanced\n",
                writer=lambda _t: None,
                verify_live=True,
            )
        outcome = payload["outcomes"][0]
        self.assertEqual(outcome["status"], "blocked_liveness")
