from __future__ import annotations

import difflib
import hashlib
import json
from pathlib import Path

from .agents import career_report, proposals
from .formatting import audit_file
from .ingestion import ExtractionError, load, write_docx


def build_proposal(resume: Path, job_description: Path) -> dict:
    try:
        cv = load(resume)
        jd = load(job_description)
    except ExtractionError as exc:
        return {"schema_version": 2, "status": "blocked", "reason": str(exc), "source": str(resume), "job_description": str(job_description)}
    report = career_report(cv["text"], jd["text"])
    return {"schema_version": 2, "status": "draft", "source": str(resume), "job_description": str(job_description), "source_sha256": cv["sha256"], "job_description_sha256": jd["sha256"], "changes": proposals(cv["text"], jd["text"], report), "report": report, "formatting": audit_file(str(resume))}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply_manifest(manifest_path: Path, approved: list[str]) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    proposal_path = manifest.get("proposal")
    proposal = json.loads(Path(proposal_path).read_text(encoding="utf-8")) if proposal_path else manifest
    if proposal.get("status") == "blocked":
        raise ValueError(proposal.get("reason", "proposal is blocked"))
    if not isinstance(approved, list) or not all(isinstance(item, str) for item in approved):
        raise ValueError("approved_change_ids must be a list of strings")
    source = Path(proposal["source"])
    if proposal.get("source_sha256") and proposal["source_sha256"] != _sha(source):
        raise ValueError("stale proposal: source hash no longer matches")
    changes = {change["id"]: change for change in proposal.get("changes", [])}
    unknown = [item for item in approved if item not in changes]
    if unknown:
        raise ValueError(f"unknown approved change IDs: {', '.join(unknown)}")
    text = load(source)["text"]
    original = text
    applied = []
    for change_id in approved:
        change = changes[change_id]
        if not change.get("supported") or not change.get("evidence_ids"):
            raise ValueError(f"change {change_id} is unsupported or has no evidence references")
        expected = change.get("expected_text", change.get("from", ""))
        replacement = change.get("replacement_text", change.get("to", ""))
        if not expected:
            raise ValueError(f"change {change_id} has no exact expected text")
        matches = [i for i in range(len(text)) if text.startswith(expected, i)]
        if len(matches) == 0:
            raise ValueError(f"change {change_id} expected text was not found")
        if len(matches) > 1:
            raise ValueError(f"change {change_id} is ambiguous: {len(matches)} matches")
        start = matches[0]
        if expected == replacement:
            raise ValueError(f"change {change_id} is a no-op")
        text = text[:start] + replacement + text[start + len(expected):]
        applied.append({"id": change_id, "status": "applied", "expected_text": expected, "replacement_text": replacement, "start": start, "end": start + len(replacement)})
    if text == original:
        raise ValueError("approved changes produced no output change")
    output = Path(manifest.get("output") or (str(source) + ".approved" + (".docx" if source.suffix.lower() == ".docx" else "")))
    if output.resolve() == source.resolve():
        raise ValueError("output must not overwrite the source")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() == ".docx":
        write_docx(output, text)
    else:
        output.write_text(text, encoding="utf-8")
    diff = "".join(difflib.unified_diff(original.splitlines(True), text.splitlines(True), fromfile=str(source), tofile=str(output)))
    result = {"status": "applied", "approved_change_ids": [item["id"] for item in applied], "applied_changes": applied, "source": str(source), "output": str(output), "source_overwrite": False, "source_sha256": _sha(source), "output_sha256": _sha(output), "diff": diff, "validation": audit_file(str(output))}
    log = output.with_suffix(output.suffix + ".applied.json")
    log.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
