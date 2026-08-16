from __future__ import annotations

import unittest

from ats_agent.evidence import EvidenceSource, build_evidence_ledger
from ats_agent.requirements import (
    evaluate_hard_gates,
    extract_requirements,
    map_requirements,
)


class RequirementEngineTests(unittest.TestCase):
    def ledger(self, text: str):
        return build_evidence_ledger(
            "candidate-a",
            [
                EvidenceSource(
                    source="resume",
                    source_file="resume.txt",
                    text=text,
                    candidate_id="candidate-a",
                )
            ],
        )

    def requirement_for(self, requirements: list[dict], term: str) -> dict:
        return next(
            requirement
            for requirement in requirements
            if term in requirement.get("normalized_terms", [])
        )

    def gate_for(self, gates: list[dict], kind: str) -> dict:
        return next(gate for gate in gates if gate["kind"] == kind)

    def test_semicolon_clauses_keep_local_importance(self) -> None:
        requirements = extract_requirements(
            "Python is required; Docker is preferred. "
            "Candidates must be authorized to work in India."
        )
        self.assertEqual(
            self.requirement_for(requirements, "python")["importance"],
            "mandatory",
        )
        self.assertEqual(
            self.requirement_for(requirements, "docker")["importance"],
            "preferred",
        )
        authorization = next(
            requirement
            for requirement in requirements
            if requirement["kind"] == "work_authorization"
        )
        self.assertEqual(authorization["importance"], "mandatory")
        self.assertEqual(authorization["country"], "India")

    def test_travel_percentage_over_one_hundred_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "travel percentage"):
            extract_requirements("Applicants must travel 140% of the time.")

    def test_authorization_sponsorship_mode_travel_and_grade_are_evaluated(self) -> None:
        requirements = extract_requirements(
            "Applicants must be authorized to work in India. "
            "No sponsorship is available. Hybrid work is required. "
            "Applicants must be willing to travel 25% of the time. "
            "A minimum CGPA of 8.0 is required."
        )
        ledger = self.ledger(
            "ELIGIBILITY\n"
            "- Authorized to work in India without sponsorship.\n"
            "- Available for hybrid work and willing to travel up to 30%.\n"
            "EDUCATION\n"
            "- Earned CGPA 8.5/10.\n"
        )
        gates = evaluate_hard_gates(requirements, ledger)
        for kind in (
            "work_authorization",
            "sponsorship",
            "work_mode",
            "travel",
            "minimum_grade",
        ):
            self.assertEqual(
                self.gate_for(gates, kind)["status"],
                "met",
                kind,
            )

    def test_required_sponsorship_fails_when_employer_will_not_sponsor(self) -> None:
        requirements = extract_requirements("No sponsorship is available.")
        gates = evaluate_hard_gates(
            requirements,
            self.ledger("ELIGIBILITY\n- I require visa sponsorship.\n"),
        )
        self.assertEqual(
            self.gate_for(gates, "sponsorship")["status"],
            "unmet",
        )

    def test_academic_years_do_not_satisfy_experience_gate(self) -> None:
        requirements = extract_requirements(
            "At least 2 years of professional experience are required."
        )
        gates = evaluate_hard_gates(
            requirements,
            self.ledger(
                "EDUCATION\n"
                "B.Com. (Hons.), 2024-2027\n"
                "EXPERIENCE\n"
                "- Completed 6 months of internship experience.\n"
            ),
        )
        self.assertEqual(
            self.gate_for(gates, "experience_years")["status"],
            "unmet",
        )

    def test_project_year_does_not_satisfy_graduation_gate(self) -> None:
        requirements = extract_requirements("Applicants must graduate in 2027.")
        gates = evaluate_hard_gates(
            requirements,
            self.ledger("PROJECTS\n- Built a Python project in 2027.\n"),
        )
        self.assertEqual(
            self.gate_for(gates, "graduation_year")["status"],
            "unknown",
        )

    def test_explicit_work_mode_and_grade_mismatches_are_unmet(self) -> None:
        requirements = extract_requirements(
            "Hybrid work is required. A minimum CGPA of 8.0 is required."
        )
        gates = evaluate_hard_gates(
            requirements,
            self.ledger(
                "ELIGIBILITY\n- Available only for remote work.\n"
                "EDUCATION\n- Earned CGPA 7.5/10.\n"
            ),
        )
        self.assertEqual(
            self.gate_for(gates, "work_mode")["status"],
            "unmet",
        )
        self.assertEqual(
            self.gate_for(gates, "minimum_grade")["status"],
            "unmet",
        )

    def test_ambiguous_aliases_do_not_satisfy_technical_requirements(self) -> None:
        cases = (
            (
                "React is required.",
                "EXPERIENCE\n- React quickly to operational incidents.\n",
                "react",
            ),
            (
                "Retrieval-augmented generation is required.",
                "EXPERIENCE\n- Prepared a red-amber-green RAG status.\n",
                "retrieval-augmented generation",
            ),
        )
        for job_description, evidence, term in cases:
            with self.subTest(term=term):
                requirements = extract_requirements(job_description)
                mappings = map_requirements(
                    requirements,
                    self.ledger(evidence),
                )
                mapping = next(
                    item
                    for item in mappings
                    if term in item.get("normalized_terms", [])
                )
                self.assertEqual(mapping["coverage"], "unsupported")
                self.assertEqual(mapping["evidence_ids"], [])

    def test_unambiguous_react_and_rag_evidence_remains_supported(self) -> None:
        cases = (
            (
                "React is required.",
                "SKILLS\nReact.js\n",
                "react",
            ),
            (
                "Retrieval-augmented generation is required.",
                "PROJECTS\n- Built a RAG pipeline for document retrieval.\n",
                "retrieval-augmented generation",
            ),
        )
        for job_description, evidence, term in cases:
            with self.subTest(term=term):
                requirements = extract_requirements(job_description)
                mappings = map_requirements(
                    requirements,
                    self.ledger(evidence),
                )
                mapping = next(
                    item
                    for item in mappings
                    if term in item.get("normalized_terms", [])
                )
                self.assertIn(mapping["coverage"], {"direct", "transferable"})
                self.assertTrue(mapping["evidence_ids"])


if __name__ == "__main__":
    unittest.main()
