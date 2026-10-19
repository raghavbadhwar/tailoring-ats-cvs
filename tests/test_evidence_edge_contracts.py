from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ats_agent.evidence import (
    PROOF_CARD_LIMITS,
    ProofCard,
    _mapping_tuple,
    _optional_int,
    _proof_origin,
    _proof_text,
    _read_proof_cards,
    _string_tuple,
    append_proof_card,
    proof_card_sources,
)


class EvidenceEdgeContractTests(unittest.TestCase):
    def test_invalid_scalar_claim_inputs_are_rejected(self) -> None:
        self.assertEqual(_optional_int("7"), 7)
        for value in (True, object()):
            with self.subTest(value=type(value).__name__), self.assertRaises(ValueError):
                _optional_int(value)
        self.assertEqual(_string_tuple("metric"), ("metric",))
        with self.assertRaisesRegex(ValueError, "fact_types"):
            _string_tuple(4)
        with self.assertRaisesRegex(ValueError, "atomic_claims"):
            _mapping_tuple("bad")
        with self.assertRaisesRegex(ValueError, "atomic claim records"):
            _mapping_tuple(["bad"])

    def test_proof_card_rejects_unbacked_or_escaping_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "activity is required"):
            _proof_text(None, "activity", required=True)
        with self.assertRaisesRegex(ValueError, "activity must be text"):
            _proof_text(3, "activity")
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "proof.json"
            base = {"activity": "Built a test", "setting": "coursework", "origin": {"role": "Intern", "requirement": "testing", "gap": "testing"}}
            for value, message in (({**base, "candidate_id": "other"}, "candidate_id does not match"), ({**base, "status": "invented"}, "status is invalid"), ({**base, "artifact_path": "../secret"}, "must stay in the run directory")):
                with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                    ProofCard.from_mapping(value, candidate_id="candidate", revision=1, card_id="PC1", ledger_path=ledger)

    def test_proof_card_text_and_artifact_boundaries(self) -> None:
        with self.assertRaisesRegex(ValueError, "activity is required"):
            _proof_text("   ", "activity", required=True)
        with self.assertRaisesRegex(ValueError, "activity is too long"):
            _proof_text("x" * (PROOF_CARD_LIMITS["activity"] + 1), "activity")
        with self.assertRaisesRegex(ValueError, "origin must be an object"):
            _proof_origin(None)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = root / "run"
            run.mkdir()
            ledger = run / "proof.json"
            artifact = run / "certificate.txt"
            artifact.write_text("candidate-owned proof\n", encoding="utf-8")
            base = {
                "activity": "Built a test",
                "setting": "coursework",
                "artifact_path": artifact.name,
                "origin": {
                    "role": "Intern",
                    "requirement": "testing",
                    "gap": "testing",
                },
            }
            card = ProofCard.from_mapping(
                base,
                candidate_id="candidate",
                revision=1,
                card_id="PC1",
                ledger_path=ledger,
            )
            self.assertEqual(card.artifact_path, artifact.name)

            with self.assertRaisesRegex(ValueError, "does not exist"):
                ProofCard.from_mapping(
                    {**base, "artifact_path": "missing.txt"},
                    candidate_id="candidate",
                    revision=1,
                    card_id="PC1",
                    ledger_path=ledger,
                )
            outside = root / "outside.txt"
            outside.write_text("outside\n", encoding="utf-8")
            link = run / "link.txt"
            link.symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "stay in the run directory"):
                ProofCard.from_mapping(
                    {**base, "artifact_path": link.name},
                    candidate_id="candidate",
                    revision=1,
                    card_id="PC1",
                    ledger_path=ledger,
                )

    def test_card_ids_and_revision_ledgers_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = root / "proof.json"
            draft = {
                "activity": "Built a test",
                "setting": "coursework",
                "origin": {
                    "role": "Intern",
                    "requirement": "testing",
                    "gap": "testing",
                },
            }
            for card_id in (3, "   "):
                with self.subTest(card_id=card_id), self.assertRaisesRegex(
                    ValueError, "card_id must be text"
                ):
                    append_proof_card(
                        ledger,
                        {**draft, "card_id": card_id},
                        candidate_id="candidate",
                    )

            cases = (
                (
                    [{**draft, "card_id": "PC1", "revision": 1, "candidate_id": "other"}],
                    "candidate_id does not match",
                ),
                (
                    [{**draft, "card_id": 1, "revision": 1, "candidate_id": "candidate"}],
                    "invalid revision",
                ),
                (
                    [
                        {**draft, "card_id": "PC1", "revision": 1, "candidate_id": "candidate"},
                        {**draft, "card_id": "PC1", "revision": 3, "candidate_id": "candidate"},
                    ],
                    "append-only",
                ),
            )
            for cards, message in cases:
                ledger.write_text(
                    json.dumps({"schema_version": 1, "cards": cards}),
                    encoding="utf-8",
                )
                with self.subTest(message=message), self.assertRaisesRegex(
                    ValueError, message
                ):
                    proof_card_sources(
                        [ledger], candidate_id="candidate", job_text="testing"
                    )

    def test_malformed_ledgers_fail_before_evidence_is_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "proof.json"
            path.write_text("not-json", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not valid JSON"):
                _read_proof_cards(path)
            path.write_text(json.dumps({"schema_version": 0, "cards": []}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsupported schema"):
                _read_proof_cards(path)
            path.write_text(json.dumps({"schema_version": 1, "cards": {}}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "cards must be a list"):
                _read_proof_cards(path)


if __name__ == "__main__":
    unittest.main()
