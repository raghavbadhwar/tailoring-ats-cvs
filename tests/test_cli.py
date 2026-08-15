import json
import subprocess
import sys
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

from ats_agent.ingestion import write_docx
from ats_agent.workflow import apply_manifest

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "ats_agent.cli", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_audit_validates_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            resume, job = Path(directory) / "resume.txt", Path(directory) / "job.md"
            resume.write_text("resume", encoding="utf-8")
            job.write_text("job", encoding="utf-8")
            result = self.run_cli("audit", str(resume), str(job))
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["status"], "ready")

    def test_apply_requires_string_change_ids(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as manifest:
            json.dump({"approved_change_ids": ["C1"]}, manifest)
            path = manifest.name
        result = self.run_cli("apply", path)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(json.loads(result.stdout)["source_overwrite"])

    def test_format_reports_layout_risks(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as resume:
            resume.write("EDUCATION\n" + "A" * 121 + "\n\tEXPERIENCE\nSKILLS\n")
            path = resume.name
        result = self.run_cli("format", path, "--json")
        self.assertEqual(result.returncode, 0)
        findings = {item["id"] for item in json.loads(result.stdout)["findings"]}
        self.assertTrue({"F2", "F3"}.issubset(findings))

    def test_propose_emits_named_agent_report_without_editing_source(self):
        with tempfile.TemporaryDirectory() as directory:
            resume, job = Path(directory) / "resume.txt", Path(directory) / "job.md"
            resume.write_text(
                "SUMMARY\n2026\n- Built Python workflow automation with 42 tests.\n",
                encoding="utf-8",
            )
            job.write_text(
                "Required Python and workflow automation for AI agents.",
                encoding="utf-8",
            )
            before = resume.read_text(encoding="utf-8")
            result = self.run_cli("propose", str(resume), str(job))
            payload = json.loads(result.stdout)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(payload["status"], "draft")
            self.assertIn("ats", payload["report"]["agents"])
            self.assertIn("hiring_manager", payload["report"]["agents"])
            self.assertTrue(payload["evidence_ledger"])
            self.assertTrue(payload["requirement_evidence"])
            self.assertEqual(resume.read_text(encoding="utf-8"), before)

    def test_apply_exact_supported_change_and_log(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "resume.txt"
            source.write_text("SUMMARY\nBuilt Python workflows.\n", encoding="utf-8")
            proposal = root / "proposal.json"
            proposal.write_text(
                json.dumps(
                    {
                        "status": "draft",
                        "candidate_id": "candidate-a",
                        "source": str(source),
                        "source_sha256": sha256(source.read_bytes()).hexdigest(),
                        "evidence_ledger": [
                            {
                                "id": "E1",
                                "candidate_id": "candidate-a",
                                "text": "Built Python workflows.",
                                "source": "resume",
                                "source_file": str(source),
                                "source_span": "line 2",
                                "line_number": 2,
                                "ownership": "direct",
                                "confidence": "high",
                            }
                        ],
                        "changes": [
                            {
                                "id": "C1",
                                "operation": "replace_span",
                                "supported": True,
                                "evidence_ids": ["E1"],
                                "expected_text": "Built",
                                "replacement_text": "Designed",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            manifest = root / "approved.json"
            manifest.write_text(
                json.dumps({"proposal": str(proposal), "output": str(root / "final.txt")}),
                encoding="utf-8",
            )
            result = apply_manifest(manifest, ["C1"])
            self.assertEqual(
                (root / "final.txt").read_text(encoding="utf-8"),
                "SUMMARY\nDesigned Python workflows.\n",
            )
            self.assertTrue((root / "final.txt.applied.json").exists())
            self.assertEqual(result["approved_change_ids"], ["C1"])
            self.assertEqual(result["validation"]["status"], "audited")

    def test_apply_rejects_stale_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "resume.txt"
            source.write_text("Built Built", encoding="utf-8")
            proposal = root / "proposal.json"
            proposal.write_text(
                json.dumps(
                    {
                        "source": str(source),
                        "source_sha256": "stale",
                        "evidence_ledger": [],
                        "changes": [],
                    }
                ),
                encoding="utf-8",
            )
            manifest = root / "approved.json"
            manifest.write_text(json.dumps({"proposal": str(proposal)}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "stale proposal"):
                apply_manifest(manifest, [])

    def test_docx_round_trip_is_extractable_and_non_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resume.docx"
            write_docx(path, "SUMMARY\nBuilt Python workflows.")
            result = self.run_cli("propose", str(path), str(path))
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["status"], "draft")


if __name__ == "__main__":
    unittest.main()
