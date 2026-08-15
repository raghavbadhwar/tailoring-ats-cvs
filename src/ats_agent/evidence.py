"""Candidate-scoped evidence ledger and ownership protection."""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Iterable, Literal, Mapping, Sequence, cast

Ownership = Literal["observed", "contributor", "direct", "lead", "owner"]
Confidence = Literal["low", "medium", "high"]
Verification = Literal["candidate_supplied", "source_verified", "unverified"]

OWNERSHIP_RANK: dict[str, int] = {
    "observed": 0,
    "contributor": 1,
    "direct": 2,
    "lead": 3,
    "owner": 4,
}

SKILL_SIGNAL = re.compile(
    r"\b(?:python|sql|typescript|javascript|react|next(?:\.?js)?|postgres(?:ql)?|"
    r"supabase|api|excel|git|github|playwright|pydantic|fastify|figma|canva|"
    r"power\s*bi|tableau|docker|kubernetes|aws|azure|gcp|rag|llm|mcp)\b",
    re.IGNORECASE,
)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("boolean is not a valid numeric position")
    if isinstance(value, int):
        return value
    if isinstance(value, (str, bytes, bytearray)):
        return int(value)
    raise ValueError(f"invalid numeric position: {value!r}")


def _string_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(str(item) for item in value)
    raise ValueError("fact_types must be a sequence")


@dataclass(frozen=True)
class SourceFragment:
    part: str
    paragraph_index: int | None
    line_number: int | None
    text: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "SourceFragment":
        return cls(
            part=str(value.get("part") or "text"),
            paragraph_index=_optional_int(value.get("paragraph_index")),
            line_number=_optional_int(value.get("line_number")),
            text=str(value.get("text") or ""),
        )


@dataclass(frozen=True)
class EvidenceSource:
    source: str
    source_file: str
    text: str
    fragments: tuple[SourceFragment, ...] = ()
    verification_status: Verification = "candidate_supplied"
    candidate_id: str | None = None


@dataclass(frozen=True)
class EvidenceItem:
    id: str
    candidate_id: str
    text: str
    source: str
    source_file: str
    source_span: str
    line_number: int | None
    paragraph_index: int | None
    part: str
    ownership: Ownership
    confidence: Confidence = "medium"
    verification_status: Verification = "candidate_supplied"
    fact_types: tuple[str, ...] = field(default_factory=tuple)
    source_sha256: str = ""

    def to_dict(self) -> dict:
        value = asdict(self)
        value["fact_types"] = list(self.fact_types)
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "EvidenceItem":
        return cls(
            id=str(value["id"]),
            candidate_id=str(value["candidate_id"]),
            text=str(value["text"]),
            source=str(value["source"]),
            source_file=str(value["source_file"]),
            source_span=str(value.get("source_span") or ""),
            line_number=_optional_int(value.get("line_number")),
            paragraph_index=_optional_int(value.get("paragraph_index")),
            part=str(value.get("part") or "text"),
            ownership=cast(Ownership, str(value.get("ownership") or "observed")),
            confidence=cast(Confidence, str(value.get("confidence") or "medium")),
            verification_status=cast(
                Verification,
                str(value.get("verification_status") or "candidate_supplied"),
            ),
            fact_types=_string_tuple(value.get("fact_types")),
            source_sha256=str(value.get("source_sha256") or ""),
        )


@dataclass(frozen=True)
class EvidenceLedger:
    candidate_id: str
    items: tuple[EvidenceItem, ...]

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("candidate_id is required")
        mismatched = [item.id for item in self.items if item.candidate_id != self.candidate_id]
        if mismatched:
            raise ValueError(
                "candidate identity mismatch for evidence IDs: " + ", ".join(mismatched)
            )
        ids = [item.id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate evidence IDs are not allowed")

    def by_id(self) -> dict[str, EvidenceItem]:
        return {item.id: item for item in self.items}

    def require(self, evidence_ids: Iterable[str]) -> list[EvidenceItem]:
        index = self.by_id()
        requested = list(evidence_ids)
        unknown = [item for item in requested if item not in index]
        if unknown:
            raise ValueError(f"unknown evidence IDs: {', '.join(unknown)}")
        return [index[item] for item in requested]

    def to_dicts(self) -> list[dict]:
        return [item.to_dict() for item in self.items]

    @classmethod
    def from_dicts(
        cls,
        candidate_id: str,
        records: Sequence[Mapping[str, object]],
    ) -> "EvidenceLedger":
        return cls(candidate_id=candidate_id, items=tuple(EvidenceItem.from_dict(r) for r in records))


def detect_ownership(text: str) -> Ownership:
    body = text.lower()
    if re.search(r"\b(founded|co-founded|owned)\b", body):
        return "owner"
    if re.search(r"\b(led|headed|directed)\b", body) or re.search(
        r"\bmanaged\s+(?:a\s+|an\s+|the\s+)?(?:team|project|programme|program|initiative)\b",
        body,
    ):
        return "lead"
    if re.search(
        r"\b(helped|assisted|contributed|participated|collaborated|supported)\b",
        body,
    ):
        return "contributor"
    if re.search(
        r"\b(built|designed|developed|created|implemented|engineered|validated|"
        r"analysed|analyzed|delivered|launched)\b",
        body,
    ):
        return "direct"
    return "observed"


def ownership_rank(value: str) -> int:
    try:
        return OWNERSHIP_RANK[value]
    except KeyError as exc:
        raise ValueError(f"unknown ownership level: {value}") from exc


def _is_heading(line: str) -> bool:
    stripped = line.strip().rstrip(":")
    standard = {
        "summary",
        "profile",
        "education",
        "experience",
        "projects",
        "skills",
        "certifications",
        "leadership",
        "achievements",
    }
    return stripped.lower() in standard or (
        bool(stripped)
        and stripped.upper() == stripped
        and len(stripped.split()) <= 6
        and not SKILL_SIGNAL.search(stripped)
    )


def _is_compact_evidence(claim: str) -> bool:
    return bool(SKILL_SIGNAL.search(claim)) or "," in claim or "/" in claim


def _fact_types(text: str) -> tuple[str, ...]:
    kinds: set[str] = set()
    if SKILL_SIGNAL.search(text):
        kinds.add("skill")
    if re.search(r"\b(?:19|20)\d{2}\b", text):
        kinds.add("date")
    if re.search(r"(?<![A-Za-z])\d+(?:[.,]\d+)?%?", text):
        kinds.add("metric")
    if re.search(r"\b(?:bachelor|master|b\.?com|b\.?tech|mba|degree|diploma)\b", text, re.I):
        kinds.add("qualification")
    if re.search(r"\b(?:production|deployed|live|prototype|mvp|customer|user|revenue)\b", text, re.I):
        kinds.add("status")
    if detect_ownership(text) != "observed":
        kinds.add("ownership")
    return tuple(sorted(kinds or {"narrative"}))


def _fallback_fragments(text: str) -> tuple[SourceFragment, ...]:
    fragments: list[SourceFragment] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if line.strip():
            fragments.append(
                SourceFragment(
                    part="text",
                    paragraph_index=None,
                    line_number=line_number,
                    text=line,
                )
            )
    return tuple(fragments)


def _claim_fragments(source: EvidenceSource) -> list[SourceFragment]:
    claims: list[SourceFragment] = []
    for fragment in source.fragments or _fallback_fragments(source.text):
        stripped = fragment.text.strip()
        if not stripped or _is_heading(stripped):
            continue
        claim = re.sub(r"^\s*[-*•▪◦]\s*", "", stripped).strip()
        if len(claim.split()) < 3 and not _is_compact_evidence(claim):
            continue
        claims.append(
            SourceFragment(
                part=fragment.part,
                paragraph_index=fragment.paragraph_index,
                line_number=fragment.line_number,
                text=claim,
            )
        )
    return claims


def _evidence_id(
    candidate_id: str,
    source_file: str,
    part: str,
    position: int | None,
    text: str,
) -> str:
    payload = f"{candidate_id}\x00{source_file}\x00{part}\x00{position}\x00{text}".encode("utf-8")
    return "E" + hashlib.sha256(payload).hexdigest()[:14].upper()


def build_evidence_ledger(
    candidate_id: str,
    sources: Iterable[EvidenceSource],
) -> EvidenceLedger:
    if not candidate_id.strip():
        raise ValueError("candidate_id is required")
    items: list[EvidenceItem] = []
    seen: set[tuple[str, str, str]] = set()
    for source in sources:
        if source.candidate_id and source.candidate_id != candidate_id:
            raise ValueError(
                f"candidate identity mismatch in source {source.source_file}: "
                f"{source.candidate_id} != {candidate_id}"
            )
        source_hash = hashlib.sha256(source.text.encode("utf-8")).hexdigest()
        for fragment in _claim_fragments(source):
            identity = (source.source_file, fragment.part, fragment.text)
            if identity in seen:
                continue
            seen.add(identity)
            position = (
                fragment.paragraph_index
                if fragment.paragraph_index is not None
                else fragment.line_number
            )
            span = (
                f"{fragment.part} paragraph {fragment.paragraph_index}"
                if fragment.paragraph_index is not None
                else f"line {fragment.line_number}"
            )
            items.append(
                EvidenceItem(
                    id=_evidence_id(
                        candidate_id,
                        source.source_file,
                        fragment.part,
                        position,
                        fragment.text,
                    ),
                    candidate_id=candidate_id,
                    text=fragment.text,
                    source=source.source,
                    source_file=source.source_file,
                    source_span=span,
                    line_number=fragment.line_number,
                    paragraph_index=fragment.paragraph_index,
                    part=fragment.part,
                    ownership=detect_ownership(fragment.text),
                    confidence="high" if source.source == "resume" else "medium",
                    verification_status=source.verification_status,
                    fact_types=_fact_types(fragment.text),
                    source_sha256=source_hash,
                )
            )
    return EvidenceLedger(candidate_id=candidate_id, items=tuple(items))
