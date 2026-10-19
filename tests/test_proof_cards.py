from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ats_agent.evidence import append_proof_card
from ats_agent.review import build_approval_manifest, render_markdown
from ats_agent.workflow import apply_manifest, build_proposal


class ProofCardTests(unittest.TestCase):
    def _draft(self, **overrides: object) -> dict[str, object]:
        return {
            "status": "accepted",
            "activity": "Built workflow automation for procurement teams.",
            "setting": "A student consulting project.",
            "timeframe": None,
            "result": "Validated the workflow with 42 tests.",
            "origin": {
                "role": "Product Operations Intern",
                "requirement": "workflow automation",
                "gap": "workflow automation",
            },
            **overrides,
        }

    def _proposal(self, root: Path, cards: Path) -> tuple[Path, dict]:
        resume = root / "resume.txt"
        job = root / "job.txt"
        resume.write_text("PROJECTS\n- Helped build internal tools.\n", encoding="utf-8")
        job.write_text("Workflow automation experience is required.\n", encoding="utf-8")
        return resume, build_proposal(
            resume,
            job,
            candidate_id="candidate-a",
            evidence_card_paths=[cards],
        )

    def test_accepted_card_is_role_scoped_evidence_and_binds_a_fresh_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cards = root / "run" / "proof-cards.json"
            card = append_proof_card(cards, self._draft(), candidate_id="candidate-a")
            resume, proposal = self._proposal(root, cards)
            self.assertEqual(proposal["status"], "draft")
            self.assertEqual(
                proposal["source_sha256"],
                hashlib.sha256(resume.read_bytes()).hexdigest(),
            )
            self.assertTrue(any(item["source"] == "proof_card" for item in proposal["evidence_ledger"]))
            self.assertEqual(proposal["proof_card_receipts"], [{"card_id": card.card_id, "revision": 1, "status": "accepted", "relevant": True}])
            self.assertIn(str(cards.resolve()), proposal["evidence_files"])

    def test_bare_yes_and_outside_artifact_are_rejected_without_mutating_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cards = root / "run" / "proof-cards.json"
            with self.assertRaisesRegex(ValueError, "activity plus setting or timeframe"):
                append_proof_card(cards, self._draft(activity="yes", setting=None, timeframe=None), candidate_id="candidate-a")
            self.assertFalse(cards.exists())
            with self.assertRaisesRegex(ValueError, "run directory"):
                append_proof_card(cards, self._draft(artifact_path="../secret.txt"), candidate_id="candidate-a")
            self.assertFalse(cards.exists())

    def test_unmatched_card_is_retained_but_cannot_authorize_a_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cards = root / "run" / "proof-cards.json"
            append_proof_card(cards, self._draft(), candidate_id="candidate-a")
            resume, job = root / "resume.txt", root / "job.txt"
            resume.write_text("PROJECTS\n- Helped build internal tools.\n", encoding="utf-8")
            job.write_text("SQL analysis experience is required.\n", encoding="utf-8")
            proposal = build_proposal(
                resume,
                job,
                candidate_id="candidate-a",
                evidence_card_paths=[cards],
            )
            self.assertEqual(proposal["proof_card_receipts"][0]["relevant"], False)
            self.assertFalse(any(item["source"] == "proof_card" for item in proposal["evidence_ledger"]))

    def test_declined_contradictory_and_withdrawn_cards_never_authorize_rewrites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cards = root / "run" / "proof-cards.json"
            first = append_proof_card(cards, self._draft(), candidate_id="candidate-a")
            append_proof_card(
                cards,
                self._draft(card_id=first.card_id, status="withdrawn", activity=None, setting=None),
                candidate_id="candidate-a",
            )
            _resume, proposal = self._proposal(root, cards)
            self.assertEqual(proposal["proof_card_receipts"][0]["status"], "withdrawn")
            self.assertFalse(any(item["source"] == "proof_card" for item in proposal["evidence_ledger"]))
            for status in ("asked", "declined", "insufficient", "contradiction_pending"):
                pending = root / f"{status}.json"
                append_proof_card(
                    pending,
                    self._draft(status=status, activity=None, setting=None),
                    candidate_id="candidate-a",
                )
                _resume, pending_proposal = self._proposal(root, pending)
                self.assertFalse(any(item["source"] == "proof_card" for item in pending_proposal["evidence_ledger"]))

    def test_cli_writes_a_canonical_card_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            draft, cards = root / "draft.json", root / "run" / "proof-cards.json"
            draft.write_text(json.dumps(self._draft()), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ats_agent.cli",
                    "proof-card",
                    "--input",
                    str(draft),
                    "--out",
                    str(cards),
                    "--candidate-id",
                    "candidate-a",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(json.loads(result.stdout)["status"], "written")
            self.assertEqual(
                json.loads(cards.read_text(encoding="utf-8"))["schema_version"], 1
            )

    def test_correction_and_withdrawal_invalidate_an_existing_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cards = root / "run" / "proof-cards.json"
            first = append_proof_card(cards, self._draft(), candidate_id="candidate-a")
            _resume, proposal = self._proposal(root, cards)
            change = next(item for item in proposal["changes"] if item.get("supported"))
            proposal_path = root / "proposal.json"
            approval_path = root / "approval.json"
            proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
            approval_path.write_text(
                json.dumps(
                    build_approval_manifest(
                        proposal,
                        proposal_filename=str(proposal_path),
                        selections=[(change["id"], change["default_variant"])],
                        output_document=str(root / "tailored.txt"),
                    )
                ),
                encoding="utf-8",
            )
            append_proof_card(cards, self._draft(card_id=first.card_id, result="Validated with 43 tests."), candidate_id="candidate-a")
            with self.assertRaisesRegex(ValueError, "candidate_evidence.*hash"):
                apply_manifest(approval_path)
            append_proof_card(cards, self._draft(card_id=first.card_id, status="withdrawn", activity=None, setting=None), candidate_id="candidate-a")
            with self.assertRaisesRegex(ValueError, "candidate_evidence.*hash"):
                apply_manifest(approval_path)

    def test_failed_write_preserves_prior_revision_and_redaction_hides_card_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cards = root / "run" / "proof-cards.json"
            first = append_proof_card(cards, self._draft(), candidate_id="candidate-a")
            before = cards.read_text(encoding="utf-8")
            with patch("ats_agent.evidence.os.replace", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(OSError, "disk full"):
                    append_proof_card(cards, self._draft(card_id=first.card_id), candidate_id="candidate-a")
            self.assertEqual(cards.read_text(encoding="utf-8"), before)
            _resume, proposal = self._proposal(root, cards)
            redacted = render_markdown(proposal, redacted=True)
            self.assertNotIn("procurement teams", redacted)
            self.assertNotIn(str(cards.parent), redacted)


if __name__ == "__main__":
    unittest.main()
