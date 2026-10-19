from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ats_agent.hashing import verify_proposal_digest
from ats_agent.review import write_review_bundle
from ats_agent.workflow import apply_manifest, build_proposal


class ProposalHashBindingTests(unittest.TestCase):
    def _prepare(self, root: Path) -> dict[str, object]:
        resume = root / "resume.txt"
        job = root / "job.md"
        evidence = root / "evidence.md"
        company = root / "company.md"
        proposal_path = root / "proposal.json"
        manifest_path = root / "approval.json"

        resume.write_text(
            "PROJECTS\n- Helped build automated order workflows with 42 tests.\n",
            encoding="utf-8",
        )
        job.write_text(
            "Workflow automation experience is required for this product operations role.",
            encoding="utf-8",
        )
        evidence.write_text(
            "CANDIDATE EVIDENCE\n- Contributed to automated procurement workflows and validated them through 42 tests.\n",
            encoding="utf-8",
        )
        company.write_text(
            "Official company context describes careful product operations, human review, reliable systems, and accountable execution.",
            encoding="utf-8",
        )

        proposal = build_proposal(
            resume,
            job,
            evidence_paths=[evidence],
            candidate_id="candidate-a",
            company_context=company,
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
                    "proposal_digest": proposal.get(
                        "proposal_digest",
                        "missing",
                    ),
                    "selections": [
                        {
                            "change_id": change["id"],
                            "variant_id": variant_id,
                        }
                    ],
                    "approved_change_ids": [change["id"]],
                    "document_mode": "preserve",
                    "output": str(root / "tailored.txt"),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return {
            "resume": resume,
            "job": job,
            "evidence": evidence,
            "company": company,
            "proposal": proposal,
            "proposal_path": proposal_path,
            "manifest": manifest_path,
            "change": change,
            "variant_id": variant_id,
        }

    def test_proposal_fingerprints_every_input_and_has_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            case = self._prepare(Path(directory))
            proposal = case["proposal"]
            self.assertEqual(proposal["schema_version"], 5)
            artifacts = proposal["artifacts"]
            self.assertEqual(
                {item["kind"] for item in artifacts},
                {
                    "resume",
                    "job_description",
                    "candidate_evidence",
                    "company_context",
                },
            )
            self.assertTrue(
                all(len(item["sha256"]) == 64 for item in artifacts)
            )
            self.assertEqual(len(proposal["proposal_digest"]), 64)
            self.assertEqual(
                verify_proposal_digest(json.loads(json.dumps(proposal))),
                proposal["proposal_digest"],
            )
            self.assertTrue(proposal["coverage"]["baseline"])
            self.assertTrue(proposal["coverage"]["proposed_variants"])

    def test_full_review_bundle_persists_a_verifiable_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = self._prepare(root)
            paths = write_review_bundle(case["proposal"], root / "review")
            persisted = json.loads(Path(paths["proposal"]).read_text(encoding="utf-8"))
            self.assertEqual(verify_proposal_digest(persisted), case["proposal"]["proposal_digest"])

    def test_redacted_review_cannot_be_approved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = self._prepare(root)
            paths = write_review_bundle(case["proposal"], root / "review", redacted=True)
            redacted = json.loads(Path(paths["proposal"]).read_text(encoding="utf-8"))
            self.assertEqual(Path(paths["proposal"]).name, "proposal.redacted.json")
            with self.assertRaisesRegex(ValueError, "redacted"):
                from ats_agent.review import build_approval_manifest

                build_approval_manifest(
                    redacted,
                    proposal_filename="proposal.redacted.json",
                    selections=[(case["change"]["id"], case["variant_id"])],
                    output_document="tailored.txt",
                )

    def test_schema_v5_rejects_legacy_undigested_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = self._prepare(root)
            change = case["change"]
            manifest = case["manifest"]
            manifest.write_text(
                json.dumps(
                    {
                        "proposal": str(case["proposal_path"]),
                        "selections": [
                            {
                                "change_id": change["id"],
                                "variant_id": case["variant_id"],
                            }
                        ],
                        "output": str(root / "legacy.txt"),
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError,
                "digest-bound approval",
            ):
                apply_manifest(manifest)

    def test_changed_job_description_blocks_old_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            case = self._prepare(Path(directory))
            job = case["job"]
            job.write_text(
                job.read_text(encoding="utf-8")
                + "\nKubernetes is now mandatory.\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "job_description.*hash"):
                apply_manifest(case["manifest"])

    def test_changed_candidate_evidence_blocks_old_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            case = self._prepare(Path(directory))
            evidence = case["evidence"]
            evidence.write_text(
                evidence.read_text(encoding="utf-8")
                + "\nChanged after proposal creation.\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError,
                "candidate_evidence.*hash",
            ):
                apply_manifest(case["manifest"])

    def test_changed_company_context_blocks_old_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            case = self._prepare(Path(directory))
            company = case["company"]
            company.write_text(
                company.read_text(encoding="utf-8")
                + "\nContext changed after approval.\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError,
                "company_context.*hash",
            ):
                apply_manifest(case["manifest"])

    def test_edited_proposal_blocks_old_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            case = self._prepare(Path(directory))
            proposal_path = case["proposal_path"]
            proposal = json.loads(
                proposal_path.read_text(encoding="utf-8")
            )
            proposal["changes"][0]["reason"] = "tampered after review"
            proposal_path.write_text(
                json.dumps(proposal, indent=2),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "proposal digest"):
                apply_manifest(case["manifest"])


if __name__ == "__main__":
    unittest.main()
