import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ats_agent.agents import career_report
from ats_agent.benchmark import run as run_benchmark
from ats_agent.cli import main as cli_main
from ats_agent.documents import patch_document, write_ats_docx
from ats_agent.evidence import (
    EvidenceItem,
    EvidenceLedger,
    EvidenceSource,
    SourceFragment,
    build_evidence_ledger,
    detect_ownership,
    ownership_rank,
)
from ats_agent.formatting import audit_file, audit_text
from ats_agent.ingestion import ExtractionError, load
from ats_agent.reporting import proposal_html, proposal_markdown
from ats_agent.requirements import extract_requirements, map_requirements
from ats_agent.validation import validate_change, validate_changes
from ats_agent.workflow import apply_manifest, build_proposal


class MoreTests(unittest.TestCase):
    def test_evidence_model_rejects_duplicates_and_source_mismatch(self):
        item = EvidenceItem(
            id="E1",
            candidate_id="a",
            text="Built Python workflows",
            source="resume",
            source_file="resume.txt",
            source_span="line 1",
            line_number=1,
            paragraph_index=None,
            part="text",
            ownership="direct",
        )
        with self.assertRaisesRegex(ValueError, "duplicate"):
            EvidenceLedger("a", (item, item))
        with self.assertRaisesRegex(ValueError, "candidate identity"):
            EvidenceLedger("b", (item,))
        with self.assertRaisesRegex(ValueError, "unknown ownership"):
            ownership_rank("superhero")
        self.assertEqual(detect_ownership("Observed a workflow"), "observed")
        self.assertEqual(detect_ownership("Founded a company"), "owner")
        self.assertEqual(detect_ownership("Led a team"), "lead")

    def test_source_fragments_preserve_paragraph_anchor(self):
        source = EvidenceSource(
            source="resume",
            source_file="resume.docx",
            text="Built Python workflows",
            fragments=(
                SourceFragment(
                    "word/document.xml",
                    4,
                    None,
                    "Built Python workflows",
                ),
            ),
        )
        ledger = build_evidence_ledger("a", [source])
        self.assertEqual(ledger.items[0].paragraph_index, 4)
        self.assertEqual(ledger.items[0].part, "word/document.xml")

    def test_requirement_extraction_more_gate_types(self):
        requirements = extract_requirements(
            "A minimum CGPA of 8.0 is required. This is an on-site role "
            "with 25% travel. React, SQL, Docker, and stakeholder "
            "management are preferred."
        )
        kinds = {requirement["kind"] for requirement in requirements}
        self.assertTrue(
            {"minimum_grade", "work_mode", "travel", "skill"}.issubset(
                kinds
            )
        )
        terms = {
            term
            for requirement in requirements
            for term in requirement["normalized_terms"]
        }
        self.assertTrue(
            {"react", "sql", "docker", "stakeholder management"}.issubset(
                terms
            )
        )

    def test_map_marks_unknown_skill_unsupported(self):
        ledger = build_evidence_ledger(
            "a",
            [
                EvidenceSource(
                    "resume",
                    "r.txt",
                    "- Built Excel analysis workflows.",
                )
            ],
        )
        requirements = extract_requirements("Kubernetes is required.")
        self.assertFalse(
            any(
                "kubernetes" in requirement.get("normalized_terms", [])
                for requirement in requirements
            )
        )
        requirements = extract_requirements("Python is required.")
        mapping = map_requirements(requirements, ledger)
        self.assertEqual(mapping[0]["coverage"], "unsupported")

    def test_validation_rejects_unsupported_employer_and_duplicate_ids(self):
        ledger = build_evidence_ledger(
            "a",
            [
                EvidenceSource(
                    "resume",
                    "r.txt",
                    "- Contributed to Python workflows with 42 tests.",
                )
            ],
        )
        item = ledger.items[0]
        change = {
            "id": "C1",
            "operation": "replace_span",
            "supported": True,
            "evidence_ids": [item.id],
            "expected_text": item.text,
            "replacement_text": (
                "Contributed to Python workflows for OpenAI with 42 tests."
            ),
        }
        with self.assertRaisesRegex(ValueError, "organization"):
            validate_change(change, ledger)
        safe = {
            **change,
            "replacement_text": "Supported Python workflows with 42 tests.",
        }
        with self.assertRaisesRegex(ValueError, "unique"):
            validate_changes([safe, safe], ledger)

    def test_text_insert_and_rebuild_docx(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "resume.txt"
            source.write_text(
                "SUMMARY\nCandidate\nPROJECTS\nSKILLS\nPython\n",
                encoding="utf-8",
            )
            output = root / "out.docx"
            patch_document(
                source,
                output,
                [
                    {
                        "id": "C1",
                        "operation": "insert_after",
                        "expected_text": "PROJECTS",
                        "replacement_text": (
                            "Built Python workflow automation with 42 tests."
                        ),
                        "anchor": {
                            "heading": "PROJECTS",
                            "line_number": 3,
                        },
                    }
                ],
                mode="rebuild",
            )
            loaded = load(output)
            self.assertIn("Built Python workflow automation", loaded["text"])
            self.assertIn("SKILLS", loaded["text"])

    def test_docx_diagnostics_and_format_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resume.docx"
            write_ats_docx(
                path,
                "SUMMARY\nCandidate\nEDUCATION\nB.Com 2027\nEXPERIENCE\n"
                "- Built Python workflows\nSKILLS\nPython",
            )
            loaded = load(path)
            self.assertEqual(loaded["format"], "docx")
            self.assertEqual(loaded["quality"]["status"], "usable")
            audit = audit_file(str(path))
            self.assertEqual(audit["status"], "audited")
            self.assertIn(audit["risk_level"], {"low", "medium", "high"})

    def test_html_rtf_and_unsupported_ingestion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            html_file = root / "a.html"
            html_file.write_text(
                "<h1>SUMMARY</h1><p>Built Python workflows with 42 tests.</p>",
                encoding="utf-8",
            )
            self.assertIn("Built Python", load(html_file)["text"])
            rtf = root / "a.rtf"
            rtf.write_text(
                r"{\rtf1 SUMMARY\par Built Python workflows with 42 tests.}",
                encoding="utf-8",
            )
            self.assertIn("Built Python", load(rtf)["text"])
            bad = root / "a.bin"
            bad.write_bytes(b"binary")
            with self.assertRaisesRegex(ExtractionError, "unsupported"):
                load(bad)

    def test_audit_text_flags_layout_risks(self):
        audit = audit_text(
            "EDUCATION\n" + "x" * 140 + "\nA     B\n● item"
        )
        ids = {finding["id"] for finding in audit["findings"]}
        self.assertTrue({"F2", "F3", "F4", "F5"}.issubset(ids))

    def test_report_is_explainable_not_universal_score(self):
        ledger = build_evidence_ledger(
            "a",
            [
                EvidenceSource(
                    "resume",
                    "r.txt",
                    "- Built Python workflows with 42 tests.",
                )
            ],
        )
        report = career_report(
            "SUMMARY\nAI product candidate\n"
            "- Built Python workflows with 42 tests.",
            "Python is required.",
            ledger=ledger,
        )
        recruiter = report["agents"]["recruiter"]
        self.assertNotIn("score", recruiter)
        self.assertIn(
            recruiter["decision"],
            {"aligned", "partially-aligned", "unclear"},
        )

    def test_benchmark_computes_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory) / "cases.jsonl"
            case = {
                "id": "one",
                "resume": "- Built Python workflow automation with 42 tests.",
                "job_description": (
                    "Python and workflow automation are required."
                ),
                "expected_supported_terms": [
                    "python",
                    "workflow automation",
                ],
                "expected_unsupported_terms": [],
                "expected_hard_gates": [],
            }
            dataset.write_text(
                json.dumps(case) + "\n",
                encoding="utf-8",
            )
            result = run_benchmark(dataset)
            self.assertEqual(result["case_count"], 1)
            self.assertEqual(result["supported_requirement_recall"], 1.0)
            self.assertEqual(result["unsafe_rewrite_count"], 0)

    def test_reporting_handles_empty_sections(self):
        proposal = {
            "candidate_id": "a",
            "status": "draft",
            "source": "resume.txt",
            "requirements": [],
            "requirement_evidence": [],
            "hard_gates": [],
            "changes": [],
            "evidence_ledger": [],
        }
        self.assertIn(
            "No deterministic hard gate",
            proposal_markdown(proposal),
        )
        self.assertIn("approval-manifest", proposal_html(proposal))

    def test_workflow_blocked_on_bad_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume = root / "empty.txt"
            jd = root / "job.txt"
            resume.write_text("", encoding="utf-8")
            jd.write_text("Python is required", encoding="utf-8")
            proposal = build_proposal(resume, jd)
            self.assertEqual(proposal["status"], "blocked")

    def test_apply_rejects_no_approval_and_invalid_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume = root / "resume.txt"
            jd = root / "job.txt"
            resume.write_text(
                "PROJECTS\n"
                "- Helped build automated workflows with 42 tests.\n",
                encoding="utf-8",
            )
            jd.write_text(
                "Workflow automation is required.",
                encoding="utf-8",
            )
            proposal = build_proposal(resume, jd, candidate_id="a")
            proposal_path = root / "proposal.json"
            proposal_path.write_text(
                json.dumps(proposal),
                encoding="utf-8",
            )
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "proposal": str(proposal_path),
                        "proposal_digest": proposal["proposal_digest"],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "no changes"):
                apply_manifest(manifest)
            change = next(
                item
                for item in proposal["changes"]
                if item.get("supported")
            )
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "proposal": str(proposal_path),
                        "proposal_digest": proposal["proposal_digest"],
                        "approved_change_ids": [change["id"]],
                        "mode": "magic",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "mode"):
                apply_manifest(manifest)

    def test_cli_doctor_format_validate_and_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume = root / "resume.txt"
            resume.write_text(
                "EDUCATION\nB.Com 2027\nEXPERIENCE\n"
                "- Built Python workflows with 42 tests.\nSKILLS\nPython\n",
                encoding="utf-8",
            )
            for args in (
                ["doctor"],
                ["format", str(resume)],
                ["validate", str(resume)],
            ):
                result = subprocess.run(
                    [sys.executable, "-m", "ats_agent.cli", *args],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(json.loads(result.stdout))
            bad = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ats_agent.cli",
                    "apply",
                    str(resume),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(bad.returncode, 2)

    def test_cli_main_direct_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume = root / "resume.txt"
            jd = root / "job.txt"
            dataset = root / "cases.jsonl"
            resume.write_text(
                "PROJECTS\n"
                "- Helped build automated workflows with 42 tests.\n",
                encoding="utf-8",
            )
            jd.write_text(
                "Workflow automation is required.",
                encoding="utf-8",
            )
            dataset.write_text(
                json.dumps(
                    {
                        "id": "case",
                        "resume": resume.read_text(encoding="utf-8"),
                        "job_description": jd.read_text(encoding="utf-8"),
                        "expected_supported_terms": [
                            "workflow automation"
                        ],
                        "expected_unsupported_terms": [],
                        "expected_hard_gates": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual(cli_main(["doctor"]), 0)
            self.assertEqual(
                cli_main(["audit", str(resume), str(jd)]),
                0,
            )
            proposal_path = root / "proposal.json"
            self.assertEqual(
                cli_main(
                    [
                        "propose",
                        str(resume),
                        str(jd),
                        "--output",
                        str(proposal_path),
                    ]
                ),
                0,
            )
            self.assertTrue(proposal_path.exists())
            self.assertEqual(
                cli_main(["benchmark", "--dataset", str(dataset)]),
                0,
            )
            self.assertEqual(cli_main(["format", str(resume)]), 0)
            self.assertEqual(cli_main(["validate", str(resume)]), 0)


if __name__ == "__main__":
    unittest.main()
