from __future__ import annotations

import unittest

from ats_agent.evidence import (
    EvidenceItem,
    EvidenceLedger,
    EvidenceSource,
    build_evidence_ledger,
)
from ats_agent.requirements import extract_requirements, map_requirements
from ats_agent.rewriting import _find_section_anchor, propose_supported_changes


class SectionPlacementTests(unittest.TestCase):
    def test_external_work_evidence_targets_experience_section(self) -> None:
        resume = (
            "SUMMARY\n"
            "Business and AI candidate\n"
            "EXPERIENCE\n"
            "- Supported an operations team.\n"
            "PROJECTS\n"
            "- Built a market-sizing model.\n"
        )
        ledger = build_evidence_ledger(
            "candidate-a",
            [
                EvidenceSource(
                    source="resume",
                    source_file="resume.txt",
                    text=resume,
                    candidate_id="candidate-a",
                ),
                EvidenceSource(
                    source="supporting",
                    source_file="experience-bank.md",
                    text=(
                        "- Worked at Acme as an analyst using Python for "
                        "data analysis.\n"
                    ),
                    candidate_id="candidate-a",
                ),
            ],
        )
        requirements = extract_requirements(
            "Python and data analysis are required."
        )
        mappings = map_requirements(requirements, ledger)
        changes = propose_supported_changes(
            resume,
            requirements,
            mappings,
            ledger,
        )
        surfaced = next(
            change
            for change in changes
            if change.get("kind") == "surface-evidence"
        )
        self.assertEqual(surfaced["target_section"], "experience")
        self.assertEqual(
            surfaced["expected_text"],
            "Supported an operations team.",
        )
        self.assertEqual(surfaced["provider"], "deterministic")
        self.assertTrue(surfaced["variants"])

    def test_product_systems_heading_uses_last_section_item_as_anchor(self) -> None:
        resume = (
            "AI & PRODUCT SYSTEMS\n"
            "- Existing product system.\n"
            "SKILLS\n"
            "Python\n"
        )
        ledger = build_evidence_ledger(
            "candidate-a",
            [
                EvidenceSource(
                    source="resume",
                    source_file="resume.txt",
                    text=resume,
                    candidate_id="candidate-a",
                ),
                EvidenceSource(
                    source="supporting",
                    source_file="project-bank.md",
                    text="- Built Python workflow automation with 42 tests.\n",
                    candidate_id="candidate-a",
                ),
            ],
        )
        changes = propose_supported_changes(
            resume,
            extract_requirements("Python is required."),
            map_requirements(extract_requirements("Python is required."), ledger),
            ledger,
        )
        surfaced = next(change for change in changes if change.get("supported"))
        self.assertEqual(surfaced["target_section"], "projects")
        self.assertEqual(surfaced["expected_text"], "Existing product system.")
        self.assertEqual(surfaced["anchor"]["line_number"], 2)

    def test_docx_anchor_crosses_continued_heading_and_matches_list_text(self) -> None:
        cv = (
            "AI & PRODUCT SYSTEMS\n"
            "First project\n"
            "•  First project evidence.\n"
            "AI & PRODUCT SYSTEMS — CONTINUED\n"
            "Second project\n"
            "•  Last project evidence.\n"
            "SKILLS\n"
            "Python\n"
        )
        ledger = EvidenceLedger(
            candidate_id="candidate-a",
            items=(
                EvidenceItem(
                    id="E1",
                    candidate_id="candidate-a",
                    text="First project evidence.",
                    source="resume",
                    source_file="resume.docx",
                    source_span="paragraph 2",
                    line_number=None,
                    paragraph_index=2,
                    part="word/document.xml",
                    ownership="observed",
                ),
                EvidenceItem(
                    id="E2",
                    candidate_id="candidate-a",
                    text="Last project evidence.",
                    source="resume",
                    source_file="resume.docx",
                    source_span="paragraph 5",
                    line_number=None,
                    paragraph_index=5,
                    part="word/document.xml",
                    ownership="observed",
                ),
            ),
        )
        anchor = _find_section_anchor(cv, ledger, "projects")
        self.assertEqual(anchor["paragraph_index"], 5)
        self.assertEqual(anchor["text"], "Last project evidence.")

    def test_missing_target_section_is_visible_and_not_supported(self) -> None:
        resume = "SKILLS\nExcel\n"
        ledger = build_evidence_ledger(
            "candidate-a",
            [
                EvidenceSource(
                    source="resume",
                    source_file="resume.txt",
                    text=resume,
                    candidate_id="candidate-a",
                ),
                EvidenceSource(
                    source="supporting",
                    source_file="project-bank.md",
                    text="- Built Python workflow automation with 42 tests.\n",
                    candidate_id="candidate-a",
                ),
            ],
        )
        requirements = extract_requirements("Python is required.")
        changes = propose_supported_changes(
            resume,
            requirements,
            map_requirements(requirements, ledger),
            ledger,
        )
        self.assertFalse(any(change.get("supported") for change in changes))
        self.assertTrue(
            any(
                change.get("kind") == "placement-gap"
                and "No unambiguous projects section" in change["reason"]
                for change in changes
            )
        )

    def test_empty_target_section_is_not_an_insertion_anchor(self) -> None:
        cv = "PROJECTS\nSKILLS\nExcel\n"
        ledger = build_evidence_ledger(
            "candidate-a",
            [
                EvidenceSource(
                    source="resume",
                    source_file="resume.txt",
                    text=cv,
                    candidate_id="candidate-a",
                )
            ],
        )
        self.assertEqual(_find_section_anchor(cv, ledger, "projects"), {})

    def test_eligibility_evidence_is_evaluated_but_not_rewritten(self) -> None:
        resume = (
            "AVAILABILITY\n"
            "Available for on-site work.\n"
            "PROJECTS\n"
            "- Supported Python workflow automation for onboarding, with "
            "reviewable test notes.\n"
        )
        ledger = build_evidence_ledger(
            "candidate-a",
            [
                EvidenceSource(
                    source="resume",
                    source_file="resume.txt",
                    text=resume,
                    candidate_id="candidate-a",
                )
            ],
        )
        requirements = extract_requirements(
            "Python is required. On-site work is required."
        )
        mappings = map_requirements(requirements, ledger)
        changes = propose_supported_changes(
            resume,
            requirements,
            mappings,
            ledger,
        )
        supported = [
            change for change in changes if change.get("supported")
        ]
        self.assertTrue(
            any(
                "Python workflow automation"
                in str(change.get("expected_text") or "")
                for change in supported
            )
        )
        self.assertFalse(
            any(
                change.get("expected_text")
                == "Available for on-site work."
                for change in supported
            )
        )


if __name__ == "__main__":
    unittest.main()
