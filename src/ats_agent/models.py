"""Stable public data contracts for integrations."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class RequirementEvidence:
    requirement_id: str
    coverage: Literal["direct", "transferable", "unsupported"]
    evidence_ids: tuple[str, ...] = ()
    confidence: Literal["low", "medium", "high"] = "medium"
    explanation: str = ""


@dataclass(frozen=True)
class RewriteVariant:
    id: Literal["conservative", "balanced", "compact"]
    text: str


@dataclass(frozen=True)
class ProposedChange:
    id: str
    kind: str
    operation: Literal[
        "replace_span",
        "insert_after",
        "insert_before",
        "delete_span",
        "none",
    ]
    expected_text: str
    evidence_ids: tuple[str, ...] = ()
    variants: tuple[RewriteVariant, ...] = ()
    supported: bool = False
    reason: str = ""
    anchor: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ApprovalSelection:
    change_id: str
    variant_id: str | None = None


@dataclass(frozen=True)
class ApprovalManifest:
    proposal: str
    selections: tuple[ApprovalSelection, ...]
    output: str
    mode: Literal["preserve", "rebuild"] = "preserve"


@dataclass(frozen=True)
class AppliedChange:
    id: str
    status: Literal["applied"]
    operation: str
    evidence_ids: tuple[str, ...]
    replacement_text: str
    selected_variant: str | None = None


def model_dict(value: Any) -> dict[str, Any]:
    return asdict(value)
