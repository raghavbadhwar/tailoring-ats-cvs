from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ats_agent.cli import main as cli_main
from ats_agent.review import (
    build_approval_manifest,
    render_html,
    render_markdown,
    write_review_bundle,
)


class UnifiedReviewTests(unittest.TestCase):
    def proposal(self) -> dict:
        return {
            "schema_version": 5,
            "status": "draft",
            "proposal_id": "P-REVIEW",
            "proposal_digest": "a" * 64,
            "candidate_id": "candidate-secret",
            "source": "/private/raghav-secret.docx",
            "job_description": "/private/job-secret.md",
            "requirements": [
                {
                    "id": "R1",
                    "text": "Python workflow automation is required.",
                    "importance": "mandatory",
                    "normalized_terms": ["python", "workflow automation"],
                }
            ],
            "requirement_evidence": [
                {
                    "requirement_id": "R1",
                    "coverage": "direct",
                    "evidence_ids": ["E1"],
                }
            ],
            "hard_gates": [
                {
                    "requirement_id": "R2",
                    "kind": "work_authorization",
                    "status": "unknown",
                    "requirement": "Must be authorised to work in Canada.",
                    "evidence_ids": [],
                }
            ],
            "evidence_ledger": [
                {
                    "id": "E1",
                    "text": "SECRET EVIDENCE processed 50 invoices.",
                    "source_file": "/private/project-bank-secret.md",
                    "source_span": "line 4",
                    "ownership": "direct",
                    "verification_status": "candidate_supplied",
                }
            ],
            "changes": [
                {
                    "id": "C1",
                    "kind": "language-rewrite",
                    "supported": True,
                    "reason": "Surface supported terminology.",
                    "expected_text": "SECRET BULLET helped build a workflow.",
                    "evidence_ids": ["E1"],
                    "default_variant": "balanced",
                    "variants": [
                        {
                            "id": "conservative",
                            "text": "SECRET CONSERVATIVE contributed to a workflow.",
                        },
                        {
                            "id": "balanced",
                            "text": "SECRET REWRITE contributed to workflow automation.",
                        },
                    ],
                },
                {
                    "id": "C2",
                    "kind": "qualification-gap",
                    "supported": False,
                    "reason": "No evidence supports Kubernetes.",
                    "expected_text": "",
                    "evidence_ids": [],
                    "variants": [],
                },
            ],
            "report": {
                "agents": {
                    "recruiter": {
                        "decision": "partially-aligned",
                        "confidence": "medium",
                        "positive_signals": ["Python evidence exists."],
                        "blocking_signals": ["Work authorization is unknown."],
                    }
                }
            },
        }

    def test_redacted_review_contains_no_candidate_content_or_paths(self) -> None:
        proposal = self.proposal()
        html = render_html(
            proposal,
            proposal_filename="proposal.json",
            default_output="tailored.docx",
            redacted=True,
        )
        markdown = render_markdown(proposal, redacted=True)
        combined = html + markdown
        for secret in (
            "candidate-secret",
            "/private/raghav-secret.docx",
            "/private/project-bank-secret.md",
            "SECRET EVIDENCE",
            "SECRET BULLET",
            "SECRET CONSERVATIVE",
            "SECRET REWRITE",
        ):
            self.assertNotIn(secret, combined)
        self.assertIn("Privacy-safe redacted review", combined)
        self.assertIn("a" * 64, combined)
        self.assertIn("[redacted]", combined)

    def test_full_review_escapes_html_and_warns_about_sensitive_data(self) -> None:
        proposal = self.proposal()
        proposal["changes"][0]["expected_text"] = (
            "<script>window.pwned=true</script>"
        )
        result = render_html(
            proposal,
            proposal_filename="proposal.json",
            default_output="tailored.docx",
        )
        self.assertNotIn("<script>window.pwned=true</script>", result)
        self.assertIn(
            "&lt;script&gt;window.pwned=true&lt;/script&gt;",
            result,
        )
        self.assertIn("Contains sensitive candidate evidence", result)

    def test_build_approval_manifest_validates_supported_changes_and_variants(self) -> None:
        manifest = build_approval_manifest(
            self.proposal(),
            proposal_filename="proposal.json",
            selections=[("C1", "balanced")],
            output_document="tailored.docx",
            document_mode="preserve",
            force=True,
        )
        self.assertEqual(manifest["schema_version"], 2)
        self.assertEqual(manifest["proposal_digest"], "a" * 64)
        self.assertEqual(manifest["approved_change_ids"], ["C1"])
        self.assertEqual(
            manifest["selections"],
            [{"change_id": "C1", "variant_id": "balanced"}],
        )
        self.assertTrue(manifest["force"])
        with self.assertRaisesRegex(ValueError, "unsupported"):
            build_approval_manifest(
                self.proposal(),
                proposal_filename="proposal.json",
                selections=[("C2", None)],
                output_document="tailored.docx",
            )
        with self.assertRaisesRegex(ValueError, "variant"):
            build_approval_manifest(
                self.proposal(),
                proposal_filename="proposal.json",
                selections=[("C1", "invented")],
                output_document="tailored.docx",
            )

    def test_review_bundle_uses_one_renderer_and_writes_all_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = write_review_bundle(
                self.proposal(),
                root,
                default_output="tailored.docx",
                redacted=True,
            )
            self.assertEqual(set(paths), {"proposal", "markdown", "html"})
            self.assertTrue((root / "proposal.json").is_file())
            self.assertTrue((root / "proposal.md").is_file())
            self.assertTrue((root / "review.html").is_file())
            self.assertNotIn(
                "SECRET EVIDENCE",
                (root / "review.html").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                json.loads((root / "proposal.json").read_text(encoding="utf-8"))[
                    "proposal_id"
                ],
                "P-REVIEW",
            )

    def test_cli_approve_creates_manifest_without_editing_a_resume(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proposal_path = root / "proposal.json"
            manifest_path = root / "approval.json"
            proposal_path.write_text(
                json.dumps(self.proposal(), indent=2),
                encoding="utf-8",
            )
            result = cli_main(
                [
                    "approve",
                    str(proposal_path),
                    "--select",
                    "C1:balanced",
                    "--output",
                    str(manifest_path),
                    "--output-document",
                    "tailored.docx",
                    "--force",
                ]
            )
            self.assertEqual(result, 0)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["proposal_digest"], "a" * 64)
            self.assertEqual(manifest["approved_change_ids"], ["C1"])
            self.assertFalse((root / "tailored.docx").exists())


if __name__ == "__main__":
    unittest.main()
