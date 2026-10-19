"""Regression coverage for QA-discovered proof-card isolation."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ats_agent.evidence import append_proof_card


class ProofCardCandidateIsolationRegressionTests(unittest.TestCase):
    # Regression: ISSUE-001 — a second candidate could append to another candidate's ledger.
    # Found by /qa on 2026-08-19.
    # Report: .gstack/qa-reports/qa-report-local-review-2026-08-19.md
    def test_rejects_cross_candidate_append_without_mutating_ledger(self) -> None:
        draft = {
            "status": "accepted",
            "activity": "Built a workflow automation.",
            "setting": "A student project.",
            "timeframe": None,
            "result": "Validated with 42 tests.",
            "origin": {
                "role": "Intern",
                "requirement": "workflow automation",
                "gap": "workflow automation",
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "run" / "proof-cards.json"
            append_proof_card(ledger, draft, candidate_id="candidate-a")
            before = ledger.read_text(encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "candidate_id does not match"):
                append_proof_card(ledger, draft, candidate_id="candidate-b")

            self.assertEqual(ledger.read_text(encoding="utf-8"), before)
            self.assertEqual(
                json.loads(before)["cards"][0]["candidate_id"], "candidate-a"
            )


if __name__ == "__main__":
    unittest.main()
