from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents/skills/tailor-cv/scripts/summarize_proposal.py"


def load_module():
    spec = importlib.util.spec_from_file_location("summarize_proposal", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProposalSummaryTests(unittest.TestCase):
    def test_summary_excludes_source_path(self) -> None:
        proposal = {"schema_version": 5, "status": "draft", "proposal_id": "P1", "proposal_digest": "a" * 64, "source": "/private/resume.docx", "hard_gates": [], "requirement_evidence": [], "changes": [{"id": "C1", "supported": True, "variants": []}, {"id": "C2", "supported": False}]}
        summary = load_module().summarize(proposal)
        self.assertEqual(summary["supported_change_ids"], ["C1"])
        self.assertEqual(summary["unsupported_gap_ids"], ["C2"])
        self.assertNotIn("/private/resume.docx", str(summary))
