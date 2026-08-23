"""Tests for the company deep-dive engine."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ats_agent.deepdive import (
    BoardError,
    Watchlist,
    analyze_careers_page_text,
    analyze_roles,
    expand_aspiration,
    internship_program_signal,
    verdict,
)


def _job(role, description="", updated_at=None, url=None):
    job = {"role": role, "description": description}
    if updated_at:
        job["updated_at"] = updated_at
    if url:
        job["job_url"] = url
    return job


class VocabularyTests(unittest.TestCase):
    def test_multi_word_aspiration_suppresses_subtokens(self):
        vocab = expand_aspiration("data analyst")
        self.assertNotIn("data", vocab)
        self.assertIn("data analyst", vocab)

    def test_single_word_keeps_aliases(self):
        vocab = expand_aspiration("power bi")
        self.assertTrue(any("power" in term for term in vocab))


class VerdictTierTests(unittest.TestCase):
    VOCAB = expand_aspiration("data analyst")

    def test_act_now_on_direct_match(self):
        analysis = analyze_roles(
            [_job("Data Analyst Intern", "sql dashboards",
                  "2026-08-20T00:00:00Z")],
            self.VOCAB,
        )
        state, reasons = verdict(analysis, {"program_evidence": False})
        self.assertEqual(state, "ACT NOW")
        self.assertGreaterEqual(len(reasons), 1)

    def test_watch_closely_on_fresh_adjacent(self):
        # vocabulary appears only in the description, never the title,
        # so this is adjacency momentum rather than a direct match.
        analysis = analyze_roles(
            [_job("Platform Lead", "analytics infrastructure",
                  "2026-08-19T00:00:00Z")],
            ["analytics"],
        )
        state, _ = verdict(analysis, {"program_evidence": False})
        self.assertEqual(state, "WATCH CLOSELY")

    def test_on_radar_when_postings_but_no_match(self):
        analysis = analyze_roles([_job("Accountant", "ledger bookkeeping")],
                                 self.VOCAB)
        program = internship_program_signal([])
        state, reasons = verdict(analysis, program)
        self.assertEqual(state, "ON RADAR")
        self.assertIn("re-run weekly", reasons[1])

    def test_no_signal_on_empty_feed(self):
        state, _ = verdict(analyze_roles([], self.VOCAB),
                           internship_program_signal([]))
        self.assertEqual(state, "NO_SIGNAL")

    def test_internship_program_signal_counts_open_titles(self):
        program = internship_program_signal([
            _job("SWE Intern"), _job("Data Intern"), _job("Manager"),
        ])
        self.assertEqual(program["intern_open_now"], 2)
        self.assertTrue(program["program_evidence"])


class CareersPageSignalTests(unittest.TestCase):
    def test_hiring_language_detected(self):
        page = analyze_careers_page_text(
            "We are hiring across teams. Join our team in Bengaluru. "
            "Analysts use SQL daily.",
            ["analyst"],
        )
        self.assertGreater(page["marker_hits"], 0)
        self.assertIn("analyst", page["vocabulary_on_page"])

    def test_quiet_page_scores_zero(self):
        page = analyze_careers_page_text("Investor relations and press.", [])
        self.assertEqual(page["marker_hits"], 0)


class WatchlistDeltaTests(unittest.TestCase):
    def test_first_snapshot_then_growth_delta(self):
        with tempfile.TemporaryDirectory() as tmp:
            wl = Watchlist(Path(tmp) / "wl.json")
            prev = wl.record(
                "greenhouse:acme",
                Watchlist.fingerprint([{"job_url": "u-a", "role": "A"}]),
            )
            self.assertIsNone(prev)
            current = Watchlist.fingerprint([
                {"job_url": "u-a", "role": "A"},
                {"job_url": "u-b", "role": "B"},
            ])
            deltas = Watchlist.delta(prev, current)
            self.assertIn("first snapshot taken", deltas)

            # recording the same fingerprint again reports its predecessor
            next_prev = wl.record("greenhouse:acme", current)
            self.assertEqual(next_prev["posting_count"], 1)
            deltas = Watchlist.delta(next_prev, current)
            self.assertTrue(any("grew" in d for d in deltas))

            grown = Watchlist.fingerprint([
                {"job_url": "u-a", "role": "A"},
                {"job_url": "u-b", "role": "B"},
                {"job_url": "u-c", "role": "C"},
            ])
            latest_prev = wl.record("greenhouse:acme", grown)
            deltas = Watchlist.delta(latest_prev, grown)
            self.assertTrue(any("grew" in d for d in deltas))

            steady_prev = wl.record("greenhouse:acme", grown)
            self.assertEqual(Watchlist.delta(steady_prev, grown),
                             ["no change since last check"])

    def test_persistence_across_instances(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wl.json"
            Watchlist(path).record("lever:x", {"posting_count": 3})
            reloaded = Watchlist(path)
            self.assertEqual(reloaded.data["companies"]["lever:x"]["posting_count"], 3)


class IsolationTests(unittest.TestCase):
    def test_dead_board_does_not_sink_the_batch(self):
        from ats_agent.deepdive import deep_dive

        good = [{"id": "g1", "role": "Data Analyst Intern",
                 "description": "sql dashboards", "company": "liveco",
                 "job_url": "https://liveco.example.com/1",
                 "updated_at": "2026-08-20T00:00:00Z"}]

        fetchers = {
            "greenhouse": lambda token: (_ for _ in ()).throw(
                BoardError("HTTP 404")),
            "lever": lambda token: [
                {**good[0], "company": token},
            ],
            "ashby": lambda token: [],
        }

        with tempfile.TemporaryDirectory() as tmp:
            with patch("ats_agent.deepdive._FETCHERS", fetchers):
                payload = deep_dive(
                    "https://boards.greenhouse.io/deadco\n"
                    "https://jobs.lever.co/liveco",
                    aspire="data analyst",
                    watch=True,
                    watchlist_path=Path(tmp) / "wl.json",
                    writer=lambda _t: None,
                )
        statuses = {r["source"].split(":")[0]: r["verdict"]
                    for r in payload["results"]}
        self.assertEqual(statuses["greenhouse"], "NO_SIGNAL")
        self.assertEqual(statuses["lever"], "ACT NOW")


class DeepDiveBranchTests(unittest.TestCase):
    def test_careers_fallback_success_and_failure(self):
        from ats_agent.deepdive import BoardError, deep_dive

        def fake_capture(url, destination, *, source_type):
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                "We are hiring. Join our team. Analysts welcome.\n",
                encoding="utf-8")
            return {"url": url, "path": str(destination), "sha256": "x",
                    "captured_at": "2026-08-23T00:00:00+00:00",
                    "method": "scrapling_public_https",
                    "source_type": source_type,
                    "extraction_status": "captured"}

        with patch("ats_agent.deepdive.capture_url", side_effect=fake_capture):
            payload = deep_dive("https://acme.example.com/careers",
                                aspire="analyst", writer=lambda _t: None)
        self.assertEqual(payload["mode"], "careers_page")
        self.assertGreater(payload["analysis"]["marker_hits"], 0)

        from ats_agent.capture import CaptureError
        def failing(url, destination, *, source_type):
            raise CaptureError("connection reset")
        with patch("ats_agent.deepdive.capture_url", side_effect=failing):
            with self.assertRaises(BoardError):
                deep_dive("https://acme.example.com/careers",
                          writer=lambda _t: None)

    def test_cards_and_helpers(self):
        from ats_agent import deepdive as D
        self.assertEqual(D._provider_url("greenhouse", "acme"),
                         "https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true")
        self.assertEqual(D._clean_lines("a\n\nA \n b"), "a\nb")
        results = [{
            "source": "greenhouse:x", "verdict": "COLD", "reasons": ["r"],
            "deltas": [],
            "analysis": {"direct_matches": [{"role": "R", "url": "u",
                                             "age_days": 3}]},
            "internship_program": {"program_evidence": True,
                                   "intern_open_now": 1,
                                   "intern_titles_seen": ["T"]},
        }]
        card = D._card(results, "data analyst")
        self.assertIn("⚪ COLD", card)
        fb = D._card_fallback("s", {"method": "m", "captured_at": "n"},
                              {"marker_hits": 0, "hiring_markers": [],
                               "vocabulary_on_page": []})
        self.assertIn("no hiring language", fb)

    def test_days_since_garbage(self):
        from ats_agent.deepdive import _days_since
        self.assertIsNone(_days_since("not-a-date"))
        self.assertIsNone(_days_since(""))

if __name__ == "__main__":
    unittest.main()
