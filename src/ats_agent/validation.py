"""Deterministic factual, metric-binding, and ownership safety checks."""
from __future__ import annotations

import re
from typing import Iterable

from .evidence import (
    AtomicClaim,
    EvidenceItem,
    EvidenceLedger,
    MetricBinding,
    atomic_claims_from_text,
    detect_ownership,
    ownership_rank,
)
from .requirements import TERM_ALIASES

PROTECTED_STATUS_TERMS = {
    "production",
    "deployed",
    "live",
    "enterprise",
    "customer",
    "customers",
    "user",
    "users",
    "revenue",
    "profit",
    "savings",
    "patent",
    "certified",
    "award-winning",
}

SCOPE_STOP_WORDS = {
    "a",
    "an",
    "and",
    "at",
    "automated",
    "built",
    "by",
    "contributed",
    "created",
    "developed",
    "for",
    "from",
    "helped",
    "implemented",
    "improved",
    "in",
    "increased",
    "of",
    "on",
    "processed",
    "processing",
    "reduced",
    "supported",
    "that",
    "the",
    "through",
    "to",
    "using",
    "validated",
    "with",
}


def _numbers(text: str) -> set[str]:
    return set(
        re.findall(r"(?<![A-Za-z])\d+(?:[.,]\d+)?%?", text)
    )


def _contains_alias(text: str, alias: str) -> bool:
    return (
        re.search(
            rf"(?<![a-z0-9]){re.escape(alias.lower())}(?![a-z0-9])",
            text.lower(),
        )
        is not None
    )


def _contains_term(text: str, canonical: str) -> bool:
    return any(
        _contains_alias(text, alias)
        for alias in TERM_ALIASES.get(canonical, (canonical,))
    )


def _unsupported_terms(
    expected: str,
    replacement: str,
    evidence_text: str,
) -> list[str]:
    introduced: list[str] = []
    for canonical in TERM_ALIASES:
        if (
            _contains_term(replacement, canonical)
            and not _contains_term(expected, canonical)
            and not _contains_term(evidence_text, canonical)
        ):
            introduced.append(canonical)
    return introduced


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z-]+", text)
    }


def _normalized_text(text: str) -> str:
    return " ".join(
        re.findall(r"[a-z0-9]+", text.lower())
    ).strip()


def near_duplicate_cv_lines(text: str, resume_text: str) -> list[str]:
    """Return conservative near-duplicates for review; callers must not insert them."""

    target = set(_normalized_text(text).split())
    if len(target) < 4:
        return []
    warnings: list[str] = []
    for line in resume_text.splitlines():
        candidate = set(_normalized_text(line).split())
        if not candidate or candidate == target:
            continue
        similarity = len(target & candidate) / len(target | candidate)
        if similarity >= 0.8:
            warnings.append(line.strip())
    return warnings


def _source_evidence_matches(
    expected: str,
    evidence: Iterable[EvidenceItem],
) -> bool:
    target = _normalized_text(expected)
    return any(_normalized_text(item.text) == target for item in evidence)


def _metric_claims(
    text: str,
    *,
    candidate_id: str,
) -> tuple[AtomicClaim, ...]:
    return atomic_claims_from_text(
        text,
        candidate_id=candidate_id,
        source_file="<proposed-change>",
        source_span="generated",
        verification_status="unverified",
    )


def _scope_tokens(metric: MetricBinding) -> set[str]:
    tokens: set[str] = set()
    for raw in re.findall(r"[A-Za-z][A-Za-z-]+", metric.scope.lower()):
        token = raw[:-1] if raw.endswith("s") and len(raw) > 3 else raw
        if token == metric.unit or token in SCOPE_STOP_WORDS:
            continue
        tokens.add(token)
    return tokens


def _same_metric_binding(
    candidate: MetricBinding,
    support: MetricBinding,
) -> bool:
    if candidate.value != support.value or candidate.unit != support.unit:
        return False
    candidate_scope = _scope_tokens(candidate)
    support_scope = _scope_tokens(support)
    if not candidate_scope and not support_scope:
        return True
    return bool(candidate_scope & support_scope)


def _all_metrics(
    claims: Iterable[AtomicClaim],
) -> tuple[MetricBinding, ...]:
    return tuple(
        metric
        for claim in claims
        for metric in claim.metrics
    )


def _validate_metric_bindings(
    expected: str,
    replacement: str,
    evidence: Iterable[EvidenceItem],
    *,
    candidate_id: str,
) -> None:
    replacement_metrics = _all_metrics(
        _metric_claims(replacement, candidate_id=candidate_id)
    )
    if not replacement_metrics:
        return
    expected_metrics = _all_metrics(
        _metric_claims(expected, candidate_id=candidate_id)
    )
    evidence_metrics = tuple(
        metric
        for item in evidence
        for claim in item.atomic_claims
        for metric in claim.metrics
    )
    for metric in replacement_metrics:
        if any(
            _same_metric_binding(metric, support)
            for support in (*expected_metrics, *evidence_metrics)
        ):
            continue
        raise ValueError(
            "metric binding is unsupported for "
            f"{metric.value} {metric.unit}: {metric.scope}"
        )


def validate_change(
    change: dict,
    ledger: EvidenceLedger,
    *,
    resume_text: str | None = None,
) -> None:
    change_id = change.get("id", "<unknown>")
    if not change.get("supported"):
        raise ValueError(f"change {change_id} is unsupported")
    evidence_ids = change.get("evidence_ids") or []
    if not evidence_ids:
        raise ValueError(f"change {change_id} has no evidence references")
    evidence = ledger.require(evidence_ids)

    operation = change.get("operation") or "replace_span"
    expected = str(change.get("expected_text", ""))
    replacement = str(change.get("replacement_text", ""))
    allowed_operations = {
        "replace",
        "replace_span",
        "insert_after",
        "insert_before",
        "delete_span",
    }
    if operation not in allowed_operations:
        raise ValueError(
            f"change {change_id} uses unsupported operation: {operation}"
        )
    if operation in {"replace", "replace_span", "delete_span"} and not expected:
        raise ValueError(f"change {change_id} has no exact expected text")
    if operation != "delete_span" and not replacement:
        raise ValueError(f"change {change_id} has no replacement text")
    if operation in {"replace", "replace_span"} and (
        expected == replacement
        or _normalized_text(expected) == _normalized_text(replacement)
    ):
        raise ValueError(f"change {change_id} is a no-op")
    if resume_text and operation != "delete_span":
        normalized_replacement = _normalized_text(replacement)
        normalized_expected = _normalized_text(expected)
        existing = {
            _normalized_text(line)
            for line in resume_text.splitlines()
            if _normalized_text(line) and _normalized_text(line) != normalized_expected
        }
        if normalized_replacement in existing:
            raise ValueError(
                f"change {change_id} duplicates existing CV text"
            )
    if operation in {"replace", "replace_span", "delete_span"}:
        if not _source_evidence_matches(expected, evidence):
            raise ValueError(
                f"change {change_id} cited evidence does not support the "
                "edited source span"
            )

    original_ownership = detect_ownership(expected)
    replacement_ownership = detect_ownership(replacement)
    evidence_limit = max(
        ownership_rank(item.ownership) for item in evidence
    )
    allowed_rank = max(
        ownership_rank(original_ownership),
        evidence_limit,
    )
    if ownership_rank(replacement_ownership) > allowed_rank:
        raise ValueError(
            "ownership escalation: "
            f"{original_ownership} to {replacement_ownership} "
            "exceeds supporting evidence"
        )

    original_numbers = _numbers(expected)
    evidence_text = "\n".join(item.text for item in evidence)
    evidence_numbers = _numbers(evidence_text)
    introduced_numbers = (
        _numbers(replacement) - original_numbers - evidence_numbers
    )
    if introduced_numbers:
        raise ValueError(
            "unsupported numeric claims introduced: "
            + ", ".join(sorted(introduced_numbers))
        )
    _validate_metric_bindings(
        expected,
        replacement,
        evidence,
        candidate_id=ledger.candidate_id,
    )

    introduced_terms = _unsupported_terms(
        expected,
        replacement,
        evidence_text,
    )
    if introduced_terms:
        raise ValueError(
            "unsupported qualification terms introduced: "
            + ", ".join(sorted(introduced_terms))
        )

    baseline_tokens = _tokens(expected + "\n" + evidence_text)
    introduced_status = sorted(
        term
        for term in PROTECTED_STATUS_TERMS
        if term in _tokens(replacement) and term not in baseline_tokens
    )
    if introduced_status:
        raise ValueError(
            "protected status claims introduced without evidence: "
            + ", ".join(introduced_status)
        )

    employer_mentions = re.findall(
        r"\b(?:at|for)\s+"
        r"([A-Z][A-Za-z0-9&.-]+"
        r"(?:\s+[A-Z][A-Za-z0-9&.-]+){0,3})",
        replacement,
    )
    evidence_entities = set(
        re.findall(
            r"\b[A-Z][A-Za-z0-9&.-]+"
            r"(?:\s+[A-Z][A-Za-z0-9&.-]+){0,3}\b",
            expected + "\n" + evidence_text,
        )
    )
    unsupported_entities = [
        entity
        for entity in employer_mentions
        if entity not in evidence_entities
    ]
    if unsupported_entities:
        raise ValueError(
            "unsupported employer or organization introduced: "
            + ", ".join(unsupported_entities)
        )


def validate_changes(
    changes: Iterable[dict],
    ledger: EvidenceLedger,
) -> None:
    seen: set[str] = set()
    for change in changes:
        change_id = str(change.get("id") or "")
        if not change_id or change_id in seen:
            raise ValueError("change IDs must be non-empty and unique")
        seen.add(change_id)
        validate_change(change, ledger)
