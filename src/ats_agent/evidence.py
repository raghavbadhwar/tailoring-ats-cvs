"""Candidate-scoped evidence ledger, atomic claims, and ownership protection."""
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

CLAUSE_ACTIONS = (
    "analysed",
    "analyzed",
    "architected",
    "assisted",
    "automated",
    "built",
    "collaborated",
    "conducted",
    "contributed",
    "created",
    "delivered",
    "designed",
    "developed",
    "directed",
    "engineered",
    "founded",
    "headed",
    "helped",
    "implemented",
    "improved",
    "increased",
    "launched",
    "led",
    "managed",
    "owned",
    "participated",
    "processed",
    "reduced",
    "supported",
    "validated",
)
CLAUSE_SPLIT = re.compile(
    r"\s+(?:and|;)\s+(?=(?:" + "|".join(CLAUSE_ACTIONS) + r")\b)",
    re.IGNORECASE,
)
PERCENT_METRIC = re.compile(
    r"(?<![A-Za-z0-9])(?P<value>\d+(?:[.,]\d+)?)\s*%"
)
COUNT_METRIC = re.compile(
    r"(?<![A-Za-z0-9])(?P<value>\d+(?:[.,]\d+)?)\s+"
    r"(?P<unit>[A-Za-z][A-Za-z-]*)\b"
)
GRADE_VALUE = re.compile(
    r"\b(?:cgpa|gpa)\s*(?:of|:|=)?\s*(?P<value>\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
GRADUATION_VALUE = re.compile(
    r"\b(?:graduat(?:e|ing|ion)|class\s+of)\D{0,24}(?P<value>20\d{2})\b",
    re.IGNORECASE,
)
EMPLOYMENT_DATE = re.compile(
    r"\b(?:joined|started|employed|employment|worked)\D{0,24}(?P<value>(?:19|20)\d{2})\b",
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


def _mapping_tuple(value: object) -> tuple[Mapping[str, object], ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        raise ValueError("atomic_claims must be a sequence")
    records: list[Mapping[str, object]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("atomic claim records must be mappings")
        records.append(item)
    return tuple(records)


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
class MetricBinding:
    """A value bound to its unit and the clause-level scope it describes."""

    value: str
    unit: str
    scope: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "MetricBinding":
        return cls(
            value=str(value.get("value") or ""),
            unit=str(value.get("unit") or ""),
            scope=str(value.get("scope") or ""),
        )


@dataclass(frozen=True)
class AtomicClaim:
    """A clause that can be supported or rejected independently."""

    id: str
    candidate_id: str
    text: str
    source_file: str
    source_span: str
    ownership: Ownership
    verification_status: Verification
    metrics: tuple[MetricBinding, ...] = ()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "candidate_id": self.candidate_id,
            "text": self.text,
            "source_file": self.source_file,
            "source_span": self.source_span,
            "ownership": self.ownership,
            "verification_status": self.verification_status,
            "metrics": [metric.to_dict() for metric in self.metrics],
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "AtomicClaim":
        raw_metrics = value.get("metrics")
        if raw_metrics is None:
            metrics: tuple[MetricBinding, ...] = ()
        elif isinstance(raw_metrics, Sequence) and not isinstance(
            raw_metrics, (str, bytes, bytearray)
        ):
            metrics = tuple(
                MetricBinding.from_mapping(item)
                for item in raw_metrics
                if isinstance(item, Mapping)
            )
        else:
            raise ValueError("metrics must be a sequence")
        return cls(
            id=str(value.get("id") or ""),
            candidate_id=str(value.get("candidate_id") or ""),
            text=str(value.get("text") or ""),
            source_file=str(value.get("source_file") or ""),
            source_span=str(value.get("source_span") or ""),
            ownership=cast(
                Ownership, str(value.get("ownership") or "observed")
            ),
            verification_status=cast(
                Verification,
                str(value.get("verification_status") or "unverified"),
            ),
            metrics=metrics,
        )


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
    atomic_claims: tuple[AtomicClaim, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        value = asdict(self)
        value["fact_types"] = list(self.fact_types)
        value["atomic_claims"] = [
            claim.to_dict() for claim in self.atomic_claims
        ]
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "EvidenceItem":
        item_id = str(value["id"])
        candidate_id = str(value["candidate_id"])
        text = str(value["text"])
        source_file = str(value["source_file"])
        source_span = str(value.get("source_span") or "")
        ownership = cast(
            Ownership, str(value.get("ownership") or "observed")
        )
        verification = cast(
            Verification,
            str(value.get("verification_status") or "candidate_supplied"),
        )
        claim_records = _mapping_tuple(value.get("atomic_claims"))
        claims = tuple(
            AtomicClaim.from_mapping(record) for record in claim_records
        )
        if not claims:
            claims = atomic_claims_from_text(
                text,
                candidate_id=candidate_id,
                source_file=source_file,
                source_span=source_span,
                verification_status=verification,
                ownership=ownership,
                parent_id=item_id,
            )
        return cls(
            id=item_id,
            candidate_id=candidate_id,
            text=text,
            source=str(value["source"]),
            source_file=source_file,
            source_span=source_span,
            line_number=_optional_int(value.get("line_number")),
            paragraph_index=_optional_int(value.get("paragraph_index")),
            part=str(value.get("part") or "text"),
            ownership=ownership,
            confidence=cast(
                Confidence, str(value.get("confidence") or "medium")
            ),
            verification_status=verification,
            fact_types=_string_tuple(value.get("fact_types")),
            source_sha256=str(value.get("source_sha256") or ""),
            atomic_claims=claims,
        )


@dataclass(frozen=True)
class EvidenceLedger:
    candidate_id: str
    items: tuple[EvidenceItem, ...]

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("candidate_id is required")
        mismatched = [
            item.id
            for item in self.items
            if item.candidate_id != self.candidate_id
        ]
        if mismatched:
            raise ValueError(
                "candidate identity mismatch for evidence IDs: "
                + ", ".join(mismatched)
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
        return cls(
            candidate_id=candidate_id,
            items=tuple(EvidenceItem.from_dict(record) for record in records),
        )


def detect_ownership(text: str) -> Ownership:
    body = text.lower()
    if re.search(r"\b(founded|co-founded|owned)\b", body):
        return "owner"
    if re.search(r"\b(led|headed|directed)\b", body) or re.search(
        r"\bmanaged\s+(?:a\s+|an\s+|the\s+)?"
        r"(?:team|project|programme|program|initiative)\b",
        body,
    ):
        return "lead"
    if re.search(
        r"\b(helped|assisted|contributed|participated|collaborated|supported)\b",
        body,
    ):
        return "contributor"
    if re.search(
        r"\b(built|designed|developed|created|implemented|engineered|"
        r"validated|analysed|analyzed|delivered|launched|processed|"
        r"reduced|improved|increased|conducted)\b",
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
        and not re.search(r"\d", stripped)
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
    if re.search(
        r"\b(?:bachelor|master|b\.?com|b\.?tech|mba|degree|diploma)\b",
        text,
        re.IGNORECASE,
    ):
        kinds.add("qualification")
    if re.search(
        r"\b(?:production|deployed|live|prototype|mvp|customer|user|"
        r"revenue)\b",
        text,
        re.IGNORECASE,
    ):
        kinds.add("status")
    if detect_ownership(text) != "observed":
        kinds.add("ownership")
    return tuple(sorted(kinds or {"narrative"}))


def _fallback_fragments(text: str) -> tuple[SourceFragment, ...]:
    return tuple(
        SourceFragment(
            part="text",
            paragraph_index=None,
            line_number=line_number,
            text=line,
        )
        for line_number, line in enumerate(text.splitlines(), 1)
        if line.strip()
    )


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


def _singular_unit(value: str) -> str:
    unit = value.lower().strip(" .,:;")
    if unit.endswith("ies") and len(unit) > 3:
        return unit[:-3] + "y"
    if unit.endswith("ses") and len(unit) > 3:
        return unit[:-2]
    if unit.endswith("s") and not unit.endswith("ss") and len(unit) > 2:
        return unit[:-1]
    return unit


def _metrics(text: str) -> tuple[MetricBinding, ...]:
    metrics: list[MetricBinding] = []
    percent_spans: list[tuple[int, int]] = []
    for match in PERCENT_METRIC.finditer(text):
        percent_spans.append(match.span())
        metrics.append(
            MetricBinding(
                value=match.group("value").replace(",", ""),
                unit="percent",
                scope=text.strip(),
            )
        )
    for match in COUNT_METRIC.finditer(text):
        if any(
            match.start() >= start and match.end() <= end
            for start, end in percent_spans
        ):
            continue
        value = match.group("value").replace(",", "")
        unit = _singular_unit(match.group("unit"))
        if unit in {"year", "month"} and value.isdigit():
            number = int(value)
            if unit == "year" and 1900 <= number <= 2100:
                continue
        metrics.append(
            MetricBinding(value=value, unit=unit, scope=text.strip())
        )
    return tuple(metrics)


def _atomic_texts(text: str) -> tuple[str, ...]:
    parts = [
        part.strip()
        for part in CLAUSE_SPLIT.split(text.strip())
        if part.strip()
    ]
    return tuple(parts or [text.strip()])


def _claim_id(parent_id: str, index: int, text: str) -> str:
    payload = f"{parent_id}\x00{index}\x00{text}".encode("utf-8")
    return "AC" + hashlib.sha256(payload).hexdigest()[:14].upper()


def atomic_claims_from_text(
    text: str,
    *,
    candidate_id: str,
    source_file: str,
    source_span: str,
    verification_status: Verification,
    ownership: Ownership | None = None,
    parent_id: str = "generated",
) -> tuple[AtomicClaim, ...]:
    """Split text into independently supportable clauses and bound metrics."""

    claims: list[AtomicClaim] = []
    for index, clause in enumerate(_atomic_texts(text), 1):
        claim_ownership = ownership or detect_ownership(clause)
        claims.append(
            AtomicClaim(
                id=_claim_id(parent_id, index, clause),
                candidate_id=candidate_id,
                text=clause,
                source_file=source_file,
                source_span=source_span,
                ownership=claim_ownership,
                verification_status=verification_status,
                metrics=_metrics(clause),
            )
        )
    return tuple(claims)


def _evidence_id(
    candidate_id: str,
    source_file: str,
    part: str,
    position: int | None,
    text: str,
) -> str:
    payload = (
        f"{candidate_id}\x00{source_file}\x00{part}\x00"
        f"{position}\x00{text}"
    ).encode("utf-8")
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
        source_hash = hashlib.sha256(
            source.text.encode("utf-8")
        ).hexdigest()
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
            item_id = _evidence_id(
                candidate_id,
                source.source_file,
                fragment.part,
                position,
                fragment.text,
            )
            ownership = detect_ownership(fragment.text)
            items.append(
                EvidenceItem(
                    id=item_id,
                    candidate_id=candidate_id,
                    text=fragment.text,
                    source=source.source,
                    source_file=source.source_file,
                    source_span=span,
                    line_number=fragment.line_number,
                    paragraph_index=fragment.paragraph_index,
                    part=fragment.part,
                    ownership=ownership,
                    confidence=(
                        "high" if source.source == "resume" else "medium"
                    ),
                    verification_status=source.verification_status,
                    fact_types=_fact_types(fragment.text),
                    source_sha256=source_hash,
                    atomic_claims=atomic_claims_from_text(
                        fragment.text,
                        candidate_id=candidate_id,
                        source_file=source.source_file,
                        source_span=span,
                        verification_status=source.verification_status,
                        ownership=None,
                        parent_id=item_id,
                    ),
                )
            )
    return EvidenceLedger(candidate_id=candidate_id, items=tuple(items))


def _conflict_scope(text: str) -> str:
    return " ".join(
        token
        for token in re.findall(r"[a-z]+", text.lower())
        if token not in {"a", "an", "and", "by", "of", "the", "to", "with"}
    )


def _conflict_record(item: EvidenceItem, value: str) -> dict[str, str]:
    return {
        "value": value,
        "evidence_id": item.id,
        "source": item.source,
        "source_span": item.source_span,
    }


def _authorization_value(text: str) -> str | None:
    body = text.lower()
    if re.search(r"\b(?:require|need)s? (?:visa )?sponsorship\b", body):
        return "requires_sponsorship"
    if re.search(r"\b(?:authori[sz]ed|eligible|right to work)\b", body):
        return "authorized"
    return None


def _employment_status(text: str) -> str | None:
    body = text.lower()
    if "unemployed" in body:
        return "unemployed"
    if re.search(r"\b(?:currently )?(?:employed|working)\b", body):
        return "employed"
    if re.search(r"\b(?:undergraduate|student)\b", body):
        return "student"
    return None


def evidence_conflicts(ledger: EvidenceLedger) -> list[dict[str, object]]:
    """Return unresolved candidate-fact conflicts without choosing a winner."""

    values: dict[tuple[str, str], list[dict[str, str]]] = {}

    def add(kind: str, scope: str, item: EvidenceItem, value: str) -> None:
        values.setdefault((kind, scope), []).append(_conflict_record(item, value))

    for item in ledger.items:
        for match in GRADE_VALUE.finditer(item.text):
            kind = match.group(0).split()[0].lower()
            add(kind, kind, item, match.group("value"))
        for match in GRADUATION_VALUE.finditer(item.text):
            add("graduation_year", "graduation", item, match.group("value"))
        for match in EMPLOYMENT_DATE.finditer(item.text):
            add("employment_date", "employment", item, match.group("value"))
        authorization = _authorization_value(item.text)
        if authorization:
            add("work_authorization", "authorization", item, authorization)
        status = _employment_status(item.text)
        if status:
            add("employment_status", "current", item, status)
        for claim in item.atomic_claims:
            for metric in claim.metrics:
                kind = (
                    "percentage"
                    if metric.unit == "percent"
                    else "money"
                    if metric.unit in {"inr", "usd", "eur", "gbp", "rupee", "dollar"}
                    else "count"
                )
                scope = _conflict_scope(metric.scope)
                add(kind, f"{metric.unit}:{scope}", item, metric.value)
    return [
        {
            "kind": kind,
            "scope": scope,
            "status": "unresolved",
            "values": records,
            "evidence_ids": [record["evidence_id"] for record in records],
        }
        for (kind, scope), records in values.items()
        if len({record["value"] for record in records}) > 1
    ]
