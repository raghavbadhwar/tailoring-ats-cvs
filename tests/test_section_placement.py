from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ats_agent.evidence import (
    EvidenceSource,
    SourceFragment,
    build_evidence_ledger,
)
from ats_agent.requirements import extract_requirements, map_requirements
from ats_agent.rewriting import propose_supported_changes
from ats_agent.workflow import build_proposal


class SectionPlacementTests(unittest.TestCase):
    def test_docx_project_evidence_shares_last_project_anchor(self) -> None:
        lines = [
            "PROFILE",
            "Commerce student",
            "AI & PRODUCT SYSTEMS",
            "Existing System\t2026",
            "•  Designed operating workflows.",
            "SKILLS",
            "Finance: Corporate finance",
        ]
        resume = "\n".join(lines)
        ledger = build_evidence_ledger(
            "candidate-a",
            [
                EvidenceSource(
                    source="resume",
                    source_file="resume.docx",
                    text=resume,
                    fragments=tuple(
                        SourceFragment(
                            part="word/document.xml",
                            paragraph_index=index,
                            line_number=None,
                            text=line,
                        )
                        for index, line in enumerate(lines)
                    ),
                    candidate_id="candidate-a",
                ),
                EvidenceSource(
                    source="supporting",
                    source_file="projects.md",
                    text=(
                        "Built a Python data analysis prototype.\n"
                        "Built a market sizing model for a new venture.\n"
                    ),
                    candidate_id="candidate-a",
                ),
            ],
        )
        requirements = extract_requirements(
            "Python data analysis and market sizing are required."
        )
        changes = propose_supported_changes(
            resume,
            requirements,
            map_requirements(requirements, ledger),
            ledger,
        )
        surfaced = [
            change
            for change in changes
            if change.get("kind") == "surface-evidence"
        ]
        self.assertEqual(len(surfaced), 2)
        self.assertEqual(
            [change["anchor"]["paragraph_index"] for change in surfaced],
            [4, 4],
        )

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
        self.assertEqual(surfaced["anchor"]["heading"], "EXPERIENCE")
        self.assertEqual(surfaced["provider"], "deterministic")
        self.assertTrue(surfaced["variants"])

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

    def test_project_heading_is_bound_to_supported_project_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume = root / "resume.txt"
            job = root / "job.md"
            evidence = root / "projects.md"
            resume.write_text("PROJECTS\n- Built a lightweight prototype.\n", encoding="utf-8")
            job.write_text("Python data analysis is required.", encoding="utf-8")
            evidence.write_text("Built a Python data analysis prototype.\n", encoding="utf-8")

            proposal = build_proposal(
                resume,
                job,
                evidence_paths=[evidence],
                candidate_id="candidate-a",
                project_heading="VENTURE SYSTEMS",
            )

        heading = proposal["changes"][0]
        self.assertEqual(heading["kind"], "section-heading")
        self.assertEqual(heading["replacement_text"], "VENTURE SYSTEMS")
        self.assertTrue(heading["evidence_ids"])


if __name__ == "__main__":
    unittest.main()
