"""Tests for the chat-first stderr summary renderer."""

import unittest

from ats_agent.summary import render_proposal_summary


def _proposal() -> dict:
    return {
        "candidate_id": "candidate-2026",
        "proposal_id": "P5BD52E7114900692ADE2",
        "status": "draft",
        "proposal_digest": "baf11362d5f81b4c70b2abf708247c22525e46c1380be1b44e05cfaa0884f3a5",
        "requirements": [
            {"kind": "skill", "normalized_terms": ["sql"], "importance": "preferred"},
            {
                "kind": "degree",
                "normalized_terms": ["bachelor"],
                "importance": "mandatory",
            },
        ],
        "requirement_evidence": [
            {
                "normalized_terms": ["power bi"],
                "coverage": "direct",
                "evidence_ids": ["E1"],
            },
            {
                "normalized_terms": ["power bi"],
                "coverage": "direct",
                "evidence_ids": ["E2"],
            },
            {
                "normalized_terms": ["a/b testing"],
                "coverage": "unsupported",
                "evidence_ids": [],
            },
        ],
        "changes": [
            {
                "id": "C1",
                "kind": "surface-evidence",
                "target_section": "experience",
                "default_variant": "conservative",
                "anchor": {"part": "text", "line_number": 5, "heading": "Experience"},
                "variants": [
                    {
                        "id": "conservative",
                        "text": "Bengaluru Food Drive volunteer analytics: tracked donations.",
                    }
                ],
            },
            {
                "id": "C2",
                "kind": "qualification-gap",
                "reason": "No candidate evidence supports this requirement; do not insert it into the CV.",
            },
        ],
    }


class ChatSummaryTests(unittest.TestCase):
    def setUp(self):
        self.text = render_proposal_summary(_proposal())

    def test_reports_candidate_status_and_counts(self):
        self.assertIn("candidate-2026", self.text)
        self.assertIn("P5BD52E7114900692ADE2", self.text)
        self.assertIn("requirements analysed : 2", self.text)

    def test_aggregates_duplicate_term_rows(self):
        self.assertEqual(self.text.count("power bi"), 1)
        self.assertIn("(2 evidence)", self.text)

    def test_marks_unsupported_terms_as_gaps(self):
        self.assertIn("a/b testing", self.text)
        self.assertIn("unsupported", self.text)

    def test_next_step_commands_use_real_selections(self):
        self.assertIn("--select C1:conservative", self.text)
        self.assertIn("ats-agent apply approval.json", self.text)

    def test_refused_gap_is_visible(self):
        self.assertIn("refused gaps : 1", self.text)
        self.assertIn("do not insert", self.text)

    def test_no_scores_or_probability_claims(self):
        for banned in ("score", "percent", "%", "probability"):
            self.assertNotIn(banned, self.text.lower())


if __name__ == "__main__":
    unittest.main()
