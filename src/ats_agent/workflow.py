"""PROPOSE → APPROVE → APPLY workflow with content-bound provenance."""
from __future__ import annotations

import difflib
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from .agents import career_report
from .artifacts import register_artifacts
from .documents import docx_structure_fingerprint, patch_document
from .evidence import (
    EvidenceLedger,
    EvidenceSource,
    SourceFragment,
    build_evidence_ledger,
    evidence_conflicts,
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
from .providers import DeterministicRewriteProvider, RewriteProvider
from .requirements import (
    TERM_ALIASES,
    evaluate_hard_gates,
    extract_requirements,
    map_requirements,
)
from .rewriting import propose_supported_changes
from .validation import near_duplicate_cv_lines, validate_change

SCHEMA_VERSION = 5
POLICY_VERSION = "evidence-policy-v1"
ONTOLOGY_VERSION = "requirements-v1"
ALLOWED_OUTPUT_SUFFIXES = {".txt", ".md", ".markdown", ".docx"}
MAX_RESEARCH_AGE = timedelta(days=7)


def finalize_proposal(payload: dict) -> dict:
    """Validate the final proposal shape, bind its digest, and verify it."""

    draft = dict(payload)
    draft["proposal_digest"] = "0" * 64
    canonical = ProposalEnvelope.model_validate(draft).model_dump(mode="json")
    canonical["proposal_digest"] = compute_proposal_digest(canonical)
    finalized = ProposalEnvelope.model_validate(canonical).model_dump(mode="json")
    verify_proposal_digest(finalized)
    return finalized


def _coverage_report(mappings: Iterable[dict], changes: Iterable[dict]) -> dict:
    baseline = [
        {
            "requirement_id": item["requirement_id"],
            "terms": item.get("normalized_terms", []),
            "coverage": item.get("coverage"),
        }
        for item in mappings
    ]
    variants = [
        {
            "change_id": change["id"],
            "variant_id": variant["id"],
            "terms_added": variant.get("coverage_delta", []),
            "reason": change.get("value_reason", change.get("reason", "")),
        }
        for change in changes
        for variant in change.get("variants", [])
        if change.get("supported")
    ]
    return {"baseline": baseline, "proposed_variants": variants}


def _validated_coverage(requirements: Iterable[dict], text: str) -> dict:
    """Measure visible requirement terms in the parser-readable output."""

    visible = text.lower()
    records: list[dict] = []
    for requirement in requirements:
        terms = list(requirement.get("normalized_terms", []))
        covered = [
            term
            for term in terms
            if any(
                re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", visible)
                for alias in TERM_ALIASES.get(term, (term,))
            )
        ]
        records.append(
            {
                "requirement_id": requirement["id"],
                "covered_terms": covered,
                "missing_terms": [term for term in terms if term not in covered],
            }
        )
    return {"requirements": records, "covered_term_count": sum(len(item["covered_terms"]) for item in records)}


def _absolute(path: Path) -> Path:
    return path.expanduser().resolve()


def _validate_research_freshness(proposal: dict) -> None:
    """Require a new capture before applying an old public-job proposal."""

    research = proposal.get("research")
    if not isinstance(research, dict):
        return
    captured_at = research.get("captured_at")
    if not isinstance(captured_at, str):
        raise ValueError("research proposal has no liveness timestamp; refresh before apply")
    try:
        captured = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("research liveness timestamp is invalid; refresh before apply") from exc
    if captured.tzinfo is None or datetime.now(timezone.utc) - captured.astimezone(timezone.utc) > MAX_RESEARCH_AGE:
        raise ValueError("research capture is stale; refresh before apply")


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
    provider: RewriteProvider | None = None,
    additional_requirements: Iterable[dict] | None = None,
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
    duplicate_warnings = [
        {
            "evidence_id": item.id,
            "status": "review_only",
            "reason": "Supporting evidence closely overlaps an existing CV line.",
            "matching_cv_lines": near_duplicate_cv_lines(item.text, cv["body_text"]),
        }
        for item in ledger.items
        if item.source == "supporting" and near_duplicate_cv_lines(item.text, cv["body_text"])
    ]
    requirements = extract_requirements(jd["text"])
    if additional_requirements:
        from .requirements import merge_requirements

        requirements = merge_requirements(requirements, additional_requirements)
    mappings = map_requirements(requirements, ledger)
    hard_gates = evaluate_hard_gates(requirements, ledger)
    selected_provider = provider or DeterministicRewriteProvider()
    changes = propose_supported_changes(
        cv["body_text"],
        requirements,
        mappings,
        ledger,
        provider=selected_provider,
    )
    conflicts = evidence_conflicts(ledger)
    conflicting_ids: set[str] = set()
    for conflict in conflicts:
        evidence_ids = conflict.get("evidence_ids")
        if isinstance(evidence_ids, list):
            conflicting_ids.update(
                evidence_id
                for evidence_id in evidence_ids
                if isinstance(evidence_id, str)
            )
    for change in changes:
        if conflicting_ids.intersection(change.get("evidence_ids", [])):
            change["supported"] = False
            change["status"] = "blocked_conflict"
            change["reason"] = (
                "Candidate evidence conflicts on a scoped fact; provide "
                "reconciled evidence before using this change."
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
        "provider": selected_provider.provider_id,
        "provider_version": selected_provider.provider_version,
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
        "evidence_conflicts": conflicts,
        "duplicate_warnings": duplicate_warnings,
        "coverage": _coverage_report(mappings, changes),
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
    return finalize_proposal(payload)


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


def _temporary_output(output: Path) -> Path:
    """Return a same-directory temporary path with the genuine output suffix."""

    token = uuid.uuid4().hex
    return output.with_name(
        f".{output.stem}.tmp-{token}{output.suffix.lower()}"
    )


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


def _validate_output_path(
    source: Path,
    output: Path,
    *,
    force: bool,
) -> None:
    if output == source:
        raise ValueError("output must not overwrite the source")
    suffix = output.suffix.lower()
    if suffix == ".pdf":
        raise ValueError(
            "PDF output requires a genuine PDF renderer; "
            "choose DOCX or text output"
        )
    if suffix not in ALLOWED_OUTPUT_SUFFIXES:
        raise ValueError(
            "unsupported output format: "
            f"{suffix or '<none>'}; choose TXT, Markdown, or DOCX"
        )
    if output.exists() and not force:
        raise ValueError(
            f"output already exists: {output}; set force=true to replace it"
        )


def apply_manifest(
    manifest_path: Path,
    approved: list[str] | None = None,
) -> dict:
    """Apply selected changes only after verifying every temporary output."""

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
    _validate_research_freshness(proposal_data)
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
        change["max_character_growth"] = approval.max_character_growth
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
    _validate_output_path(source, output, force=approval.force)
    mode = approval.document_mode

    original = load(source)["body_text"]
    format_fingerprint = (
        docx_structure_fingerprint(source)
        if mode == "strict-preserve" and source.suffix.lower() == ".docx"
        else None
    )
    temporary = _temporary_output(output)
    loaded_output: dict
    updated: str
    try:
        patch_document(source, temporary, materialized, mode=mode)
        loaded_output = load(temporary)
        updated = loaded_output["body_text"]
        if updated == original:
            raise ValueError("approved changes produced no output change")
        if format_fingerprint and docx_structure_fingerprint(temporary) != format_fingerprint:
            raise ValueError("strict-preserve structural fingerprint changed")
        for change in materialized:
            if (
                change["operation"] != "delete_span"
                and change["replacement_text"] not in updated
            ):
                raise ValueError(
                    f"output verification failed for change {change['id']}"
                )
        os.replace(temporary, output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

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
        "format_lock": {
            "status": "verified" if format_fingerprint else "not_requested",
            "structural_fingerprint": format_fingerprint,
            "rendered_layout": "unverified",
        },
        "diff": diff,
        "validation": {
            "path": str(output),
            "status": "audited",
            **audit_text(
                loaded_output["text"],
                loaded_output.get("diagnostics"),
            ),
        },
        "coverage": {
            "baseline": proposal_data.get("coverage", {}).get("baseline", []),
            "proposed_variants": proposal_data.get("coverage", {}).get("proposed_variants", []),
            "validated_output": _validated_coverage(proposal_data["requirements"], updated),
        },
    }
    log = output.with_suffix(output.suffix + ".applied.json")
    log.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
