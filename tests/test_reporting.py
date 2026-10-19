import json
import tempfile
import unittest
from pathlib import Path

from ats_agent.agents import career_report
from ats_agent.benchmark import run


class ReportingTests(unittest.TestCase):
    def test_recruiter_report_is_qualitative_and_not_a_fake_score(self):
        report = career_report(
            "SUMMARY\nAI product operations candidate.\n2026\n",
            "Python workflow automation experience is required.",
        )
        recruiter = report["agents"]["recruiter"]
        self.assertNotIn("score", recruiter)
        self.assertIn(recruiter["decision"], {"aligned", "partially-aligned", "unclear"})
        self.assertIn(recruiter["confidence"], {"low", "medium", "high"})
        self.assertIsInstance(recruiter["positive_signals"], list)
        self.assertIsInstance(recruiter["blocking_signals"], list)

    def test_resume_claims_are_not_marked_verified_from_numbers_alone(self):
        report = career_report(
            "PROJECTS\n- Increased enterprise revenue by 900% across 10 million users.\n",
            "Revenue analytics experience preferred.",
        )
        claims = report["agents"]["evidence"]["claims"]
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["verification_status"], "unverified")
        self.assertFalse(claims[0]["verified"])

    def test_benchmark_measures_expected_requirement_and_claim_outcomes(self):
        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory) / "cases.jsonl"
            cases = [
                {
                    "id": "supported-python",
                    "resume": "SKILLS\nPython\n",
                    "job_description": "Python is required.",
                    "evidence": ["python"],
                    "expected_hard_gates": [],
                    "expected_unsupported_claims": [],
                },
                {
                    "id": "unsupported-sql",
                    "resume": "SKILLS\nPython\n",
                    "job_description": "SQL is required.",
                    "evidence": ["python"],
                    "expected_hard_gates": [],
                    "expected_unsupported_claims": ["sql"],
                },
            ]
            dataset.write_text(
                "\n".join(json.dumps(case) for case in cases) + "\n",
                encoding="utf-8",
            )
            result = run(dataset)
            self.assertEqual(result["case_count"], 2)
            self.assertEqual(result["supported_requirement_recall"], 1.0)
            self.assertEqual(result["unsupported_requirement_detection_rate"], 1.0)
            self.assertIsNone(result["parser_risk_delta"])
            self.assertEqual(
                result["measurement_status"]["parser_risk_delta"],
                "not_implemented",
            )


if __name__ == "__main__":
    unittest.main()
