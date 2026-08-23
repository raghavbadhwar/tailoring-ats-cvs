"""Usability-layer tests: evidence scaffold, friendly start, deep-dive bridge."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class EvidenceScaffoldTests(unittest.TestCase):
    def _run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "ats_agent.cli", *args],
            capture_output=True, text=True, cwd=ROOT,
        )

    def test_new_creates_guided_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "evidence.md"
            result = self._run_cli("evidence", "new", "--out", str(out))
            self.assertEqual(result.returncode, 0)
            text = out.read_text(encoding="utf-8")
            for section in ("## Experience", "## Projects", "## Education",
                            "## Skills", "## Explicit non-evidence"):
                self.assertIn(section, text)

    def test_existing_file_is_protected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "evidence.md"
            out.write_text("keep me", encoding="utf-8")
            result = self._run_cli("evidence", "new", "--out", str(out))
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "blocked")
            self.assertEqual(out.read_text(encoding="utf-8"), "keep me")


class FriendlyStartTests(unittest.TestCase):
    def test_no_arguments_prints_three_door_card(self):
        result = subprocess.run(
            [sys.executable, "-m", "ats_agent.cli"],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0)
        for door in ("tailor", "deep-dive", "evidence"):
            self.assertIn(door, result.stdout)


class DeepDiveBridgeTests(unittest.TestCase):
    """Deep-dive must hand tailor a ready-to-consume export."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_matches_export_written_with_descriptions_and_hint(self):
        from ats_agent.deepdive import deep_dive

        jobs = [{
            "id": "g1", "role": "Data Analyst Intern",
            "description": "Build SQL dashboards for the revenue team.",
            "company": "acme", "job_url": "https://j/1",
            "updated_at": "2026-08-20T00:00:00Z",
        }]
        fetchers = {
            "greenhouse": lambda token: jobs,
            "lever": lambda token: [],
            "ashby": lambda token: [],
        }
        matches_path = Path(self.tmp.name) / "matches.json"
        with patch("ats_agent.deepdive._FETCHERS", fetchers):
            payload = deep_dive(
                "https://boards.greenhouse.io/acme",
                aspire="data analyst",
                writer=lambda _t: None,
                save_matches=matches_path,
            )
        self.assertTrue(matches_path.exists())
        exported = json.loads(matches_path.read_text(encoding="utf-8"))
        self.assertEqual(exported["jobs"][0]["role"], "Data Analyst Intern")
        self.assertIn("SQL dashboards", exported["jobs"][0]["description"])
        self.assertGreater(payload["match_count"], 0)
        self.assertIn("tailor", payload["next_hint"])
        # the export must be a valid research-export for the propose engine
        from ats_agent.intake import resolve_source
        resolved = resolve_source(str(matches_path))
        self.assertEqual(resolved["kind"], "json_export")

    def test_quiet_mode_sets_changed_flag_from_deltas(self):
        from ats_agent.deepdive import deep_dive

        jobs_a = [{"id": "x", "role": "Data Analyst",
                   "description": "sql", "company": "a",
                   "job_url": "https://a/1"}]
        jobs_b = jobs_a + [{"id": "y", "role": "Second Analyst",
                            "description": "more sql", "company": "a",
                            "job_url": "https://a/2"}]
        states = iter([jobs_a, jobs_b])
        fetchers = {
            "greenhouse": lambda token: next(states),
            "lever": lambda token: [],
            "ashby": lambda token: [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            wl = Path(tmp) / "wl.json"
            with patch("ats_agent.deepdive._FETCHERS", fetchers):
                first = deep_dive("greenhouse:seed", aspire="data analyst",
                                  watch=True, watchlist_path=wl,
                                  quiet=True, writer=lambda _t: None,
                                  save_matches=Path(tmp) / "m1.json")
                second = deep_dive("greenhouse:seed", aspire="data analyst",
                                   watch=True, watchlist_path=wl,
                                   quiet=True, writer=lambda _t: None,
                                   save_matches=Path(tmp) / "m2.json")
        self.assertFalse(first["changed"])
        self.assertTrue(second["changed"])


if __name__ == "__main__":
    unittest.main()
