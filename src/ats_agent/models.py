"""Versioned public schemas for the approval-gated workflow."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ArtifactKind = Literal["resume", "candidate_evidence", "job_description", "company_context"]
Ownership = Literal["observed", "contributor", "direct", "lead", "owner"]
Verification = Literal["candidate_supplied", "source_verified", "externally_verified", "unverified"]


class SourceSpan(BaseModel):
    model_config = ConfigDict(frozen=True)
    part: str
    paragraph_index: int | None = None
    line_number: int | None = None
    start_char: int | None = None
    end_char: int | None = None


class ArtifactFingerprint(BaseModel):
    model_config = ConfigDict(frozen=True)
    artifact_id: str
    candidate_id: str | None = None
    kind: ArtifactKind
    path: str
    mime_type: str
    sha256: str


class AtomicClaim(BaseModel):
    model_config = ConfigDict(frozen=True)
    claim_id: str
    candidate_id: str
    artifact_id: str
    source_span: SourceSpan
    source_text: str
    subject: str | None = None
    action: str | None = None
    object: str | None = None
    technologies: tuple[str, ...] = ()
    entities: tuple[str, ...] = ()
    metric_value: Decimal | None = None
    metric_unit: str | None = None
    metric_scope: str | None = None
    ownership: Ownership = "observed"
    verification: Verification = "candidate_supplied"
    confidence: float = Field(ge=0, le=1)
    supersedes: tuple[str, ...] = ()
    contradicts: tuple[str, ...] = ()


class RewriteVariant(BaseModel):
    model_config = ConfigDict(frozen=True)
    variant_id: Literal["conservative", "balanced", "compact"]
    text: str
    evidence_claim_ids: tuple[str, ...] = ()
    requirement_ids: tuple[str, ...] = ()
    verifier_digest: str = ""


class ProposedChange(BaseModel):
    """V1 proposal change; ``from_dict`` keeps legacy integrations readable."""
    model_config = ConfigDict(extra="ignore")
    change_id: str = Field(alias="id")
    operation: Literal["replace_span", "insert_after", "insert_before", "delete_span"]
    target_artifact_id: str = "resume"
    target_span: SourceSpan = Field(default_factory=lambda: SourceSpan(part="text"))
    expected_text: str = ""
    variants: tuple[RewriteVariant, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    supported: bool = False
    reason: str = ""
    risk: Literal["low", "medium", "high"] = "medium"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ProposedChange":
        change_id = value.get("id", value.get("change_id"))
        if not isinstance(change_id, str) or not change_id:
            raise ValueError("change id is required")
        anchor = value.get("anchor") or {}
        variants = tuple(
            RewriteVariant(variant_id=item.get("id", item.get("variant_id")), text=item["text"])
            for item in value.get("variants", [])
            if item.get("id", item.get("variant_id")) in {"conservative", "balanced", "compact"}
        )
        return cls(
            id=change_id, operation=value.get("operation", "replace_span"),
            target_span=SourceSpan(part=anchor.get("part", "text"), paragraph_index=anchor.get("paragraph_index"), line_number=anchor.get("line_number")),
            expected_text=value.get("expected_text", ""), variants=variants,
            evidence_ids=tuple(value.get("evidence_ids", ())), supported=bool(value.get("supported")), reason=value.get("reason", ""),
        )


class ProposalEnvelope(BaseModel):
    schema_version: Literal[5] = 5
    proposal_id: str
    candidate_id: str
    artifacts: tuple[ArtifactFingerprint, ...]
    policy_version: str = "v1"
    ontology_version: str = "v1"
    provider: str = "deterministic"
    provider_version: str = "v1"
    changes: tuple[ProposedChange, ...] = ()
    proposal_digest: str


class ApprovalSelection(BaseModel):
    change_id: str
    variant_id: Literal["conservative", "balanced", "compact"]


class ApprovalManifest(BaseModel):
    schema_version: Literal[2] = 2
    proposal_path: str = Field(alias="proposal")
    proposal_digest: str
    selections: tuple[ApprovalSelection, ...]
    output_path: str = Field(alias="output")
    document_mode: Literal["preserve", "rebuild"] = "preserve"
    force: bool = False
