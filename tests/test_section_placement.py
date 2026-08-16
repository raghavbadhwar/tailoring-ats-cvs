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


if __name__ == "__main__":
    unittest.main()
