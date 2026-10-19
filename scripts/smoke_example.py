"""Run the synthetic example through PROPOSE -> APPROVE -> APPLY -> VALIDATE."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from ats_agent.ingestion import extract
from ats_agent.reports import write_review_bundle
from ats_agent.workflow import apply_manifest, build_proposal

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        run = Path(directory)
        resume = run / "sample_resume.txt"
        job = run / "sample_job.md"
        evidence = run / "sample_evidence.md"
        shutil.copy2(EXAMPLES / resume.name, resume)
        shutil.copy2(EXAMPLES / job.name, job)
        shutil.copy2(EXAMPLES / evidence.name, evidence)

        proposal = build_proposal(
            resume,
            job,
            candidate_id="sample-candidate",
            evidence_paths=[evidence],
        )
        if proposal.get("status") != "draft":
            raise RuntimeError("example proposal was blocked: %s" % proposal.get("reason"))
        supported = [item for item in proposal.get("changes", []) if item.get("supported")]
        if not supported:
            raise RuntimeError("example produced no evidence-backed changes")

        bundle = write_review_bundle(proposal, run / "review")
        proposal_path = Path(bundle["proposal"])
        output = run / "sample_resume.tailored.txt"
        first = supported[0]
        manifest = run / "approval-manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "proposal": str(proposal_path),
                    "approved_change_ids": [first["id"]],
                    "selected_variants": {first["id"]: "balanced"},
                    "output": str(output),
                    "output_mode": "preserve",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        result = apply_manifest(manifest)
        if result.get("status") != "applied":
            raise RuntimeError("example apply did not complete")
        if not output.exists() or output.read_bytes() == resume.read_bytes():
            raise RuntimeError("example output is missing or unchanged")
        if result.get("validation", {}).get("status") != "passed":
            raise RuntimeError("example output validation failed")
        if not Path(str(output) + ".applied.json").exists():
            raise RuntimeError("example applied-change log is missing")
        extract(output)
        print(json.dumps({"status": "passed", "approved_change": first["id"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
