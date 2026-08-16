from __future__ import annotations

import unittest

from ats_agent.review import render_html


class ReviewApprovalBindingTests(unittest.TestCase):
    def proposal(self) -> dict:
        return {
            "schema_version": 5,
            "status": "draft",
            "proposal_id": "P1",
            "proposal_digest": "a" * 64,
            "candidate_id": "candidate-a",
            "source": "/tmp/resume.docx",
            "job_description": "/tmp/job.md",
            "requirements": [],
            "requirement_evidence": [],
            "hard_gates": [],
            "evidence_ledger": [],
            "changes": [],
            "report": {"agents": {"recruiter": {}}},
        }

    def test_primary_review_manifest_is_schema_v2_and_digest_bound(self) -> None:
        html = render_html(
            self.proposal(),
            proposal_filename="proposal.json",
            default_output="tailored.docx",
            digest_reference="proposal",
        )
        self.assertIn("schema_version:2", html)
        self.assertIn("proposal_digest:proposal.proposal_digest", html)
        self.assertIn("document_mode:'preserve'", html)

    def test_constant_digest_review_manifest_is_schema_v2_and_bound(self) -> None:
        html = render_html(
            self.proposal(),
            proposal_filename="proposal.json",
            default_output="tailored.docx",
        )
        self.assertIn("schema_version:2", html)
        self.assertIn("proposal_digest:proposalDigest", html)
        self.assertIn('const proposalDigest="' + "a" * 64 + '"', html)


if __name__ == "__main__":
    unittest.main()
