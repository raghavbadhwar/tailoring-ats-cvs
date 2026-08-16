import json
import tempfile
import unittest
from pathlib import Path

from ats_agent.documents import patch_document, write_ats_docx
from ats_agent.ingestion import load
from ats_agent.workflow import apply_manifest, build_proposal


class DocumentTests(unittest.TestCase):
    def test_preserve_docx_patch_keeps_unrelated_content_and_reparses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "resume.docx"
            write_ats_docx(source, "SUMMARY\nAI product candidate\nPROJECTS\n- Contributed to automated order workflows with 42 tests.\nSKILLS\nPython")
            loaded_before = load(source)
            target = next(p for p in loaded_before["paragraphs"] if "automated order workflows" in p["text"])
            output = root / "tailored.docx"
            patch_document(
                source,
                output,
                [{
                    "id": "C1",
                    "operation": "replace_span",
                    "expected_text": target["text"],
                    "replacement_text": "Contributed to workflow automation for orders with 42 tests.",
                    "anchor": {"part": target["part"], "paragraph_index": target["paragraph_index"]},
                }],
                mode="preserve",
            )
            loaded_after = load(output)
            self.assertIn("workflow automation", loaded_after["text"])
            self.assertIn("AI product candidate", loaded_after["text"])
            self.assertNotEqual(source.read_bytes(), output.read_bytes())

    def test_pdf_output_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "resume.txt"
            source.write_text("SUMMARY\n- Helped build Python workflows with 42 tests.\n", encoding="utf-8")
            proposal = build_proposal(source, source)
            supported = [c for c in proposal["changes"] if c.get("supported")]
            if not supported:
                self.skipTest("fixture did not produce a supported rewrite")
            proposal_path = root / "proposal.json"
            proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"proposal": str(proposal_path), "approved_change_ids": [supported[0]["id"]], "output": str(root / "bad.pdf")}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "PDF output"):
                apply_manifest(manifest, [supported[0]["id"]])

    def test_apply_uses_variant_selection_and_rejects_stale_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "resume.txt"
            source.write_text("PROJECTS\n- Helped build automated order workflows with 42 tests.\n", encoding="utf-8")
            jd = root / "job.md"
            jd.write_text("Workflow automation experience is required.", encoding="utf-8")
            proposal = build_proposal(source, jd, candidate_id="candidate-a")
            change = next(c for c in proposal["changes"] if c.get("supported"))
            proposal_path = root / "proposal.json"
            proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "proposal": str(proposal_path),
                "selections": [{"change_id": change["id"], "variant_id": "compact"}],
                "output": str(root / "final.txt"),
            }), encoding="utf-8")
            result = apply_manifest(manifest, [])
            self.assertEqual(result["status"], "applied")
            self.assertTrue((root / "final.txt.applied.json").exists())
            source.write_text(source.read_text(encoding="utf-8") + "changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, r"stale (?:proposal|artifact)"):
                apply_manifest(manifest, [])


if __name__ == "__main__":
    unittest.main()
