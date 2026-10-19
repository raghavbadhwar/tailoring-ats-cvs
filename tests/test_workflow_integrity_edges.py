from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ats_agent.workflow import (
    _default_output,
    _ledger_from_proposal,
    _materialize_change,
    _resolve_from,
    _selections,
    _validate_output_path,
    _validate_research_freshness,
    apply_manifest,
)


class WorkflowIntegrityEdgeTests(unittest.TestCase):
    def test_research_liveness_fails_closed(self) -> None:
        _validate_research_freshness({})
        for research, message in (
            ({}, "no liveness timestamp"),
            ({"captured_at": "not-a-date"}, "timestamp is invalid"),
            ({"captured_at": "2026-08-19T12:00:00"}, "capture is stale"),
            (
                {
                    "captured_at": (
                        datetime.now(timezone.utc) - timedelta(days=8)
                    ).isoformat()
                },
                "capture is stale",
            ),
        ):
            with self.subTest(research=research), self.assertRaisesRegex(
                ValueError, message
            ):
                _validate_research_freshness({"research": research})

        _validate_research_freshness(
            {"research": {"captured_at": datetime.now(timezone.utc).isoformat()}}
        )

    def test_paths_and_default_outputs_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self.assertIsNone(_resolve_from(root, None))
            self.assertEqual(_resolve_from(root, "child.txt"), root / "child.txt")
            self.assertEqual(_resolve_from(root, str(root / "abs.txt")), root / "abs.txt")
            self.assertEqual(_default_output(root / "resume.pdf").name, "resume.tailored.docx")
            self.assertEqual(_default_output(root / "resume").name, "resume.tailored.txt")
            self.assertEqual(_default_output(root / "resume.docx").name, "resume.tailored.docx")

    def test_selection_and_variant_inputs_are_strict(self) -> None:
        changes = {"C1": {"id": "C1"}}
        self.assertEqual(
            _selections({}, ["C1"], changes),
            [{"change_id": "C1", "variant_id": None}],
        )
        with self.assertRaisesRegex(ValueError, "selections must be a list"):
            _selections({"selections": "C1"}, [], changes)
        for item in ("C1", {}, {"change_id": 1}):
            with self.subTest(item=item), self.assertRaisesRegex(
                ValueError, "requires change_id"
            ):
                _selections({"selections": [item]}, [], changes)
        self.assertEqual(
            _selections(
                {"selections": [{"change_id": "C1", "variant_id": "compact"}]},
                [],
                changes,
            ),
            [{"change_id": "C1", "variant_id": "compact"}],
        )

        change = {
            "id": "C1",
            "default_variant": "balanced",
            "variants": [
                {"id": "balanced", "text": "Balanced"},
                {"id": "compact", "text": "Compact"},
            ],
        }
        self.assertEqual(_materialize_change(change, None)["replacement_text"], "Balanced")
        self.assertEqual(
            _materialize_change(change, "compact")["replacement_text"], "Compact"
        )
        with self.assertRaisesRegex(ValueError, "has no variant missing"):
            _materialize_change(change, "missing")
        self.assertEqual(_materialize_change({"id": "C2"}, None), {"id": "C2"})

    def test_output_validation_preserves_source_and_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "resume.txt"
            source.write_text("trusted source\n", encoding="utf-8")
            cases = (
                (source, "must not overwrite"),
                (root / "out.pdf", "genuine PDF renderer"),
                (root / "out", "unsupported output format"),
                (root / "out.rtf", "unsupported output format"),
            )
            for output, message in cases:
                with self.subTest(output=output), self.assertRaisesRegex(
                    ValueError, message
                ):
                    _validate_output_path(source, output, force=False)

            output = root / "out.txt"
            output.write_text("existing\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "already exists"):
                _validate_output_path(source, output, force=False)
            _validate_output_path(source, output, force=True)
            self.assertEqual(source.read_text(encoding="utf-8"), "trusted source\n")

    def test_blocked_and_future_proposals_never_reach_apply(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "approval.json"
            proposal = root / "proposal.json"
            manifest.write_text(
                json.dumps({"schema_version": 1, "proposal": str(proposal)}),
                encoding="utf-8",
            )
            proposal.write_text(
                json.dumps({"status": "blocked", "reason": "unsafe input"}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "unsafe input"):
                apply_manifest(manifest)

            proposal.write_text(
                json.dumps({"status": "draft", "schema_version": 999}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "newer than this runtime"):
                apply_manifest(manifest)

    def test_missing_ledger_is_rejected_before_validation(self) -> None:
        with self.assertRaisesRegex(ValueError, "no evidence ledger"):
            _ledger_from_proposal({})
        ledger = _ledger_from_proposal({"candidate_id": "candidate", "evidence_ledger": []})
        self.assertEqual(ledger.candidate_id, "candidate")


if __name__ == "__main__":
    unittest.main()
