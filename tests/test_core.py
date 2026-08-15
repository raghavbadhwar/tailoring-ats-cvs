import json
import tempfile
import unittest
from pathlib import Path

from ats_agent.evidence import EvidenceSource, build_evidence_ledger
from ats_agent.requirements import extract_requirements, map_requirements, evaluate_hard_gates
from ats_agent.rewriting import propose_supported_changes
from ats_agent.validation import validate_change


class CoreTests(unittest.TestCase):
    def test_evidence_ids_are_candidate_scoped_and_unknown_ids_block(self):
        ledger = build_evidence_ledger(
            "candidate-a",
            [EvidenceSource(source="resume", source_file="resume.txt", text="- Contributed to Python workflow automation with 42 tests.")],
        )
        self.assertTrue(ledger.items)
        self.assertEqual(ledger.items[0].candidate_id, "candidate-a")
        with self.assertRaisesRegex(ValueError, "unknown evidence IDs"):
            ledger.require(["E999"])

    def test_ownership_is_not_escalated_by_rewrite(self):
        cv = "PROJECTS\n- Helped build automated order workflows with 42 tests.\n"
        ledger = build_evidence_ledger(
            "candidate-a",
            [EvidenceSource(source="resume", source_file="resume.txt", text=cv)],
        )
        requirements = extract_requirements("Workflow automation and Python are required.")
        matches = map_requirements(requirements, ledger)
        changes = propose_supported_changes(cv, requirements, matches, ledger)
        change = next(item for item in changes if item.get("supported"))
        texts = [variant["text"] for variant in change["variants"]]
        self.assertTrue(all("Led" not in text and not text.startswith("Built") for text in texts))
        self.assertTrue(any("workflow automation" in text.lower() for text in texts))
        for variant in change["variants"]:
            candidate = {**change, "replacement_text": variant["text"]}
            validate_change(candidate, ledger)

    def test_supporting_evidence_can_be_surfaced_without_copying_other_candidate(self):
        resume = "PROJECTS\n- Contributed to an AI operations prototype.\nSKILLS\nExcel\n"
        ledger = build_evidence_ledger(
            "candidate-a",
            [
                EvidenceSource(source="resume", source_file="resume.txt", text=resume),
                EvidenceSource(source="supporting", source_file="project-bank.md", text="- Built Python workflow automation for procurement, validated through 153 tests."),
            ],
        )
        requirements = extract_requirements("Python and workflow automation are required.")
        matches = map_requirements(requirements, ledger)
        changes = propose_supported_changes(resume, requirements, matches, ledger)
        surfaced = [c for c in changes if c["kind"] == "surface-evidence" and c["supported"]]
        self.assertTrue(surfaced)
        self.assertTrue(any("Python" in v["text"] for c in surfaced for v in c["variants"]))
        self.assertTrue(all(c["evidence_ids"] for c in surfaced))

    def test_validator_blocks_new_numbers_and_production_claims(self):
        ledger = build_evidence_ledger(
            "candidate-a",
            [EvidenceSource(source="resume", source_file="resume.txt", text="- Contributed to a Python prototype with 42 tests.")],
        )
        item = ledger.items[0]
        base = {
            "id": "C1",
            "supported": True,
            "evidence_ids": [item.id],
            "expected_text": item.text,
        }
        with self.assertRaisesRegex(ValueError, "unsupported numeric"):
            validate_change({**base, "replacement_text": "Contributed to a Python prototype with 500 tests."}, ledger)
        with self.assertRaisesRegex(ValueError, "protected status"):
            validate_change({**base, "replacement_text": "Contributed to a production Python platform with 42 tests."}, ledger)

    def test_hard_gate_extraction_and_evaluation(self):
        requirements = extract_requirements(
            "Applicants must graduate in 2027, hold a bachelor's degree, have at least 2 years of experience, and be authorized to work in India. No sponsorship is available."
        )
        kinds = {item["kind"] for item in requirements}
        self.assertTrue({"graduation_year", "degree", "experience_years", "work_authorization", "sponsorship"}.issubset(kinds))
        ledger = build_evidence_ledger(
            "candidate-a",
            [EvidenceSource(source="resume", source_file="resume.txt", text="EDUCATION\nBachelor of Commerce (Honours), Expected 2027\nEXPERIENCE\n- Completed 1 year of internship experience.\n")],
        )
        gates = evaluate_hard_gates(requirements, ledger)
        experience = next(g for g in gates if g["kind"] == "experience_years")
        self.assertEqual(experience["status"], "unmet")
        graduation = next(g for g in gates if g["kind"] == "graduation_year")
        self.assertEqual(graduation["status"], "met")


if __name__ == "__main__":
    unittest.main()
