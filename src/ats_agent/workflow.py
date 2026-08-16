"""PROPOSE → APPROVE → APPLY workflow with content-bound provenance."""
from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Iterable

from . import __version__
from .agents import career_report
from .artifacts import register_artifacts
from .documents import patch_document
from .evidence import (
    EvidenceLedger,
    EvidenceSource,
    SourceFragment,
    build_evidence_ledger,
)
from .formatting import audit_file, audit_text
from .hashing import (
    compute_proposal_digest,
    sha256_path,
    stable_id,
    verify_proposal_digest,
)
from .ingestion import ExtractionError, load
from .models import ApprovalManifest, ProposalEnvelope
from .requirements import (
    evaluate_hard_gates,
    extract_requirements,
    map_requirements,
)
from .rewriting import propose_supported_changes
from .validation import validate_change

SCHEMA_VERSION = 5
POLICY_VERSION = "evidence-policy-v1"
ONTOLOGY_VERSION = "requirements-v1"


def _absolute(path: Path) -> Path:
    return path.expanduser().resolve()


def _source_from_loaded(
    source: str,
    loaded: dict,
    candidate_id: str,
) -> EvidenceSource:
    return EvidenceSource(
        source=source,
        source_file=loaded["path"],
        text=loaded["body_text"],
        fragments=tuple(
            SourceFragment.from_mapping(fragment)
            for fragment in loaded["paragraphs"]
            if fragment["part"] in {"text", "word/document.xml"}
        ),
        verification_status="candidate_supplied",
        candidate_id=candidate_id,
    )


def build_proposal(
    resume: Path,
    job_description: Path,
    evidence_paths: Iterable[Path] | None = None,
    candidate_id: str = "candidate",
    company_context: Path | None = None,
) -> dict:
    """Build a typed, content-bound proposal without editing any source."""

    resume = _absolute(resume)
    job_description = _absolute(job_description)
    evidence_paths = [_absolute(path) for path in (evidence_paths or [])]
    company_context_path = (
        _absolute(company_context) if company_context is not None else None
    )
    try:
        cv = load(resume)
        jd = load(job_description)
        loaded_evidence = [load(path) for path in evidence_paths]
        company = load(company_context_path) if company_context_path else None
        artifacts = register_artifacts(
            resume=resume,
            job_description=job_description,
            evidence_paths=evidence_paths,
            company_context=company_context_path,
            candidate_id=candidate_id,
        )
    except (ExtractionError, OSError) as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "blocked",
            "reason": str(exc),
            "source": str(resume),
            "job_description": str(job_description),
        }

    sources = [_source_from_loaded("resume", cv, candidate_id)]
    sources.extend(
        _source_from_loaded("supporting", loaded, candidate_id)
        for loaded in loaded_evidence
    )
    ledger = build_evidence_ledger(candidate_id, sources)
    requirements = extract_requirements(jd["text"])
    mappings = map_requirements(requirements, ledger)
    hard_gates = evaluate_hard_gates(requirements, ledger)
    changes = propose_supported_changes(
        cv["body_text"],
        requirements,
        mappings,
        ledger,
    )
    report = career_report(
        cv["body_text"],
        jd["text"],
        ledger=ledger,
        requirements=requirements,
        mappings=mappings,
        hard_gates=hard_gates,
    )
    if company:
        report["agents"]["company_alignment"] = {
            "agent": "company-language-alignment",
            "source_status": "user-supplied-official-context",
            "source_file": company["path"],
            "vocabulary": sorted(set(company["text"].lower().split()))[:100],
            "note": (
                "Company terminology may only be used when supported by "
                "candidate evidence."
            ),
        }

    artifact_records = [
        artifact.model_dump(mode="json") for artifact in artifacts
    ]
    proposal_id = stable_id(
        "P",
        {
            "candidate_id": candidate_id,
            "artifacts": artifact_records,
            "policy_version": POLICY_VERSION,
            "ontology_version": ONTOLOGY_VERSION,
        },
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "draft",
        "proposal_id": proposal_id,
        "candidate_id": candidate_id,
        "artifacts": artifact_records,
        "policy_version": POLICY_VERSION,
        "ontology_version": ONTOLOGY_VERSION,
        "provider": "deterministic",
        "provider_version": __version__,
        "source": str(resume),
        "source_format": cv["format"],
        "job_description": str(job_description),
        "source_sha256": cv["sha256"],
        "job_description_sha256": jd["sha256"],
        "evidence_files": [str(path) for path in evidence_paths],
        "company_context": (
            str(company_context_path) if company_context_path else None
        ),
        "evidence_ledger": ledger.to_dicts(),
        "requirements": requirements,
        "requirement_evidence": mappings,
        "hard_gates": hard_gates,
        "changes": changes,
        "report": report,
        "formatting": audit_file(str(resume)),
        "input_diagnostics": {
            "resume": cv["quality"],
            "job_description": jd["quality"],
        },
    }
    payload["proposal_digest"] = compute_proposal_digest(payload)
    return ProposalEnvelope.model_validate(payload).model_dump(mode="json")


def _sha(path: Path) -> str:
    return sha256_path(path)


def _resolve_from(parent: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (parent / path).resolve()


def _ledger_from_proposal(proposal: dict) -> EvidenceLedger:
    records = proposal.get("evidence_ledger")
    if not isinstance(records, list):
        raise ValueError("proposal has no evidence ledger")
    return EvidenceLedger.from_dicts(
        str(proposal.get("candidate_id") or "candidate"),
        records,
    )


def _default_output(source: Path) -> Path:
    suffix = source.suffix.lower()
    if suffix == ".pdf":
        suffix = ".docx"
    elif not suffix:
        suffix = ".txt"
    return source.with_name(f"{source.stem}.tailored{suffix}")


def _selections(
    manifest: dict,
    approved: list[str],
    changes: dict[str, dict],
) -> list[dict]:
    raw = manifest.get("selections")
    if raw is not None:
        if not isinstance(raw, list):
            raise ValueError("selections must be a list")
        selections = []
        for item in raw:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("change_id"), str)
            ):
                raise ValueError("each selection requires change_id")
            selections.append(
                {
                    "change_id": item["change_id"],
                    "variant_id": item.get("variant_id"),
                }
            )
        return selections
    return [
        {"change_id": change_id, "variant_id": None}
        for change_id in approved
    ]


def _materialize_change(change: dict, variant_id: str | None) -> dict:
    variants = change.get("variants") or []
    if variants:
        target = variant_id or change.get("default_variant") or variants[0]["id"]
        matches = [
            variant for variant in variants if variant["id"] == target
        ]
        if len(matches) != 1:
            raise ValueError(f"change {change['id']} has no variant {target}")
        return {
            **change,
            "selected_variant": target,
            "replacement_text": matches[0]["text"],
        }
    return dict(change)


def _verify_artifacts(
    proposal: ProposalEnvelope,
    *,
    proposal_parent: Path,
) -> Path:
    resume_paths: list[Path] = []
    for artifact in proposal.artifacts:
        path = _resolve_from(proposal_parent, artifact.path)
        if path is None or not path.is_file():
            raise ValueError(
                f"stale proposal: {artifact.kind} artifact file is missing"
            )
        if _sha(path) != artifact.sha256:
            raise ValueError(
                f"stale proposal: {artifact.kind} artifact hash no longer matches"
            )
        if artifact.kind in {"resume", "candidate_evidence"}:
            if artifact.candidate_id != proposal.candidate_id:
                raise ValueError(
                    f"candidate identity mismatch for {artifact.kind}"
                )
        if artifact.kind == "resume":
            resume_paths.append(path)
    if len(resume_paths) != 1:
        raise ValueError("proposal must contain exactly one resume artifact")
    return resume_paths[0]


def apply_manifest(
    manifest_path: Path,
    approved: list[str] | None = None,
) -> dict:
    """Apply only selected changes after verifying proposal and every input."""

    manifest_path = manifest_path.expanduser().resolve()
    raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    approval = ApprovalManifest.model_validate(raw_manifest)
    manifest = approval.model_dump(
        mode="json",
        exclude_none=True,
        exclude_unset=True,
    )

    proposal_path = _resolve_from(
        manifest_path.parent,
        approval.proposal,
    )
    if proposal_path is None:
        raise ValueError("approval manifest has no proposal path")
    proposal_data = json.loads(proposal_path.read_text(encoding="utf-8"))
    if proposal_data.get("status") == "blocked":
        raise ValueError(
            proposal_data.get("reason", "proposal is blocked")
        )
    proposal_schema = int(proposal_data.get("schema_version", 0))
    if proposal_schema > SCHEMA_VERSION:
        raise ValueError("proposal schema version is newer than this runtime")

    verified_digest = verify_proposal_digest(proposal_data)
    if proposal_schema >= 5 and (
        approval.schema_version < 2 or approval.proposal_digest is None
    ):
        raise ValueError(
            "schema-v5 proposal requires a digest-bound approval"
        )
    if (
        approval.proposal_digest is not None
        and approval.proposal_digest != verified_digest
    ):
        raise ValueError(
            "proposal digest in approval manifest does not match proposal"
        )
    proposal = ProposalEnvelope.model_validate(proposal_data)
    source = _verify_artifacts(
        proposal,
        proposal_parent=proposal_path.parent,
    )
    if Path(proposal.source).expanduser().resolve() != source:
        raise ValueError("resume artifact path does not match proposal source")

    ledger = _ledger_from_proposal(proposal_data)
    change_list = proposal_data.get("changes") or []
    changes = {str(change["id"]): change for change in change_list}
    if len(changes) != len(change_list):
        raise ValueError("proposal contains duplicate change IDs")
    approved_ids = (
        approved
        if approved is not None
        else list(approval.approved_change_ids)
    )
    if not isinstance(approved_ids, list) or not all(
        isinstance(item, str) for item in approved_ids
    ):
        raise ValueError("approved_change_ids must be a list of strings")
    selections = _selections(manifest, approved_ids, changes)
    if not selections:
        raise ValueError("no changes were approved")
    unknown = [
        selection["change_id"]
        for selection in selections
        if selection["change_id"] not in changes
    ]
    if unknown:
        raise ValueError(
            "unknown approved change IDs: " + ", ".join(unknown)
        )

    materialized: list[dict] = []
    anchors: set[tuple] = set()
    for selection in selections:
        change = _materialize_change(
            changes[selection["change_id"]],
            selection.get("variant_id"),
        )
        validate_change(change, ledger)
        anchor = change.get("anchor") or {}
        conflict_key = (
            change.get("operation"),
            anchor.get("part"),
            anchor.get("paragraph_index"),
            anchor.get("line_number"),
            change.get("expected_text"),
        )
        if conflict_key in anchors:
            raise ValueError(
                "conflicting approved changes share an anchor: "
                + str(change["id"])
            )
        anchors.add(conflict_key)
        materialized.append(change)

    output = (
        _resolve_from(manifest_path.parent, approval.output)
        or _default_output(source)
    )
    if output == source:
        raise ValueError("output must not overwrite the source")
    if output.suffix.lower() == ".pdf":
        raise ValueError(
            "PDF output requires a genuine PDF renderer; "
            "choose DOCX or text output"
        )
    mode = approval.document_mode

    original = load(source)["body_text"]
    patch_document(source, output, materialized, mode=mode)
    loaded_output = load(output)
    updated = loaded_output["body_text"]
    if updated == original:
        raise ValueError("approved changes produced no output change")
    for change in materialized:
        if (
            change["operation"] != "delete_span"
            and change["replacement_text"] not in updated
        ):
            raise ValueError(
                f"output verification failed for change {change['id']}"
            )

    diff = "".join(
        difflib.unified_diff(
            original.splitlines(True),
            updated.splitlines(True),
            fromfile=str(source),
            tofile=str(output),
        )
    )
    applied = [
        {
            "id": change["id"],
            "status": "applied",
            "operation": change["operation"],
            "selected_variant": change.get("selected_variant"),
            "evidence_ids": change["evidence_ids"],
            "replacement_text": change["replacement_text"],
        }
        for change in materialized
    ]
    result = {
        "status": "applied",
        "schema_version": SCHEMA_VERSION,
        "proposal_id": proposal.proposal_id,
        "proposal_digest": verified_digest,
        "approved_change_ids": [item["id"] for item in applied],
        "applied_changes": applied,
        "source": str(source),
        "output": str(output),
        "mode": mode,
        "document_mode": mode,
        "source_overwrite": False,
        "source_sha256": _sha(source),
        "output_sha256": _sha(output),
        "diff": diff,
        "validation": {
            "path": str(output),
            "status": "audited",
            **audit_text(
                loaded_output["text"],
                loaded_output.get("diagnostics"),
            ),
        },
    }
    log = output.with_suffix(output.suffix + ".applied.json")
    log.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
