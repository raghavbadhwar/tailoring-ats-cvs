from __future__ import annotations

import difflib
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .agents import career_report
from .docx_patch import patch_docx
from .evidence import EvidenceItem, EvidenceLedger, EvidenceSource, build_evidence_ledger
from .formatting import audit_file, audit_text
from .ingestion import ExtractionError, load, write_docx
from .requirements import extract_requirements, map_requirements
from .rewriting import propose_supported_changes
from .validation import validate_change


def _absolute(path: Path) -> Path:
    return path.expanduser().resolve()


def _load_evidence_sources(paths: Iterable[Path]) -> list[EvidenceSource]:
    sources: list[EvidenceSource] = []
    for path in paths:
        loaded = load(path)
        sources.append(
            EvidenceSource(
                source="supporting",
                source_file=str(path),
                text=loaded["text"],
            )
        )
    return sources


def build_proposal(
    resume: Path,
    job_description: Path,
    evidence_paths: Iterable[Path] | None = None,
    candidate_id: str = "candidate",
) -> dict[str, Any]:
    resume = _absolute(resume)
    job_description = _absolute(job_description)
    evidence_paths = [_absolute(path) for path in (evidence_paths or [])]
    try:
        cv = load(resume)
        jd = load(job_description)
        sources = [
            EvidenceSource(
                source="resume",
                source_file=str(resume),
                text=cv["text"],
            ),
            *_load_evidence_sources(evidence_paths),
        ]
    except ExtractionError as exc:
        return {
            "schema_version": 3,
            "status": "blocked",
            "reason": str(exc),
            "source": str(resume),
            "job_description": str(job_description),
        }

    ledger = build_evidence_ledger(candidate_id, sources)
    requirements = extract_requirements(jd["text"])
    requirement_evidence = map_requirements(requirements, ledger)
    changes = propose_supported_changes(
        cv["text"],
        requirements,
        requirement_evidence,
        ledger,
    )
    report = career_report(cv["text"], jd["text"])
    report["evidence_summary"] = {
        "candidate_id": candidate_id,
        "items": len(ledger.items),
        "supporting_files": [str(path) for path in evidence_paths],
    }

    return {
        "schema_version": 3,
        "status": "draft",
        "candidate_id": candidate_id,
        "source": str(resume),
        "job_description": str(job_description),
        "source_sha256": cv["sha256"],
        "job_description_sha256": jd["sha256"],
        "evidence_ledger": ledger.to_dicts(),
        "requirements": requirements,
        "requirement_evidence": requirement_evidence,
        "changes": changes,
        "report": report,
        "formatting": audit_file(str(resume)),
    }


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_from(parent: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (parent / path).resolve()


def _ledger_from_proposal(proposal: dict[str, Any]) -> EvidenceLedger:
    records = proposal.get("evidence_ledger")
    if not isinstance(records, list):
        raise ValueError("proposal has no evidence ledger")
    items: list[EvidenceItem] = []
    for record in records:
        try:
            items.append(EvidenceItem(**record))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid evidence record: {record!r}") from exc
    return EvidenceLedger(
        candidate_id=str(proposal.get("candidate_id") or "candidate"),
        items=tuple(items),
    )


def _default_output(source: Path) -> Path:
    suffix = source.suffix or ".txt"
    return source.with_name(f"{source.stem}.tailored{suffix}")


def _write_output(
    source: Path,
    output: Path,
    text: str,
    applied: list[dict[str, Any]],
    requested_mode: str | None,
) -> str:
    source_suffix = source.suffix.lower()
    output_suffix = output.suffix.lower()
    mode = (requested_mode or "").strip().lower()

    if output_suffix == ".pdf":
        raise ValueError(
            "PDF output requires a genuine PDF renderer; choose DOCX or text output"
        )
    if mode not in {"", "preserve", "rebuild", "text"}:
        raise ValueError(f"unknown document_mode: {requested_mode}")
    if mode == "preserve" and not (
        source_suffix == ".docx" and output_suffix == ".docx"
    ):
        raise ValueError("preserve mode requires DOCX input and DOCX output")

    output.parent.mkdir(parents=True, exist_ok=True)
    if source_suffix == ".docx" and output_suffix == ".docx" and mode != "rebuild":
        patch_docx(source, output, applied)
        return "preserve"
    if output_suffix == ".docx":
        write_docx(output, text)
        return "rebuild"

    output.write_text(text, encoding="utf-8")
    return "text"


def apply_manifest(manifest_path: Path, approved: list[str]) -> dict[str, Any]:
    manifest_path = manifest_path.expanduser().resolve()
    manifest: dict[str, Any] = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )
    proposal_path = _resolve_from(manifest_path.parent, manifest.get("proposal"))
    proposal: dict[str, Any] = (
        json.loads(proposal_path.read_text(encoding="utf-8"))
        if proposal_path
        else manifest
    )
    if proposal.get("status") == "blocked":
        raise ValueError(proposal.get("reason", "proposal is blocked"))
    if not isinstance(approved, list) or not all(
        isinstance(item, str) for item in approved
    ):
        raise ValueError("approved_change_ids must be a list of strings")

    source = _resolve_from(
        proposal_path.parent if proposal_path else manifest_path.parent,
        proposal.get("source"),
    )
    if source is None:
        raise ValueError("proposal has no source path")
    if proposal.get("source_sha256") and proposal["source_sha256"] != _sha(source):
        raise ValueError("stale proposal: source hash no longer matches")

    ledger = _ledger_from_proposal(proposal)
    changes = {change["id"]: change for change in proposal.get("changes", [])}
    unknown = [item for item in approved if item not in changes]
    if unknown:
        raise ValueError(f"unknown approved change IDs: {', '.join(unknown)}")

    text = load(source)["text"]
    original = text
    applied: list[dict[str, Any]] = []
    for change_id in approved:
        change = changes[change_id]
        validate_change(change, ledger)
        if change.get("operation") not in {None, "replace", "replace_span"}:
            raise ValueError(
                f"change {change_id} uses unsupported operation: "
                f"{change.get('operation')}"
            )
        expected = str(change.get("expected_text", change.get("from", "")))
        replacement = str(change.get("replacement_text", change.get("to", "")))
        matches = [
            index
            for index in range(len(text))
            if text.startswith(expected, index)
        ]
        if len(matches) == 0:
            raise ValueError(f"change {change_id} expected text was not found")
        if len(matches) > 1:
            raise ValueError(f"change {change_id} is ambiguous: {len(matches)} matches")
        start = matches[0]
        text = text[:start] + replacement + text[start + len(expected) :]
        applied.append(
            {
                "id": change_id,
                "status": "applied",
                "expected_text": expected,
                "replacement_text": replacement,
                "evidence_ids": list(change.get("evidence_ids", [])),
                "start": start,
                "end": start + len(replacement),
            }
        )

    if text == original:
        raise ValueError("approved changes produced no output change")

    output_value = manifest.get("output")
    output = (
        _resolve_from(manifest_path.parent, output_value)
        if output_value
        else _default_output(source)
    )
    if output is None:
        raise ValueError("could not determine output path")
    if output.resolve() == source.resolve():
        raise ValueError("output must not overwrite the source")

    document_mode = _write_output(
        source,
        output,
        text,
        applied,
        manifest.get("document_mode"),
    )

    output_text = load(output)["text"]
    if output_text != text:
        raise ValueError("output verification failed after document write")
    diff = "".join(
        difflib.unified_diff(
            original.splitlines(True),
            text.splitlines(True),
            fromfile=str(source),
            tofile=str(output),
        )
    )
    validation = {
        "path": str(output),
        "status": "audited",
        **audit_text(output_text),
    }
    result = {
        "status": "applied",
        "approved_change_ids": [item["id"] for item in applied],
        "applied_changes": applied,
        "source": str(source),
        "output": str(output),
        "document_mode": document_mode,
        "source_overwrite": False,
        "source_sha256": _sha(source),
        "output_sha256": _sha(output),
        "diff": diff,
        "validation": validation,
    }
    log = output.with_suffix(output.suffix + ".applied.json")
    log.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
