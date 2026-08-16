from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ats_agent.evidence import build_evidence_ledger
from ats_agent.models import ProposedChange
from ats_agent.validation import ValidationError, validate_proposed_change
from ats_agent.workflow import apply_manifest, build_proposal


class SectionAndEvidenceRegressionTests(unittest.TestCase):
    def test_title_case_projects_section_without_literal_bullet_is_rewritten(self):
        cv = (
            "Raghav Sample\n"
            "Projects\n"
            "Helped build a Python workflow validated through 42 tests.\n"
            "Skills\n"
            "Python\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume = root / "resume.txt"
            jd = root / "job.md"
            resume.write_text(cv, encoding="utf-8")
            jd.write_text(
                "Python workflow automation and testing experience are required for this role.",
                encoding="utf-8",
            )
            proposal = build_proposal(resume, jd, candidate_id="candidate-a")
        self.assertEqual(proposal["status"], "draft")
        self.assertTrue(proposal["changes"])
        self.assertEqual(proposal["changes"][0]["target_section"], "projects")
        self.assertIn("workflow automation", proposal["changes"][0]["replacement_text"].lower())

    def test_valid_but_unrelated_evidence_cannot_authorize_a_change(self):
        ledger = build_evidence_ledger(
            "Projects\n"
            "Contributed to a Python workflow.\n"
            "Contributed to market sizing research.\n",
            candidate_id="candidate-a",
            source="resume.txt",
        )
        records = list(ledger)
        python_record = next(item for item in records if "Python" in item.text)
        market_record = next(item for item in records if "market sizing" in item.text)
        change = ProposedChange.from_dict(
            {
                "id": "C1",
                "operation": "replace_span",
                "expected_text": python_record.text,
                "replacement_text": "Contributed to a Python workflow automation system.",
                "evidence_ids": [market_record.id],
                "supported": True,
                "reason": "malformed manual proposal",
            }
        )
        with self.assertRaisesRegex(ValidationError, "exact edited source span"):
            validate_proposed_change(change, ledger)


class StaleContextRegressionTests(unittest.TestCase):
    def _prepare(self, root: Path) -> tuple[Path, Path, Path, Path, dict]:
        resume = root / "resume.txt"
        jd = root / "job.md"
        evidence = root / "evidence.md"
        proposal_path = root / "proposal.json"
        resume.write_text(
            "Projects\nHelped build a Python workflow validated through 42 tests.\n",
            encoding="utf-8",
        )
        jd.write_text(
            "Python workflow automation and testing experience are required for this role.",
            encoding="utf-8",
        )
        evidence.write_text(
            "Candidate Evidence\nThe candidate supported workflow testing and did not lead the project.\n",
            encoding="utf-8",
        )
        proposal = build_proposal(
            resume,
            jd,
            candidate_id="candidate-a",
            evidence_paths=[evidence],
        )
        supported = next(item for item in proposal["changes"] if item["supported"])
        proposal_path.write_text(json.dumps(proposal, indent=2), encoding="utf-8")
        manifest = root / "approval.json"
        manifest.write_text(
            json.dumps(
                {
                    "proposal": str(proposal_path),
                    "approved_change_ids": [supported["id"]],
                    "selected_variants": {supported["id"]: "balanced"},
                    "output": str(root / "tailored.txt"),
                }
            ),
            encoding="utf-8",
        )
        return resume, jd, evidence, manifest, proposal

    def test_changed_job_description_blocks_old_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _resume, jd, _evidence, manifest, proposal = self._prepare(root)
            jd.write_text(jd.read_text(encoding="utf-8") + "\nKubernetes is mandatory.\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "job description hash"):
                apply_manifest(manifest, [proposal["changes"][0]["id"]])

    def test_changed_supplemental_evidence_blocks_old_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _resume, _jd, evidence, manifest, proposal = self._prepare(root)
            evidence.write_text(evidence.read_text(encoding="utf-8") + "\nChanged after proposal.\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "supplemental evidence 1 hash"):
                apply_manifest(manifest, [proposal["changes"][0]["id"]])


if __name__ == "__main__":
    unittest.main()
