from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ats_agent.workflow import build_proposal


class EvidenceConflictTests(unittest.TestCase):
    def test_conflicting_gpa_is_recorded_without_selecting_a_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume = root / "resume.txt"
            evidence = root / "profile.txt"
            job = root / "job.txt"
            resume.write_text(
                "EDUCATION\nBachelor of Commerce with CGPA 8.55.\n"
                "PROJECTS\nBuilt Python analysis workflows.\n",
                encoding="utf-8",
            )
            evidence.write_text(
                "Candidate profile records a CGPA of 8.82.\n",
                encoding="utf-8",
            )
            job.write_text("Python is required.\n", encoding="utf-8")

            proposal = build_proposal(
                resume,
                job,
                evidence_paths=[evidence],
                candidate_id="candidate-a",
            )

            self.assertEqual(proposal["evidence_conflicts"][0]["kind"], "cgpa")
            self.assertEqual(
                {item["value"] for item in proposal["evidence_conflicts"][0]["values"]},
                {"8.55", "8.82"},
            )

    def test_scoped_authorization_and_graduation_conflicts_are_visible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume, evidence, job = root / "resume.txt", root / "profile.txt", root / "job.txt"
            resume.write_text(
                "EDUCATION\nGraduating in 2027.\nELIGIBILITY\nAuthorized to work in India.\nPROJECTS\nBuilt Python workflows.\n",
                encoding="utf-8",
            )
            evidence.write_text(
                "Candidate requires visa sponsorship and is graduating in 2028.\n",
                encoding="utf-8",
            )
            job.write_text("Python is required.\n", encoding="utf-8")
            proposal = build_proposal(resume, job, evidence_paths=[evidence])
            self.assertEqual(
                {item["kind"] for item in proposal["evidence_conflicts"]},
                {"graduation_year", "work_authorization"},
            )


if __name__ == "__main__":
    unittest.main()
