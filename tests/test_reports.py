from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ats_agent.reports import proposal_html, proposal_markdown, write_review_bundle


class ProposalReportTests(unittest.TestCase):
    def sample_proposal(self) -> dict:
        return {
            "status": "draft",
            "candidate_id": "candidate-a",
            "source": "/tmp/resume.docx",
            "requirement_summary": {
                "direct": 1,
                "transferable": 1,
                "unsupported": 1,
                "hard_gate_blockers": 0,
                "hard_gate_unknowns": 1,
            },
            "decision": {"status": "requires_confirmation", "confidence": "medium"},
            "requirements": [
                {"id": "R1", "text": "Python is required.", "importance": "mandatory"},
            ],
            "evidence_matches": [
                {"requirement_id": "R1", "coverage": "direct", "evidence_ids": ["E1"]},
            ],
            "changes": [
                {
                    "id": "C1",
                    "reason": "aligns supported terminology",
                    "expected_text": "Helped build a Python workflow <script>alert(1)</script>",
                    "evidence_ids": ["E1"],
                    "validation": {"ownership_ceiling": "supporter"},
                    "variants": [
                        {
                            "id": "conservative",
                            "label": "Conservative",
                            "text": "Supported the development of a Python workflow.",
                            "evidence_ids": ["E1"],
                        },
                        {
                            "id": "balanced",
                            "label": "Balanced",
                            "text": "Supported the development of a Python workflow automation system.",
                            "evidence_ids": ["E1"],
                        },
                        {
                            "id": "compact",
                            "label": "Compact",
                            "text": "Supported a Python workflow automation system.",
                            "evidence_ids": ["E1"],
                        },
                    ],
                }
            ],
        }

    def test_markdown_contains_evidence_map_and_variants(self):
        result = proposal_markdown(self.sample_proposal())
        self.assertIn("Requirement-to-evidence map", result)
        self.assertIn("Python is required", result)
        self.assertIn("Conservative", result)
        self.assertIn("Balanced", result)
        self.assertIn("E1", result)

    def test_html_escapes_candidate_content_and_generates_manifest_controls(self):
        result = proposal_html(self.sample_proposal(), "proposal.json")
        self.assertNotIn("<script>alert(1)</script>", result)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", result)
        self.assertIn("approval-manifest.json", result)
        self.assertIn("selected_variants", result)
        self.assertIn("proposal.json", result)

    def test_review_bundle_writes_reusable_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            paths = write_review_bundle(self.sample_proposal(), output)
            self.assertEqual(set(paths), {"proposal", "markdown", "html"})
            self.assertTrue((output / "proposal.json").exists())
            self.assertTrue((output / "proposal.md").exists())
            self.assertTrue((output / "review.html").exists())
            self.assertEqual(json.loads((output / "proposal.json").read_text(encoding="utf-8"))["candidate_id"], "candidate-a")


if __name__ == "__main__":
    unittest.main()
