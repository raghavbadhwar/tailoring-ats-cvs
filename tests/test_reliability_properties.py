"""Reliability properties: fuzzed honesty invariants and provider injection.

The fuzz invariant is the strongest regression net for the product's core
promise: no matter how hostile or random the job description, an applied
output may never contain a claim that the candidate's evidence does not
support.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"

try:
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st

    HAVE_HYPOTHESIS = True
except ImportError:  # pragma: no cover - dev extra missing
    HAVE_HYPOTHESIS = False

from ats_agent.orchestrator import tailor  # noqa: E402
from ats_agent.validation import validate_changes  # noqa: E402

JD_VOCAB = [
    "sql", "power bi", "tableau", "aws", "a/b testing", "kubernetes",
    "bachelor", "phd", "5 years experience", "docker", "gcp",
]
FILLER = (
    "We are hiring an intern to join our analytics team. "
    "You will build dashboards and partner with stakeholders. "
)


@unittest.skipUnless(HAVE_HYPOTHESIS, "hypothesis is not installed")
class HonestyPropertyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    @settings(max_examples=50, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    @given(st.lists(st.sampled_from(JD_VOCAB), min_size=1, max_size=8))
    def test_applied_output_never_gains_unsupported_terms(self, demands):
        """Applied output must never contain terms absent from CV + evidence."""

        banned_probe = "quantumblockchainledger"
        jd_text = FILLER + " ".join(
            f"{term} is required. " for term in demands
        ) + f" {banned_probe} expertise mandatory."
        cv = EXAMPLES / "sample_resume.txt"
        evidence = EXAMPLES / "sample_project_bank.md"
        run_dir = Path(self.tmp.name) / f"run-{abs(hash(tuple(demands)))}"
        approvals = Path(self.tmp.name) / "approvals.json"
        approvals.write_text(json.dumps({"*": ["*"]}), encoding="utf-8")

        payload = tailor(
            cv, jd_text,
            candidate_id="fuzz-candidate",
            run_dir=run_dir,
            evidence_paths=[evidence],
            approve_from=approvals,
            writer=lambda _text: None,
            verify_live=False,
        )
        for outcome in payload["outcomes"]:
            if outcome["status"] != "tailored":
                continue
            output_text = Path(outcome["output_document"]).read_text(encoding="utf-8").lower()
            self.assertNotIn(banned_probe.lower(), output_text)
            for term in demands:
                term_l = term.lower()
                in_source = (
                    term_l in cv.read_text(encoding="utf-8").lower()
                    or term_l in evidence.read_text(encoding="utf-8").lower()
                )
                if not in_source:
                    self.assertNotIn(term_l, output_text,
                                     f"fabricated '{term}' appeared in output")


class ProviderInjectionTests(unittest.TestCase):
    """A hostile rewrite provider cannot smuggle fabricated claims through."""

    def test_malicious_provider_output_is_blocked_by_validation(self):
        from ats_agent.evidence import EvidenceItem, EvidenceLedger
        item = EvidenceItem(
            id="E1", candidate_id="c", text="Built dashboards",
            source="resume", source_file="cv.txt", source_span="line 1",
            line_number=1, paragraph_index=None, part="text", ownership="direct",
        )
        ledger = EvidenceLedger("c", (item,))
        change = {
            "id": "C1", "kind": "surface-evidence", "operation": "insert_after",
            "anchor": {"part": "text", "line_number": 1},
            "target_section": "projects", "expected_text": "",
            "replacement_text": "Ran enterprise A/B testing on Kubernetes clusters at scale",
            "variants": [{"id": "conservative",
                          "text": "Ran enterprise A/B testing on Kubernetes clusters at scale"}],
            "evidence_ids": ["E1"], "supported": True,
            "ownership_before": "direct", "terms_introduced": ["a/b testing"],
        }
        with self.assertRaises(ValueError):
            validate_changes([change], ledger)


if __name__ == "__main__":
    unittest.main()
