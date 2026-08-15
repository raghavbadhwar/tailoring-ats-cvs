"""Deterministic factual and ownership safety checks for CV edits."""
from __future__ import annotations

import re
from typing import Iterable

from .evidence import EvidenceLedger, detect_ownership, ownership_rank
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


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"(?<![A-Za-z])\d+(?:[.,]\d+)?%?", text))


def _contains_alias(text: str, alias: str) -> bool:
    return re.search(
        rf"(?<![a-z0-9]){re.escape(alias.lower())}(?![a-z0-9])",
        text.lower(),
    ) is not None


def _contains_term(text: str, canonical: str) -> bool:
    return any(_contains_alias(text, alias) for alias in TERM_ALIASES.get(canonical, (canonical,)))


def _unsupported_terms(expected: str, replacement: str, evidence_text: str) -> list[str]:
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
    return {token.lower() for token in re.findall(r"[A-Za-z][A-Za-z-]+", text)}


def validate_change(change: dict, ledger: EvidenceLedger) -> None:
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
    if operation not in {"replace", "replace_span", "insert_after", "insert_before", "delete_span"}:
        raise ValueError(f"change {change_id} uses unsupported operation: {operation}")
    if operation in {"replace", "replace_span", "delete_span"} and not expected:
        raise ValueError(f"change {change_id} has no exact expected text")
    if operation != "delete_span" and not replacement:
        raise ValueError(f"change {change_id} has no replacement text")
    if operation in {"replace", "replace_span"} and expected == replacement:
        raise ValueError(f"change {change_id} is a no-op")

    original_ownership = detect_ownership(expected)
    replacement_ownership = detect_ownership(replacement)
    evidence_limit = max(ownership_rank(item.ownership) for item in evidence)
    allowed_rank = max(ownership_rank(original_ownership), evidence_limit)
    if ownership_rank(replacement_ownership) > allowed_rank:
        raise ValueError(
            f"ownership escalation: {original_ownership} to {replacement_ownership} exceeds supporting evidence"
        )

    original_numbers = _numbers(expected)
    evidence_text = "\n".join(item.text for item in evidence)
    evidence_numbers = _numbers(evidence_text)
    introduced_numbers = _numbers(replacement) - original_numbers - evidence_numbers
    if introduced_numbers:
        raise ValueError(
            "unsupported numeric claims introduced: " + ", ".join(sorted(introduced_numbers))
        )

    introduced_terms = _unsupported_terms(expected, replacement, evidence_text)
    if introduced_terms:
        raise ValueError(
            "unsupported qualification terms introduced: " + ", ".join(sorted(introduced_terms))
        )

    baseline_tokens = _tokens(expected + "\n" + evidence_text)
    introduced_status = sorted(
        term
        for term in PROTECTED_STATUS_TERMS
        if term in _tokens(replacement) and term not in baseline_tokens
    )
    if introduced_status:
        raise ValueError(
            "protected status claims introduced without evidence: " + ", ".join(introduced_status)
        )

    # Employer-like entities are protected when introduced through explicit
    # employment phrasing. This avoids rejecting ordinary sentence casing.
    employer_mentions = re.findall(r"\b(?:at|for)\s+([A-Z][A-Za-z0-9&.-]+(?:\s+[A-Z][A-Za-z0-9&.-]+){0,3})", replacement)
    evidence_entities = set(re.findall(r"\b[A-Z][A-Za-z0-9&.-]+(?:\s+[A-Z][A-Za-z0-9&.-]+){0,3}\b", expected + "\n" + evidence_text))
    unsupported_entities = [entity for entity in employer_mentions if entity not in evidence_entities]
    if unsupported_entities:
        raise ValueError(
            "unsupported employer or organization introduced: " + ", ".join(unsupported_entities)
        )


def validate_changes(changes: Iterable[dict], ledger: EvidenceLedger) -> None:
    seen: set[str] = set()
    for change in changes:
        change_id = str(change.get("id") or "")
        if not change_id or change_id in seen:
            raise ValueError("change IDs must be non-empty and unique")
        seen.add(change_id)
        validate_change(change, ledger)
