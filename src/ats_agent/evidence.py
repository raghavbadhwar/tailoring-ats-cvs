"""Candidate-specific evidence records and ownership protection.

The evidence ledger is the only source from which supported rewrite claims may
be constructed. A job description is never added to this ledger.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Iterable, Literal

Ownership = Literal["observed", "contributor", "direct", "lead", "owner"]

OWNERSHIP_RANK: dict[str, int] = {
    "observed": 0,
    "contributor": 1,
    "direct": 2,
    "lead": 3,
    "owner": 4,
}

COMPACT_EVIDENCE = re.compile(
    r"\b(?:python|sql|typescript|javascript|react|next(?:\.?js)?|postgres(?:ql)?|"
    r"supabase|api|excel|git|github|playwright|pydantic|fastify|figma|canva)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EvidenceSource:
    source: str
    source_file: str
    text: str


@dataclass(frozen=True)
class EvidenceItem:
    id: str
    candidate_id: str
    text: str
    source: str
    source_file: str
    source_span: str
    line_number: int
    ownership: Ownership
    confidence: Literal["low", "medium", "high"] = "medium"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceLedger:
    candidate_id: str
    items: tuple[EvidenceItem, ...]

    def __post_init__(self) -> None:
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
        r"\b(built|designed|developed|created|implemented|engineered|validated|analysed|analyzed)\b",
        body,
    ):
        return "direct"
    return "observed"


def _is_heading(line: str) -> bool:
    stripped = line.strip().rstrip(":")
    if stripped.startswith("#"):
        return True
    return bool(stripped) and stripped.upper() == stripped and len(stripped.split()) <= 6


def _is_compact_evidence(claim: str) -> bool:
    return bool(COMPACT_EVIDENCE.search(claim)) or "," in claim or "/" in claim


def _claim_lines(text: str) -> list[tuple[int, str]]:
    claims: list[tuple[int, str]] = []
    for line_number, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or _is_heading(stripped):
            continue
        claim = re.sub(r"^\s*[-*•▪◦]\s*", "", stripped).strip()
        if len(claim.split()) < 3 and not _is_compact_evidence(claim):
            continue
        claims.append((line_number, claim))
    return claims


def _evidence_id(candidate_id: str, source_file: str, line_number: int, text: str) -> str:
    payload = f"{candidate_id}\x00{source_file}\x00{line_number}\x00{text}".encode("utf-8")
    return "E" + hashlib.sha256(payload).hexdigest()[:12].upper()


def build_evidence_ledger(
    candidate_id: str,
    sources: Iterable[EvidenceSource],
) -> EvidenceLedger:
    if not candidate_id.strip():
        raise ValueError("candidate_id is required")
    items: list[EvidenceItem] = []
    seen: set[tuple[str, str]] = set()
    for source in sources:
        for line_number, claim in _claim_lines(source.text):
            identity = (source.source_file, claim)
            if identity in seen:
                continue
            seen.add(identity)
            items.append(
                EvidenceItem(
                    id=_evidence_id(candidate_id, source.source_file, line_number, claim),
                    candidate_id=candidate_id,
                    text=claim,
                    source=source.source,
                    source_file=source.source_file,
                    source_span=f"line {line_number}",
                    line_number=line_number,
                    ownership=detect_ownership(claim),
                    confidence="high" if source.source == "resume" else "medium",
                )
            )
    return EvidenceLedger(candidate_id=candidate_id, items=tuple(items))


def ownership_rank(value: str) -> int:
    try:
        return OWNERSHIP_RANK[value]
    except KeyError as exc:
        raise ValueError(f"unknown ownership level: {value}") from exc
