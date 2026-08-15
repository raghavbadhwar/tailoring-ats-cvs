import json
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

from ats_agent.evidence import EvidenceSource, build_evidence_ledger
from ats_agent.requirements import extract_requirements, map_requirements
from ats_agent.rewriting import propose_supported_changes
from ats_agent.validation import validate_change
from ats_agent.workflow import apply_manifest, build_proposal


class IntelligenceTests(unittest.TestCase):
    def test_extracts_postfixed_required_language_and_hard_gates(self):
        requirements = extract_requirements(
            "Python is required. Candidates need 3+ years of experience. "
            "Applicants must be authorized to work in India; no sponsorship is available."
        )
        by_kind = {item["kind"]: item for item in requirements}
        self.assertEqual(by_kind["skill"]["importance"], "mandatory")
        self.assertEqual(by_kind["experience_years"]["minimum_years"], 3)
        self.assertEqual(by_kind["work_authorization"]["importance"], "mandatory")
        self.assertEqual(by_kind["sponsorship"]["value"], "unavailable")
        self.assertTrue(all(item["source_span"]["end"] > item["source_span"]["start"] for item in requirements))

    def test_maps_requirement_to_traceable_candidate_evidence(self):
        ledger = build_evidence_ledger(
            "candidate-a",
            [
                EvidenceSource(
                    source="resume",
                    source_file="resume.txt",
                    text="- Helped build automated order workflows with 42 tests.",
                )
            ],
        )
        requirements = extract_requirements("Workflow automation experience is required.")
        matches = map_requirements(requirements, ledger)
        workflow_match = next(item for item in matches if "workflow automation" in item["normalized_terms"])
        self.assertIn(workflow_match["coverage"], {"direct", "transferable"})
        self.assertEqual(workflow_match["evidence_ids"], [ledger.items[0].id])
        self.assertEqual(ledger.items[0].candidate_id, "candidate-a")
        self.assertEqual(ledger.items[0].source_file, "resume.txt")
        self.assertEqual(ledger.items[0].ownership, "contributor")

    def test_rewrite_preserves_ownership_and_surfaces_supported_language(self):
        cv = "SUMMARY\n- Helped build automated order workflows with 42 tests.\n"
        ledger = build_evidence_ledger(
            "candidate-a",
            [EvidenceSource(source="resume", source_file="resume.txt", text=cv)],
        )
        requirements = extract_requirements("Workflow automation experience is required.")
        matches = map_requirements(requirements, ledger)
        changes = propose_supported_changes(cv, requirements, matches, ledger)
        supported = [item for item in changes if item["supported"]]
        self.assertTrue(supported)
        replacement = supported[0]["replacement_text"]
        self.assertIn("Contributed to", replacement)
        self.assertIn("workflow automation", replacement.lower())
        self.assertNotIn("Led", replacement)
        self.assertNotEqual(replacement.split()[0], "Built")
        self.assertEqual(supported[0]["evidence_ids"], [ledger.items[0].id])

    def test_validator_blocks_ownership_escalation(self):
        ledger = build_evidence_ledger(
            "candidate-a",
            [
                EvidenceSource(
                    source="resume",
                    source_file="resume.txt",
                    text="- Helped build a Python workflow with 42 tests.",
                )
            ],
        )
        change = {
            "id": "C1",
            "expected_text": "Helped build a Python workflow with 42 tests.",
            "replacement_text": "Led a Python workflow with 42 tests.",
            "evidence_ids": [ledger.items[0].id],
            "supported": True,
        }
        with self.assertRaisesRegex(ValueError, "ownership escalation"):
            validate_change(change, ledger)

    def test_workflow_includes_external_evidence_and_requirement_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume = root / "resume.txt"
            job = root / "job.md"
            project_bank = root / "project-bank.md"
            resume.write_text("SUMMARY\n- Contributed to an AI operations project.\n", encoding="utf-8")
            job.write_text("Python workflow automation experience is required.", encoding="utf-8")
            project_bank.write_text(
                "- Built Python-based automated procurement workflows validated through 153 tests.\n",
                encoding="utf-8",
            )
            proposal = build_proposal(resume, job, evidence_paths=[project_bank], candidate_id="candidate-a")
            self.assertEqual(proposal["status"], "draft")
            self.assertTrue(any(item["source_file"].endswith("project-bank.md") for item in proposal["evidence_ledger"]))
            python_mapping = next(
                item for item in proposal["requirement_evidence"] if "python" in item["normalized_terms"]
            )
            self.assertIn(python_mapping["coverage"], {"direct", "transferable"})
            self.assertTrue(python_mapping["evidence_ids"])

    def test_apply_rejects_unknown_evidence_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "resume.txt"
            source.write_text("SUMMARY\nContributed to Python workflows.\n", encoding="utf-8")
            proposal = root / "proposal.json"
            proposal.write_text(
                json.dumps(
                    {
                        "status": "draft",
                        "source": str(source),
                        "source_sha256": sha256(source.read_bytes()).hexdigest(),
                        "evidence_ledger": [],
                        "changes": [
                            {
                                "id": "C1",
                                "supported": True,
                                "evidence_ids": ["E999"],
                                "expected_text": "Contributed",
                                "replacement_text": "Built",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            manifest = root / "approved.json"
            manifest.write_text(
                json.dumps({"proposal": str(proposal), "approved_change_ids": ["C1"]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "unknown evidence IDs"):
                apply_manifest(manifest, ["C1"])


if __name__ == "__main__":
    unittest.main()
