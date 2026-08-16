from __future__ import annotations

import unittest

from ats_agent.evidence import EvidenceSource, build_evidence_ledger
from ats_agent.validation import validate_change


class AtomicClaimValidationTests(unittest.TestCase):
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

    def test_same_number_with_different_unit_is_rejected(self) -> None:
        ledger = self.ledger(
            "PROJECTS\n"
            "- Built a finance workflow.\n"
            "- Processed 50 invoices.\n"
        )
        workflow = next(item for item in ledger.items if "finance workflow" in item.text)
        invoices = next(item for item in ledger.items if "50 invoices" in item.text)
        change = {
            "id": "C1",
            "operation": "replace_span",
            "expected_text": workflow.text,
            "replacement_text": "Built a finance workflow processing 50 records.",
            "evidence_ids": [workflow.id, invoices.id],
            "supported": True,
        }
        with self.assertRaisesRegex(ValueError, "metric binding"):
            validate_change(change, ledger)

    def test_same_percentage_with_different_scope_is_rejected(self) -> None:
        ledger = self.ledger(
            "PROJECTS\n"
            "- Built an operations workflow.\n"
            "- Reduced review time by 20%.\n"
        )
        workflow = next(item for item in ledger.items if "operations workflow" in item.text)
        reduction = next(item for item in ledger.items if "20%" in item.text)
        change = {
            "id": "C1",
            "operation": "replace_span",
            "expected_text": workflow.text,
            "replacement_text": "Built an operations workflow improving conversion by 20%.",
            "evidence_ids": [workflow.id, reduction.id],
            "supported": True,
        }
        with self.assertRaisesRegex(ValueError, "metric binding"):
            validate_change(change, ledger)

    def test_exact_metric_binding_is_allowed(self) -> None:
        ledger = self.ledger(
            "PROJECTS\n"
            "- Built a finance workflow.\n"
            "- Processed 50 records through the finance workflow.\n"
        )
        workflow = next(item for item in ledger.items if item.text == "Built a finance workflow.")
        records = next(item for item in ledger.items if "50 records" in item.text)
        change = {
            "id": "C1",
            "operation": "replace_span",
            "expected_text": workflow.text,
            "replacement_text": "Built a finance workflow that processed 50 records.",
            "evidence_ids": [workflow.id, records.id],
            "supported": True,
        }
        validate_change(change, ledger)

    def test_unrelated_evidence_cannot_authorize_source_rewrite(self) -> None:
        ledger = self.ledger(
            "PROJECTS\n"
            "- Built a Python workflow.\n"
            "- Conducted market sizing research.\n"
        )
        python_item = next(item for item in ledger.items if "Python" in item.text)
        market_item = next(item for item in ledger.items if "market sizing" in item.text)
        change = {
            "id": "C1",
            "operation": "replace_span",
            "expected_text": python_item.text,
            "replacement_text": "Created a Python workflow.",
            "evidence_ids": [market_item.id],
            "supported": True,
        }
        with self.assertRaisesRegex(ValueError, "edited source span"):
            validate_change(change, ledger)


if __name__ == "__main__":
    unittest.main()
