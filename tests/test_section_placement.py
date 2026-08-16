from __future__ import annotations

import unittest

from ats_agent.evidence import EvidenceSource, build_evidence_ledger
from ats_agent.requirements import extract_requirements, map_requirements
from ats_agent.rewriting import propose_supported_changes


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


if __name__ == "__main__":
    unittest.main()
