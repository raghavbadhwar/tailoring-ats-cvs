"""Small typed contracts shared by the deterministic workflow."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class CandidateEvidence:
    id: str
    text: str
    source: str
    source_span: str = ""
    confidence: Literal["low", "medium", "high"] = "medium"


@dataclass(frozen=True)
class JobRequirement:
    id: str
    term: str
    category: str
    importance: Literal["preferred", "mandatory"] = "preferred"


@dataclass(frozen=True)
class EvidenceMatch:
    requirement_id: str
    evidence_ids: list[str] = field(default_factory=list)
    coverage: Literal["direct", "transferable", "unsupported"] = "unsupported"
    explanation: str = ""


@dataclass(frozen=True)
class ProposedChange:
    id: str
    operation: Literal["replace"]
    expected_text: str
    replacement_text: str
    evidence_ids: list[str] = field(default_factory=list)
    supported: bool = False
    reason: str = ""


@dataclass(frozen=True)
class ApprovalManifest:
    proposal: str
    approved_change_ids: list[str]
    output: str | None = None


@dataclass(frozen=True)
class AppliedChange:
    id: str
    status: Literal["applied"]
    expected_text: str
    replacement_text: str
    start: int
    end: int


@dataclass(frozen=True)
class ValidationResult:
    status: Literal["passed", "blocked"]
    checks: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def model_dict(value: Any) -> dict[str, Any]:
    return asdict(value)
