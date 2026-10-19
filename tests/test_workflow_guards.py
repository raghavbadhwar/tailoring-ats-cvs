from __future__ import annotations

import json
import tempfile
import unittest
import hashlib
import socket
from threading import Event
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ats_agent.requirements import enforce_hard_gate_policy
from ats_agent.orchestrator import TailorBlocked, _approval_for_role, _approval_paths
from ats_agent.workflow import (
    _default_output,
    _materialize_change,
    _resolve_from,
    _selections,
    _validate_output_path,
    _validate_research_freshness,
)

ROOT = Path(__file__).resolve().parents[1]


class UpgradeIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        dns = patch("ats_agent.capture.socket.getaddrinfo", return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        ])
        dns.start()
        self.addCleanup(dns.stop)

    @staticmethod
    def capture(url, destination, *, source_type):
        body = (ROOT / "examples/sample_job.md").read_text()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(body)
        return {"url": url, "path": str(destination), "sha256": hashlib.sha256(body.encode()).hexdigest(),
                "captured_at": datetime.now(timezone.utc).isoformat(), "source_type": source_type,
                "method": "scrapling_public_https", "extraction_status": "captured"}

    def run_tailor(self, source, **options):
        from ats_agent.orchestrator import tailor
        return tailor(ROOT / "examples/sample_resume.txt", source,
                      candidate_id="test-upgrade", run_dir=self.root / "run",
                      evidence_paths=[ROOT / "examples/sample_project_bank.md"],
                      writer=lambda _: None, **options)

    def test_tailor_rejects_a_run_directory_that_contains_the_source_cv(self):
        from ats_agent.orchestrator import TailorBlocked, tailor

        run_dir = self.root / "run"
        run_dir.mkdir()
        resume = run_dir / "resume.txt"
        job = self.root / "job.txt"
        resume.write_text(
            "PROJECTS\n- Helped build automated workflows with 42 tests.\n",
            encoding="utf-8",
        )
        job.write_text("Workflow automation is required.\n", encoding="utf-8")
        original = resume.read_bytes()

        with self.assertRaisesRegex(TailorBlocked, "run directory must not contain"):
            tailor(resume, str(job), candidate_id="candidate", run_dir=run_dir)

        self.assertEqual(resume.read_bytes(), original)
        self.assertFalse((run_dir / "journal.json").exists())

    def test_legacy_import_and_invalid_rows_survive_convenience_intake(self):
        from ats_agent.orchestrator import _collect_roles
        source = {"kind": "json_export", "payload": {"seen": {
            "good": {"url": "https://example.com/good", "title": "Analyst", "portal": "test"},
            "invalid": {"url": "http://example.com/unsafe"},
            "expired": {"url": "https://example.com/expired", "status": "expired"},
        }}}
        with patch("ats_agent.capture.capture_url", side_effect=self.capture) as capture:
            roles = _collect_roles(source, self.root, 20)
        self.assertEqual(len(roles), 3)
        self.assertEqual(capture.call_count, 1)
        self.assertEqual(roles[0].title, "Analyst")
        self.assertEqual(roles[1].metadata["source_status"], "blocked_import")
        self.assertEqual(roles[2].metadata["source_status"], "expired")

    def test_exact_board_urls_share_one_feed_and_keep_stable_ids(self):
        from ats_agent.orchestrator import _collect_roles
        jobs = [{"id": f"role-{i}", "job_url": f"https://jobs.lever.co/acme/{i}",
                 "role": "Same title", "company": "Acme", "description": "SQL analysis required",
                 "provider": "lever", "fetched_at": datetime.now(timezone.utc).isoformat()}
                for i in range(3)]
        entries = [(jobs[i]["job_url"], "Acme", "Same title") for i in (2, 1)]
        with patch("ats_agent.orchestrator.fetch_board_url", return_value=jobs) as feed:
            roles = _collect_roles({"kind": "url_list", "entries": entries}, self.root, 20)
        self.assertEqual(feed.call_count, 1)
        self.assertEqual([r.job_url for r in roles], [e[0] for e in entries])
        with patch("ats_agent.orchestrator.fetch_board_url", return_value=jobs):
            reverse = _collect_roles({"kind": "url_list", "entries": entries[::-1]}, self.root, 20)
            limited = _collect_roles({"kind": "url_list", "entries": entries}, self.root, 1)
        self.assertEqual([r.role_id for r in roles], [r.role_id for r in reverse][::-1])
        self.assertEqual(limited[1].metadata["source_status"], "imported")

    def test_healthy_proposal_is_persisted_before_slow_capture_finishes(self):
        release = Event()
        def capture(url, destination, *, source_type):
            if url.endswith("slow"):
                self.assertTrue(release.wait(2), "healthy proposal was blocked behind slow capture")
            return self.capture(url, destination, source_type=source_type)

        from ats_agent.orchestrator import tailor
        def progress(_):
            if list((self.root / "run").glob("*/proposal.json")):
                release.set()

        source = json.dumps([{"job_url": f"https://example.com/{name}", "id": name}
                             for name in ("slow", "healthy")])
        with patch("ats_agent.capture.capture_url", side_effect=capture):
            result = tailor(ROOT / "examples/sample_resume.txt", source,
                            candidate_id="test", run_dir=self.root / "run", writer=progress)
        self.assertTrue(release.is_set())
        self.assertEqual([item["role_id"] for item in result["outcomes"]], ["slow", "healthy"])
        self.assertTrue(all(item["status"] == "awaiting_approval" for item in result["outcomes"]))

    def test_prepared_url_resume_does_not_capture_or_rewrite_and_direct_apply_checks_freshness(self):
        from ats_agent.review import build_approval_manifest
        from ats_agent.workflow import apply_manifest, ResearchFreshnessError
        source = "https://example.com/posting"
        with patch("ats_agent.capture.capture_url", side_effect=self.capture) as capture:
            first = self.run_tailor(source)
        self.assertEqual(capture.call_count, 1)
        path = Path(first["outcomes"][0]["proposal_path"])
        original = path.read_bytes()
        with patch("ats_agent.capture.capture_url", side_effect=AssertionError("recaptured")), \
             patch("ats_agent.orchestrator.build_proposal", side_effect=AssertionError("rebuilt")):
            self.run_tailor(source)
        self.assertEqual(path.read_bytes(), original)
        proposal = json.loads(original)
        self.assertTrue(proposal["research"]["sources"])
        manifest = build_approval_manifest(proposal, proposal_filename=str(path),
            selections=[("C1", "balanced")], output_document=str(self.root / "output.docx"))
        approval = self.root / "approval.json"
        approval.write_text(json.dumps(manifest))
        with patch("ats_agent.orchestrator._liveness_check", return_value="changed") as live:
            with self.assertRaises(ResearchFreshnessError):
                apply_manifest(approval)
            result = self.run_tailor(source, approve_from=approval, verify_live=False)
        self.assertEqual(live.call_count, 2)
        self.assertEqual(result["outcomes"][0]["status"], "blocked_liveness")
        self.assertFalse((self.root / "output.docx").exists())

    def test_changed_approval_cannot_reuse_completed_delivery(self):
        source = str(ROOT / "examples/sample_job.md")
        first = self.run_tailor(source, interactive=True, reader=lambda _: "C1:balanced")
        outcome = first["outcomes"][0]
        output = Path(outcome["output_document"])
        before = output.read_bytes()
        approval = Path(outcome["proposal_path"]).with_name("approval.json")
        manifest = json.loads(approval.read_text())
        manifest["document_mode"] = "rebuild"
        approval.write_text(json.dumps(manifest))
        result = self.run_tailor(source, approve_from=approval)
        self.assertEqual(result["outcomes"][0]["status"], "blocked_recovery")
        self.assertEqual(output.read_bytes(), before)

    def test_candidate_cache_is_content_and_candidate_scoped(self):
        from ats_agent.workflow import build_proposal, build_evidence_ledger
        evidence = self.root / "evidence.md"
        evidence.write_text("Built SQL analysis reports.")
        cache = {}
        args = (ROOT / "examples/sample_resume.txt", ROOT / "examples/sample_job.md")
        with patch("ats_agent.workflow.build_evidence_ledger", wraps=build_evidence_ledger) as ledger:
            for _ in range(2):
                build_proposal(*args, evidence_paths=[evidence], candidate_cache=cache, candidate_id="a")
            self.assertEqual(ledger.call_count, 1)
            evidence.write_text("Built Python analysis reports.")
            build_proposal(*args, evidence_paths=[evidence], candidate_cache=cache, candidate_id="a")
            build_proposal(*args, evidence_paths=[evidence], candidate_cache=cache, candidate_id="b")
        self.assertEqual(ledger.call_count, 3)

    def test_cache_rejects_future_metadata_and_coalesces_concurrent_misses(self):
        from concurrent.futures import ThreadPoolExecutor
        from ats_agent.capture import capture_cached
        cache = self.root / "cache"
        url = "https://example.com/shared"
        with patch("ats_agent.capture.capture_url", side_effect=self.capture) as capture:
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda _: capture_cached(url, cache, source_type="job_posting"), range(4)))
            self.assertEqual(capture.call_count, 1)
            entry = next(cache.glob("*.json"))
            payload = json.loads(entry.read_text())
            payload["captured_at"] = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
            entry.write_text(json.dumps(payload))
            capture_cached(url, cache, source_type="job_posting")
        self.assertEqual(capture.call_count, 2)
        self.assertEqual({r["sha256"] for r in results}, {results[0]["sha256"]})

    def test_dns_deadline_blocks_fetch_and_permanent_errors_are_not_retried(self):
        from ats_agent.capture import CaptureError, capture_url
        release = Event()
        def resolve(*args, **kwargs):
            release.wait(1)
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        try:
            with patch("ats_agent.capture.CAPTURE_DEADLINE_SECONDS", 0.02), \
                 patch("ats_agent.capture.socket.getaddrinfo", side_effect=resolve), \
                 patch("ats_agent.capture.require_scrapling") as require:
                with self.assertRaisesRegex(CaptureError, "deadline expired"):
                    capture_url("https://example.com/a", self.root / "a.txt", source_type="job_posting")
                require.assert_not_called()
        finally:
            release.set()
        with patch("ats_agent.capture.require_scrapling", return_value="scrapling"), \
             patch("ats_agent.capture._scrape_once", side_effect=CaptureError("HTTP 404")) as fetch:
            with self.assertRaises(CaptureError):
                capture_url("https://example.com/a", self.root / "a.txt", source_type="job_posting")
        self.assertEqual(fetch.call_count, 1)


class WorkflowGuardTests(unittest.TestCase):
    @staticmethod
    def _manifest(proposal: str, digest: str) -> dict:
        return {
            "schema_version": 3,
            "proposal": proposal,
            "proposal_digest": digest,
            "selections": [{"change_id": "C1", "variant_id": "balanced"}],
            "approved_change_ids": ["C1"],
        }

    def test_selection_and_variant_guards_fail_closed(self) -> None:
        changes = {
            "C1": {"id": "C1", "variants": [{"id": "balanced", "text": "Rewritten"}]},
            "C2": {"id": "C2"},
        }
        for manifest, message in (
            ({}, "explicit selections"),
            ({"selections": [None]}, "requires change_id"),
            ({"selections": [{"change_id": "C1", "variant_id": "balanced"}, {"change_id": "C1", "variant_id": "balanced"}]}, "duplicate"),
            ({"selections": [{"change_id": "C1", "variant_id": None}]}, "explicit variant"),
        ):
            with self.subTest(manifest=manifest), self.assertRaisesRegex(ValueError, message):
                _selections(manifest, changes)
        with self.assertRaisesRegex(ValueError, "explicit variant"):
            _materialize_change(changes["C1"], None)
        with self.assertRaisesRegex(ValueError, "no variant"):
            _materialize_change(changes["C1"], "compact")
        self.assertEqual(_materialize_change(changes["C2"], None), changes["C2"])

    def test_research_and_output_guards_reject_stale_or_destructive_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "resume.txt"
            source.write_text("resume", encoding="utf-8")
            self.assertEqual(_default_output(source).name, "resume.tailored.txt")
            self.assertIsNone(_resolve_from(root, None))
            self.assertEqual(_resolve_from(root, "out.txt"), (root / "out.txt").resolve())
            with self.assertRaisesRegex(ValueError, "must not overwrite"):
                _validate_output_path(source, source, force=False)
            with self.assertRaisesRegex(ValueError, "unsupported output"):
                _validate_output_path(source, root / "out.rtf", force=False)
            existing = root / "out.txt"
            existing.write_text("old", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "already exists"):
                _validate_output_path(source, existing, force=False)
            _validate_output_path(source, existing, force=True)

        with self.assertRaisesRegex(ValueError, "no liveness timestamp"):
            _validate_research_freshness({"research": {}})
        with self.assertRaisesRegex(ValueError, "timestamp is invalid"):
            _validate_research_freshness({"research": {"captured_at": "not-a-time"}})
        old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        with self.assertRaisesRegex(ValueError, "capture is stale"):
            _validate_research_freshness({"research": {"captured_at": old}})

    def test_hard_gate_policy_requires_exact_acknowledgements(self) -> None:
        cases = (
            ([{"status": "unknown"}], (), "requirement_id"),
            ([{"requirement_id": "R1", "status": "unknown"}, {"requirement_id": "R1", "status": "unknown"}], (), "unique"),
            ([{"requirement_id": "R1", "status": "maybe"}], (), "invalid statuses"),
            ([{"requirement_id": "R1", "status": "unmet"}], (), "unmet"),
            ([{"requirement_id": "R1", "status": "unknown"}], ("",), "non-empty"),
            ([{"requirement_id": "R1", "status": "unknown"}], ("R1", "R1"), "unique"),
            ([{"requirement_id": "R1", "status": "unknown"}], ("R2",), "do not identify"),
            ([{"requirement_id": "R1", "status": "unknown"}], (), "explicit acknowledgement"),
        )
        for gates, acknowledgements, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                enforce_hard_gate_policy(gates, acknowledgements)
        self.assertEqual(
            enforce_hard_gate_policy([{"requirement_id": "R1", "status": "unknown"}], ("R1",)),
            ["R1"],
        )

    def test_manifest_path_and_digest_binding_rejects_substitutions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proposal = root / "proposal.json"
            proposal.write_text("{}", encoding="utf-8")
            approval = root / "approval.json"
            digest = "a" * 64
            approval.write_text(
                json.dumps(self._manifest("other.json", digest)),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(TailorBlocked, "different persisted proposal"):
                _approval_for_role({None: approval}, "role", proposal, digest)

            approval.write_text(
                json.dumps(self._manifest("proposal.json", "b" * 64)),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(TailorBlocked, "different proposal digest"):
                _approval_for_role({None: approval}, "role", proposal, digest)

            batch = root / "batch.json"
            batch.write_text(
                json.dumps({
                    "schema_version": 1,
                    "approval_manifests": {"role": "approval.json"},
                }),
                encoding="utf-8",
            )
            self.assertEqual(_approval_paths(batch), {"role": approval.resolve()})
            invalid = root / "invalid.json"
            invalid.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(TailorBlocked, "approval manifest or batch index"):
                _approval_paths(invalid)


if __name__ == "__main__":
    unittest.main()
