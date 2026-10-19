import json
from pathlib import Path

import pytest

from ats_agent.workflow import apply_manifest, build_proposal


def test_tampered_v1_proposal_and_stale_jd_are_rejected(tmp_path: Path) -> None:
    resume, jd = tmp_path / "resume.txt", tmp_path / "job.md"
    resume.write_text("PROJECTS\nHelped build automated workflows with 42 tests.\n", encoding="utf-8")
    jd.write_text("Workflow automation is required.", encoding="utf-8")
    proposal = build_proposal(resume, jd, candidate_id="candidate-a")
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
    manifest = {"schema_version": 2, "proposal": str(proposal_path), "proposal_digest": proposal["proposal_digest"], "selections": [{"change_id": "C1", "variant_id": "balanced"}], "output": str(tmp_path / "tailored.txt")}
    manifest_path = tmp_path / "approval.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    jd.write_text("Kubernetes is required.", encoding="utf-8")
    with pytest.raises(ValueError, match="stale artifact"):
        apply_manifest(manifest_path)
