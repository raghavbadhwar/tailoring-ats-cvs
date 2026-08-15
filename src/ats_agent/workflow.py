from __future__ import annotations

import json
import shutil
from pathlib import Path

from .agents import career_report, proposals
from .formatting import audit_file


def build_proposal(resume: Path, job_description: Path) -> dict:
    cv = resume.read_text(encoding="utf-8", errors="replace")
    jd = job_description.read_text(encoding="utf-8", errors="replace")
    report = career_report(cv, jd)
    return {"schema_version": 1, "status": "draft", "source": str(resume), "job_description": str(job_description), "changes": proposals(cv, jd, report), "report": report, "formatting": audit_file(str(resume))}


def apply_manifest(manifest_path: Path, approved: list[str]) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(approved, list) or not all(isinstance(item, str) for item in approved):
        raise ValueError("approved_change_ids must be a list of strings")
    proposal_path = manifest.get("proposal")
    proposal = json.loads(Path(proposal_path).read_text(encoding="utf-8")) if proposal_path else manifest
    changes = {change["id"]: change for change in proposal.get("changes", [])}
    unknown = [item for item in approved if item not in changes]
    if unknown:
        raise ValueError(f"unknown approved change IDs: {', '.join(unknown)}")
    source = Path(proposal["source"])
    output = Path(manifest.get("output") or (str(source) + ".approved"))
    text = source.read_text(encoding="utf-8", errors="replace")
    applied = []
    for change_id in approved:
        change = changes[change_id]
        if not change.get("evidence"):
            raise ValueError(f"change {change_id} has no verified evidence")
        if change.get("from"):
            text = text.replace(change["from"], change["to"])
        applied.append(change_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, output)
    output.write_text(text, encoding="utf-8")
    return {"status": "applied", "approved_change_ids": applied, "source": str(source), "output": str(output), "source_overwrite": False, "validation": audit_file(str(output))}
