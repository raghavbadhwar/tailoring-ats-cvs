import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ats_agent.review import render_html, render_markdown


class ReviewReportTests(unittest.TestCase):
    def proposal(self) -> dict:
        return {
            "schema_version": 5,
            "status": "draft",
            "proposal_id": "P1",
            "proposal_digest": "a" * 64,
            "candidate_id": "candidate-a",
            "source": "/tmp/resume.docx",
            "job_description": "/tmp/job.md",
            "requirements": [
                {
                    "id": "R1",
                    "text": "Python workflow automation is required.",
                    "normalized_terms": ["python"],
                    "importance": "mandatory",
                    "kind": "skill",
                },
                {
                    "id": "R2",
                    "text": "Supabase is preferred.",
                    "normalized_terms": ["supabase"],
                    "importance": "preferred",
                    "kind": "skill",
                },
            ],
            "requirement_evidence": [
                {
                    "requirement_id": "R1",
                    "normalized_terms": ["python"],
                    "importance": "mandatory",
                    "coverage": "direct",
                    "evidence_ids": ["E1"],
                },
                {
                    "requirement_id": "R2",
                    "normalized_terms": ["supabase"],
                    "importance": "preferred",
                    "coverage": "unsupported",
                    "evidence_ids": [],
                },
            ],
            "hard_gates": [],
            "evidence_ledger": [
                {
                    "id": "E1",
                    "candidate_id": "candidate-a",
                    "text": "Contributed to Python workflow automation.",
                    "source": "resume",
                    "source_file": "/tmp/resume.docx",
                    "source_span": "line 4",
                    "line_number": 4,
                    "ownership": "contributor",
                    "confidence": "high",
                    "verification_status": "candidate_supplied",
                }
            ],
            "changes": [
                {
                    "id": "C1",
                    "kind": "language-rewrite",
                    "operation": "replace_span",
                    "expected_text": "Helped build Python workflows.",
                    "replacement_text": "Contributed to Python workflow automation.",
                    "variants": [
                        {
                            "id": "balanced",
                            "text": "Contributed to Python workflow automation.",
                        }
                    ],
                    "default_variant": "balanced",
                    "evidence_ids": ["E1"],
                    "supported": True,
                    "reason": "Improve clarity while preserving ownership.",
                },
                {
                    "id": "C2",
                    "kind": "qualification-gap",
                    "operation": "none",
                    "expected_text": "",
                    "replacement_text": "supabase",
                    "evidence_ids": [],
                    "supported": False,
                    "reason": "No candidate evidence supports this requirement.",
                },
            ],
            "report": {
                "agents": {
                    "recruiter": {
                        "decision": "partially-aligned",
                        "confidence": "medium",
                        "positive_signals": ["Python is supported"],
                        "blocking_signals": ["Supabase is unsupported"],
                    }
                }
            },
        }

    def test_markdown_contains_requirements_evidence_and_changes(self):
        report = render_markdown(self.proposal())
        self.assertIn("Requirement-to-Evidence Matrix", report)
        self.assertIn("Python workflow automation", report)
        self.assertIn("E1", report)
        self.assertIn("C1", report)
        self.assertIn("C2", report)
        self.assertIn("Unsupported", report)

    def test_html_is_self_contained_escaped_and_only_supports_safe_approval(self):
        proposal = self.proposal()
        proposal["changes"][0]["expected_text"] = "<script>alert('x')</script>"
        report = render_html(
            proposal,
            proposal_filename="proposal.json",
            default_output="tailored.docx",
        )
        self.assertNotIn("<script>alert('x')</script>", report)
        self.assertIn("&lt;script&gt;alert", report)
        self.assertIn('data-change-id="C1"', report)
        self.assertIn('value="C1"', report)
        self.assertIn('data-change-id="C2"', report)
        self.assertIn("disabled", report)
        self.assertIn("approval-manifest.json", report)
        self.assertNotIn("http://", report)
        self.assertNotIn("https://", report)

    def test_cli_review_writes_markdown_and_html(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proposal_path = root / "proposal.json"
            markdown_path = root / "review.md"
            html_path = root / "review.html"
            proposal_path.write_text(json.dumps(self.proposal()), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ats_agent.cli",
                    "review",
                    str(proposal_path),
                    "--markdown",
                    str(markdown_path),
                    "--html",
                    str(html_path),
                    "--output-document",
                    "tailored.docx",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "written")
            self.assertTrue(markdown_path.exists())
            self.assertTrue(html_path.exists())
            self.assertIn("C1", markdown_path.read_text(encoding="utf-8"))
            self.assertIn(
                "Download approval manifest",
                html_path.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
