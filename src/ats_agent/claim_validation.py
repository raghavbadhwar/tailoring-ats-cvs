"""Fail-closed atomic claim extraction and rewrite entailment checks."""
from __future__ import annotations

import hashlib
import re
from decimal import Decimal
from typing import Iterable

from .evidence import detect_ownership
from .evidence import EvidenceLedger
from .models import AtomicClaim, SourceSpan


class ClaimValidationError(ValueError):
    code: str
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def claims_from_text(text: str, candidate_id: str, artifact_id: str = "resume") -> tuple[AtomicClaim, ...]:
    claims = []
    for number, line in enumerate(text.splitlines(), 1):
        source = line.strip(" -•\t")
        if not source:
            continue
        metric = re.search(r"\b(\d+(?:\.\d+)?)\s*(%|[A-Za-z][A-Za-z -]{0,20})?", source)
        technologies = tuple(sorted(set(re.findall(r"\b(?:Python|SQL|Excel|Power BI|Tableau|Docker|Kubernetes|AWS|React|GitHub)\b", source, re.I))))
        entities = tuple(re.findall(r"\b[A-Z][A-Za-z0-9&.-]+(?:\s+[A-Z][A-Za-z0-9&.-]+){0,2}\b", source))
        action = next(iter(re.findall(r"\b(built|developed|designed|processed|analysed|analyzed|led|supported|contributed)\b", source, re.I)), None)
        claim_id = hashlib.sha256(f"{candidate_id}|{artifact_id}|{number}|{source}".encode()).hexdigest()[:16]
        claims.append(AtomicClaim(claim_id=claim_id, candidate_id=candidate_id, artifact_id=artifact_id,
            source_span=SourceSpan(part="text", line_number=number), source_text=source, action=action.lower() if action else None,
            technologies=technologies, entities=entities, metric_value=Decimal(metric.group(1)) if metric else None,
            metric_unit=metric.group(2).strip() if metric and metric.group(2) else None,
            metric_scope=source if metric else None, ownership=detect_ownership(source), confidence=0.8))
    return tuple(claims)


def claims_from_ledger(ledger: EvidenceLedger) -> tuple[AtomicClaim, ...]:
    claims = []
    for item in ledger.items:
        metric = re.search(r"\b(\d+(?:\.\d+)?)\s*(%|[A-Za-z][A-Za-z -]{0,20})?", item.text)
        claims.append(AtomicClaim(
            claim_id=f"AC:{item.id}", candidate_id=item.candidate_id, artifact_id=item.source_sha256[:16],
            source_span=SourceSpan(part=item.part, paragraph_index=item.paragraph_index, line_number=item.line_number),
            source_text=item.text, action=next(iter(re.findall(r"\b(built|developed|designed|processed|analysed|analyzed|led|supported|contributed)\b", item.text, re.I)), None),
            technologies=tuple(re.findall(r"\b(?:Python|SQL|Excel|Power BI|Tableau|Docker|Kubernetes|AWS|React|GitHub)\b", item.text, re.I)),
            entities=tuple(re.findall(r"\b[A-Z][A-Za-z0-9&.-]+(?:\s+[A-Z][A-Za-z0-9&.-]+){0,2}\b", item.text)),
            metric_value=Decimal(metric.group(1)) if metric else None, metric_unit=metric.group(2).strip() if metric and metric.group(2) else None,
            metric_scope=item.text if metric else None, ownership=item.ownership, verification=item.verification_status, confidence={"low": 0.4, "medium": 0.7, "high": 0.9}[item.confidence],
        ))
    return tuple(claims)


def verify_variant_claims(original_text: str, proposed_text: str, cited_claims: Iterable[AtomicClaim]) -> None:
    claims = tuple(cited_claims)
    evidence = "\n".join(claim.source_text for claim in claims)
    original_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?", original_text))
    proposed_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?", proposed_text))
    evidence_numbers = {str(claim.metric_value) + (claim.metric_unit or "") for claim in claims if claim.metric_value is not None}
    if proposed_numbers - original_numbers - evidence_numbers:
        raise ClaimValidationError("metric binding", "metric binding cannot use an unrelated evidence number")
    protected = {"production", "deployed", "live", "revenue", "customer", "certified", "award"}
    introduced = {x for x in protected if x in proposed_text.lower() and x not in (original_text + evidence).lower()}
    if introduced:
        raise ClaimValidationError("protected claim", "unsupported protected claim: " + ", ".join(sorted(introduced)))
