from __future__ import annotations

import unittest

from ats_agent.evidence import EvidenceSource, build_evidence_ledger
from ats_agent.rewriting import propose_supported_changes


class RewritePlannerTests(unittest.TestCase):
    def test_hard_gate_evidence_is_evaluated_but_not_rewritten(self) -> None:
        cv = (
            "AVAILABILITY\n"
            "Available for on-site work.\n"
            "PROJECTS\n"
            "Supported Python for procurement approvals, "
            "with structured decision checks.\n"
        )
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
        by_text = {item.text: item for item in ledger.items}
        availability = by_text["Available for on-site work."]
        project = by_text[
            "Supported Python for procurement approvals, "
            "with structured decision checks."
        ]
        requirements = [
            {"id": "R1", "kind": "work_mode"},
            {"id": "R2", "kind": "skill"},
        ]
        mappings = [
            {
                "requirement_id": "R1",
                "kind": "work_mode",
                "coverage": "direct",
                "normalized_terms": ["on-site"],
                "evidence_ids": [availability.id],
            },
            {
                "requirement_id": "R2",
                "kind": "skill",
                "coverage": "direct",
                "normalized_terms": ["python"],
                "evidence_ids": [project.id],
            },
        ]

        changes = propose_supported_changes(
            cv,
            requirements,
            mappings,
            ledger,
        )
        supported = [change for change in changes if change.get("supported")]

        self.assertEqual(len(supported), 1)
        self.assertEqual(supported[0]["expected_text"], project.text)
        self.assertEqual(
            {variant["id"] for variant in supported[0]["variants"]},
            {"conservative", "balanced", "compact"},
        )
        self.assertNotIn(
            availability.text,
            {change.get("expected_text") for change in supported},
        )


if __name__ == "__main__":
    unittest.main()
