"""Typed external workflow schemas for proposals, artifacts, and approvals."""
from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ArtifactKind = Literal[
    "resume",
    "candidate_evidence",
    "job_description",
    "company_context",
]
DocumentMode = Literal["preserve", "strict-preserve", "rebuild"]


class SourceSpan(BaseModel):
    """Stable document location used by proposal and evidence records."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    part: str
    paragraph_index: int | None = None
    line_number: int | None = None
    start_char: int | None = None
    end_char: int | None = None


class ArtifactFingerprint(BaseModel):
    """Content-bound input artifact registered for one proposal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: str = Field(min_length=2)
    candidate_id: str | None
    kind: ArtifactKind
    path: str = Field(min_length=1)
    mime_type: str = Field(min_length=1)
    sha256: str

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        normalized = value.lower()
        if re.fullmatch(r"[0-9a-f]{64}", normalized) is None:
            raise ValueError("sha256 must contain exactly 64 hexadecimal characters")
        return normalized


class ApprovalSelection(BaseModel):
    """One explicitly selected change and rewrite variant."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    change_id: str = Field(min_length=1)
    variant_id: str | None = None


class ApprovalManifest(BaseModel):
    """Validated approval input.

    Schema version 1 is read-only compatibility for existing local manifests.
    New review surfaces emit schema version 2, which requires a proposal digest.
    ``selections`` remains ``None`` when omitted so legacy explicit approval
    arguments are not shadowed by an empty default created during model dump.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=1, ge=1, le=2)
    proposal: str = Field(min_length=1)
    proposal_digest: str | None = None
    selections: tuple[ApprovalSelection, ...] | None = None
    approved_change_ids: tuple[str, ...] = ()
    document_mode: DocumentMode = "preserve"
    mode: DocumentMode | None = None
    output: str | None = None
    force: bool = False
    max_character_growth: int = Field(default=120, ge=0, le=2000)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_mode(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        if "document_mode" not in data and data.get("mode") is not None:
            data["document_mode"] = data["mode"]
        return data

    @model_validator(mode="after")
    def require_v2_digest(self) -> "ApprovalManifest":
        if self.schema_version >= 2 and not self.proposal_digest:
            raise ValueError("schema version 2 approval requires proposal_digest")
        return self

    @field_validator("proposal_digest")
    @classmethod
    def validate_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.lower()
        if re.fullmatch(r"[0-9a-f]{64}", normalized) is None:
            raise ValueError(
                "proposal_digest must contain exactly 64 hexadecimal characters"
            )
        return normalized


class ProposalEnvelope(BaseModel):
    """Typed schema-v5 proposal envelope.

    Existing detailed analysis collections remain JSON objects in this phase;
    their dedicated typed schemas are introduced with the claim and matching
    upgrades while the top-level security boundary is already strict.
    """

    model_config = ConfigDict(extra="allow")

    schema_version: Literal[5]
    status: Literal["draft"]
    proposal_id: str = Field(min_length=2)
    candidate_id: str = Field(min_length=1)
    artifacts: tuple[ArtifactFingerprint, ...]
    policy_version: str = Field(min_length=1)
    ontology_version: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    provider_version: str = Field(min_length=1)
    source: str = Field(min_length=1)
    source_format: str = Field(min_length=1)
    job_description: str = Field(min_length=1)
    source_sha256: str
    job_description_sha256: str
    evidence_files: tuple[str, ...] = ()
    company_context: str | None = None
    evidence_ledger: tuple[dict[str, Any], ...]
    requirements: tuple[dict[str, Any], ...]
    requirement_evidence: tuple[dict[str, Any], ...]
    hard_gates: tuple[dict[str, Any], ...]
    changes: tuple[dict[str, Any], ...]
    report: dict[str, Any]
    formatting: dict[str, Any]
    input_diagnostics: dict[str, Any]
    proposal_digest: str

    @field_validator(
        "source_sha256",
        "job_description_sha256",
        "proposal_digest",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        normalized = value.lower()
        if re.fullmatch(r"[0-9a-f]{64}", normalized) is None:
            raise ValueError("proposal hashes must be 64 hexadecimal characters")
        return normalized
