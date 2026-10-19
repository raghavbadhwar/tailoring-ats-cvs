from __future__ import annotations

import unittest

from ats_agent.evidence import EvidenceSource, build_evidence_ledger


class AtomicClaimExtractionTests(unittest.TestCase):
    def test_compound_bullet_is_split_into_atomic_claims(self) -> None:
        ledger = build_evidence_ledger(
            "candidate-a",
            [
                EvidenceSource(
                    source="resume",
                    source_file="resume.txt",
                    text=(
                        "PROJECTS\n"
                        "- Processed 50 invoices and reduced review time by 20%.\n"
                    ),
                    candidate_id="candidate-a",
                )
            ],
        )
        item = ledger.items[0]
        self.assertGreaterEqual(len(item.atomic_claims), 2)
        texts = [claim.text.lower() for claim in item.atomic_claims]
        self.assertTrue(any("50 invoices" in text for text in texts))
        self.assertTrue(any("20%" in text and "review time" in text for text in texts))

    def test_metrics_keep_value_unit_and_scope_together(self) -> None:
        ledger = build_evidence_ledger(
            "candidate-a",
            [
                EvidenceSource(
                    source="resume",
                    source_file="resume.txt",
                    text="PROJECTS\n- Processed 50 invoices and reduced review time by 20%.\n",
                    candidate_id="candidate-a",
                )
            ],
        )
        metrics = [
            metric
            for claim in ledger.items[0].atomic_claims
            for metric in claim.metrics
        ]
        self.assertTrue(
            any(metric.value == "50" and metric.unit == "invoice" for metric in metrics)
        )
        self.assertTrue(
            any(
                metric.value == "20"
                and metric.unit == "percent"
                and "review" in metric.scope.lower()
                for metric in metrics
            )
        )

    def test_candidate_supplied_claims_are_not_promoted_to_verified(self) -> None:
        ledger = build_evidence_ledger(
            "candidate-a",
            [
                EvidenceSource(
                    source="resume",
                    source_file="resume.txt",
                    text="PROJECTS\n- Built a Python workflow.\n",
                    candidate_id="candidate-a",
                )
            ],
        )
        self.assertEqual(ledger.items[0].verification_status, "candidate_supplied")
        self.assertTrue(ledger.items[0].atomic_claims)
        self.assertTrue(
            all(
                claim.verification_status == "candidate_supplied"
                for claim in ledger.items[0].atomic_claims
            )
        )


if __name__ == "__main__":
    unittest.main()
