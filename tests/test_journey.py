from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ats_agent.cli import main
from ats_agent.journey import run_journey


class JourneyTests(unittest.TestCase):
    def test_cv_first_run_pauses_for_intake_then_reuses_existing_engine(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume, answers, out = root / "resume.txt", root / "answers.json", root / "journey"
            resume.write_text("PRODUCT ANALYST\nBuilt Python and SQL product analysis.\n", encoding="utf-8")
            answers.write_text(
                json.dumps(
                    {
                        "role_queries": ["Product Analyst"],
                        "locations": ["Worldwide"],
                        "work_modes": ["remote"],
                        "work_authorization": "India",
                        "sponsorship": "unknown",
                        "relocation": "case-by-case",
                        "availability": "Immediately",
                        "deal_breakers": ["SQL"],
                        "use_linkedin_public_jobs": False,
                    }
                ),
                encoding="utf-8",
            )
            first = run_journey(resume, out, candidate_id="candidate")
            self.assertEqual(first["status"], "needs_input")
            self.assertTrue({"locations", "work_modes"} <= {q["id"] for q in first["questions"]})

            discovered = {
                "status": "search_complete",
                "captured_at": "2026-08-17T00:00:00+00:00",
                "request_count": 1,
                "failures": [],
                "jobs": [
                    {
                        "source": "freehire",
                        "title": "Product Analyst",
                        "company": "Example Co",
                        "location": "Remote",
                        "work_mode": "remote",
                        "posted_at": "2026-08-16",
                        "job_url": "https://jobs.example.com/product-analyst",
                        "provider_url": "https://freehire.me/jobs/product-analyst",
                        "description": "Python and SQL are required.",
                        "eligibility_note": "Verify remote jurisdiction.",
                    },
                    {
                        "source": "freehire",
                        "title": "Product Analyst",
                        "company": "Safe Co",
                        "location": "Remote",
                        "work_mode": "remote",
                        "posted_at": "2026-08-16",
                        "job_url": "https://jobs.example.com/safe",
                        "provider_url": "https://freehire.me/jobs/safe",
                        "description": "Product planning and customer research are required.",
                    },
                ],
            }
            researched = {
                "manifest": str(out / "research" / "manifest.json"),
                "jobs": [
                    {
                        "id": "example-co-product-analyst",
                        "company": "Example Co",
                        "role": "Product Analyst",
                        "status": "draft",
                        "keyword_coverage": [
                            {"coverage": "direct"},
                            {"coverage": "unsupported"},
                        ],
                        "eligibility_warnings": ["Verify remote jurisdiction."],
                        "proposal": str(out / "proposal.json"),
                        "review_html": str(out / "review.html"),
                    },
                    {
                        "id": "safe-co-product-analyst",
                        "company": "Safe Co",
                        "role": "Product Analyst",
                        "status": "draft",
                        "keyword_coverage": [{"coverage": "unsupported"}],
                        "eligibility_warnings": [],
                        "proposal": str(out / "safe-proposal.json"),
                        "review_html": str(out / "safe-review.html"),
                    },
                ],
            }
            with patch("ats_agent.journey.search_public_jobs", return_value=discovered), patch(
                "ats_agent.journey.research_jobs", return_value=researched
            ) as research:
                completed = run_journey(resume, out, candidate_id="candidate", answers_path=answers)

            self.assertEqual(completed["status"], "research_complete")
            self.assertEqual(
                [job["id"] for job in completed["ranked_jobs"]],
                ["safe-co-product-analyst", "example-co-product-analyst"],
            )
            self.assertEqual(completed["ranked_jobs"][1]["supported_requirement_coverage"], 50)
            self.assertEqual(completed["ranked_jobs"][1]["discovery"]["work_mode"], "remote")
            self.assertEqual(
                completed["ranked_jobs"][1]["discovery"]["possible_deal_breaker_matches"],
                ["SQL"],
            )
            research.assert_called_once()
            self.assertEqual(
                research.call_args.kwargs["evidence_paths"],
                [(out / "intake-evidence.md").resolve()],
            )
            self.assertIn(
                "Authorized to work in India",
                (out / "intake-evidence.md").read_text(encoding="utf-8"),
            )
            handoff = json.loads((out / "jobs.json").read_text(encoding="utf-8"))
            self.assertEqual(handoff["jobs"][0]["fallback"]["provider"], "freehire")
            self.assertFalse((out / "approval.json").exists())
            self.assertFalse((out / "tailored-resume.txt").exists())

            with patch("ats_agent.journey.search_public_jobs") as search_again:
                self.assertEqual(run_journey(resume, out)["status"], "research_complete")
            search_again.assert_not_called()

    def test_cli_dispatches_journey(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume = root / "resume.txt"
            resume.write_text("Python and SQL\n", encoding="utf-8")
            with patch("ats_agent.cli.run_journey", return_value={"status": "needs_input"}) as journey:
                self.assertEqual(main(["journey", str(resume), "--out", str(root / "run")]), 0)
            journey.assert_called_once_with(
                resume,
                root / "run",
                candidate_id="candidate",
                answers_path=None,
            )


if __name__ == "__main__":
    unittest.main()
