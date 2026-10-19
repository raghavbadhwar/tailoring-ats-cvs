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

    def test_requirement_sections_set_importance_without_magic_words(self) -> None:
        requirements = extract_requirements(
            "Basic Qualifications\n"
            "- Bachelor's degree\n"
            "- 3 years of relevant experience\n"
            "Preferred Qualifications\n"
            "- MBA\n"
        )

        self.assertEqual(
            self.requirement_for(requirements, "bachelor")["importance"],
            "mandatory",
        )
        experience = next(
            item for item in requirements if item["kind"] == "experience_years"
        )
        self.assertEqual(experience["importance"], "mandatory")
        self.assertEqual(
            self.requirement_for(requirements, "master")["importance"],
            "preferred",
        )

    def test_split_must_have_heading_and_year_range_keep_minimum(self) -> None:
        requirements = extract_requirements(
            "Requirements (\nMust Have):\n"
            "- 6–8 years of experience in product management.\n"
        )
        experience = next(
            item for item in requirements if item["kind"] == "experience_years"
        )

        self.assertEqual(experience["minimum_years"], 6)
        self.assertEqual(experience["importance"], "mandatory")

    def test_negated_degree_language_is_not_a_gate(self) -> None:
        requirements = extract_requirements(
            "You do not need an MBA. A master's degree is not required."
        )

        self.assertFalse(any(item["kind"] == "degree" for item in requirements))

    def test_master_project_bank_is_not_a_masters_degree(self) -> None:
        requirements = extract_requirements("A master's degree is required.")
        gates = evaluate_hard_gates(
            requirements,
            self.ledger("PROJECTS\n- Built a CV master project bank.\n"),
        )

        self.assertEqual(self.gate_for(gates, "degree")["status"], "unknown")

    def test_explicit_work_mode_is_a_hard_gate(self) -> None:
        requirement = next(
            item
            for item in extract_requirements("Work arrangement: on-site")
            if item["kind"] == "work_mode"
        )

        self.assertEqual(requirement["importance"], "mandatory")

    def test_evidence_bank_instructions_are_not_candidate_facts(self) -> None:
        ledger = build_evidence_ledger(
            "candidate-a",
            [
                EvidenceSource(
                    source="supporting",
                    source_file="bank.txt",
                    text=(
                        "GITHUB-AUDITED CV MASTER PROJECT BANK\n"
                        "Use Part I as the ready-to-edit CV draft.\n"
                        "For every pinned repository, add a roadmap.\n"
                        "Built a procurement workflow with approval gates.\n"
                    ),
                    candidate_id="candidate-a",
                )
            ],
        )

        self.assertEqual(
            [item.text for item in ledger.items],
            ["Built a procurement workflow with approval gates."],
        )

    def test_travel_percentage_over_one_hundred_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "travel percentage"):
            extract_requirements("Applicants must travel 140% of the time.")

    def test_authorization_sponsorship_mode_travel_and_grade_are_evaluated(self) -> None:
        requirements = extract_requirements(
            "Applicants must be authorized to work in India. "
            "No sponsorship is available. Hybrid work is required. "
            "Applicants must be willing to travel 25% of the time. "
            "A minimum CGPA of 8.0/10 is required."
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
            "Hybrid work is required. A minimum CGPA of 8.0/10 is required."
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

    def test_decimal_grade_requirement_preserves_value_scale_and_span(self) -> None:
        text = "A minimum CGPA of 8.5/10 is required."
        requirement = next(
            item
            for item in extract_requirements(text)
            if item["kind"] == "minimum_grade"
        )

        self.assertEqual(requirement["minimum"], 8.5)
        self.assertEqual(requirement["scale"], 10.0)
        self.assertEqual(requirement["text"], text)
        self.assertEqual(requirement["source_span"], {"start": 0, "end": len(text)})

    def test_decimal_grade_gate_respects_threshold_and_explicit_scale(self) -> None:
        requirements = extract_requirements(
            "A minimum CGPA of 8.5/10 is required."
        )
        cases = (
            ("EDUCATION\n- Earned CGPA 8.2/10.\n", "unmet"),
            ("EDUCATION\n- Earned GPA 3.9/4.\n", "unknown"),
            ("EDUCATION\n- Earned CGPA 9.0.\n", "unknown"),
        )
        for evidence, expected in cases:
            with self.subTest(evidence=evidence):
                gates = evaluate_hard_gates(requirements, self.ledger(evidence))
                self.assertEqual(
                    self.gate_for(gates, "minimum_grade")["status"],
                    expected,
                )

    def test_credential_enrollment_and_mode_constraint_gates(self) -> None:
        requirements = [
            {
                "id": "R1", "kind": "professional_credential",
                "importance": "mandatory", "text": "CA final is required.",
            },
            {
                "id": "R2", "kind": "enrollment", "importance": "mandatory",
                "text": "Current students must not apply.",
            },
            {
                "id": "R3", "kind": "work_mode", "importance": "mandatory",
                "text": "Remote work is required.", "value": "remote",
            },
            {
                "id": "R4", "kind": "work_mode_constraint",
                "importance": "mandatory", "text": "Remote-only role.",
                "value": "remote",
            },
        ]
        gates = evaluate_hard_gates(
            requirements,
            self.ledger(
                "EDUCATION\n- Currently enrolled Bachelor student, expected 2027.\n"
                "CREDENTIALS\n- Qualified CA final.\n"
            ),
        )
        self.assertEqual(self.gate_for(gates, "professional_credential")["status"], "met")
        self.assertEqual(self.gate_for(gates, "enrollment")["status"], "unmet")
        self.assertEqual(self.gate_for(gates, "work_mode_constraint")["status"], "met")

    def test_grade_gate_is_unknown_when_requirement_scale_is_missing(self) -> None:
        requirements = extract_requirements(
            "A minimum CGPA of 8.5 is required."
        )
        gates = evaluate_hard_gates(
            requirements,
            self.ledger("EDUCATION\n- Earned CGPA 9.0/10.\n"),
        )

        self.assertEqual(
            self.gate_for(gates, "minimum_grade")["status"],
            "unknown",
        )

    def test_written_grade_scales_are_recognized(self) -> None:
        requirements = extract_requirements(
            "A minimum GPA of 3.5 on a 4.0 scale is required."
        )
        requirement = self.gate_for(requirements, "minimum_grade")
        gates = evaluate_hard_gates(
            requirements,
            self.ledger("EDUCATION\n- Earned GPA 3.7 out of 4.0.\n"),
        )

        self.assertEqual(requirement["minimum"], 3.5)
        self.assertEqual(requirement["scale"], 4.0)
        self.assertEqual(self.gate_for(gates, "minimum_grade")["status"], "met")

    def test_common_written_grade_scale_forms_are_recognized(self) -> None:
        forms = (
            "GPA 3.5 on a scale of 4.0",
            "GPA 3.5 (on a 4.0 scale)",
            "GPA 3.5 on a 4.0-point scale",
        )
        for text in forms:
            with self.subTest(text=text):
                requirements = extract_requirements(f"A minimum {text} is required.")
                requirement = self.gate_for(requirements, "minimum_grade")
                self.assertEqual(requirement["minimum"], 3.5)
                self.assertEqual(requirement["scale"], 4.0)

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

    def test_pilot_vocabulary_keeps_complete_requirement_clauses(self) -> None:
        clause = (
            "Use AI agents and tool use for evaluation design and "
            "A/B testing for product analytics."
        )
        requirements = extract_requirements(clause)
        terms = {
            term for requirement in requirements for term in requirement["normalized_terms"]
        }
        self.assertTrue({"ai agents", "tool use", "evaluation design", "a/b testing", "product analytics"}.issubset(terms))
        self.assertTrue(all(requirement["text"] == clause for requirement in requirements))

    def test_availability_is_extracted_without_filtering_the_role(self) -> None:
        requirement = next(
            item
            for item in extract_requirements(
                "Candidates must be available for 6-12 months."
            )
            if item["kind"] == "availability"
        )
        self.assertEqual(requirement["duration"], "6-12 months")
        self.assertEqual(requirement["category"], "availability")


if __name__ == "__main__":
    unittest.main()
