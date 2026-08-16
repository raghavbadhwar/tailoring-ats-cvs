from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ats_agent.documents import patch_document
from ats_agent.ingestion import ExtractionError, load as real_load
from ats_agent.workflow import apply_manifest, build_proposal


class TransactionalApplyTests(unittest.TestCase):
    def _prepare(
        self,
        root: Path,
        *,
        output_name: str = "tailored.txt",
        force: bool = False,
    ) -> tuple[Path, Path, Path]:
        resume = root / "resume.txt"
        job = root / "job.md"
        proposal_path = root / "proposal.json"
        manifest_path = root / "approval.json"
        output = root / output_name

        resume.write_text(
            "PROJECTS\n"
            "- Helped build automated order workflows with 42 tests.\n",
            encoding="utf-8",
        )
        job.write_text(
            "Workflow automation experience is required.",
            encoding="utf-8",
        )
        proposal = build_proposal(
            resume,
            job,
            candidate_id="candidate-a",
        )
        self.assertEqual(proposal["status"], "draft")
        change = next(
            item for item in proposal["changes"] if item.get("supported")
        )
        variant_id = (
            change.get("default_variant") or change["variants"][0]["id"]
        )
        proposal_path.write_text(
            json.dumps(proposal, indent=2),
            encoding="utf-8",
        )
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "proposal": str(proposal_path),
                    "proposal_digest": proposal["proposal_digest"],
                    "selections": [
                        {
                            "change_id": change["id"],
                            "variant_id": variant_id,
                        }
                    ],
                    "approved_change_ids": [change["id"]],
                    "document_mode": "preserve",
                    "output": str(output),
                    "force": force,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return resume, manifest_path, output

    def test_existing_output_is_not_overwritten_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _resume, manifest, output = self._prepare(root)
            output.write_text("existing trusted output\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "already exists.*force"):
                apply_manifest(manifest)

            self.assertEqual(
                output.read_text(encoding="utf-8"),
                "existing trusted output\n",
            )

    def test_force_replaces_existing_output_after_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _resume, manifest, output = self._prepare(root, force=True)
            output.write_text("old output\n", encoding="utf-8")

            result = apply_manifest(manifest)

            self.assertEqual(result["status"], "applied")
            self.assertNotEqual(
                output.read_text(encoding="utf-8"),
                "old output\n",
            )
            self.assertIn(
                "workflow automation",
                output.read_text(encoding="utf-8").lower(),
            )

    def test_unknown_output_extension_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _resume, manifest, output = self._prepare(
                root,
                output_name="tailored.rtf",
            )

            with self.assertRaisesRegex(ValueError, "unsupported output format"):
                apply_manifest(manifest)

            self.assertFalse(output.exists())

    def test_document_patcher_rejects_rtf_and_html_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "resume.txt"
            source.write_text("Supported Python checks.\n", encoding="utf-8")
            change = {
                "id": "C1",
                "operation": "replace_span",
                "expected_text": "Supported Python checks.",
                "replacement_text": "Supported Python validation.",
                "anchor": {},
            }
            for suffix in (".rtf", ".html"):
                with self.subTest(suffix=suffix):
                    output = root / f"tailored{suffix}"
                    with self.assertRaisesRegex(
                        ValueError,
                        "unsupported output format",
                    ):
                        patch_document(source, output, [change])
                    self.assertFalse(output.exists())

    def test_failed_output_verification_leaves_no_output_or_temp_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume, manifest, output = self._prepare(root)
            source_bytes = resume.read_bytes()

            def fail_for_generated_output(path: Path) -> dict:
                resolved = Path(path).expanduser().resolve()
                if resolved == resume.resolve():
                    return real_load(resolved)
                raise ExtractionError("simulated post-write verification failure")

            with patch(
                "ats_agent.workflow.load",
                side_effect=fail_for_generated_output,
            ):
                with self.assertRaisesRegex(
                    ExtractionError,
                    "simulated post-write verification failure",
                ):
                    apply_manifest(manifest)

            self.assertFalse(output.exists())
            self.assertEqual(resume.read_bytes(), source_bytes)
            self.assertEqual(
                [path for path in root.iterdir() if ".tmp-" in path.name],
                [],
            )


if __name__ == "__main__":
    unittest.main()
