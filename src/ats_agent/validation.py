"""Deterministic safety checks for proposed CV edits."""
from __future__ import annotations

import re

from .evidence import EvidenceLedger, detect_ownership, ownership_rank
from .requirements import TERM_ALIASES


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"(?<![A-Za-z])\d+(?:[.,]\d+)?%?", text))


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


def validate_change(change: dict, ledger: EvidenceLedger) -> None:
    if not change.get("supported"):
        raise ValueError(f"change {change.get('id', '<unknown>')} is unsupported")
    evidence_ids = change.get("evidence_ids") or []
    if not evidence_ids:
        raise ValueError(
            f"change {change.get('id', '<unknown>')} has no evidence references"
        )
    evidence = ledger.require(evidence_ids)

    expected = str(change.get("expected_text", ""))
    replacement = str(change.get("replacement_text", ""))
    if not expected:
        raise ValueError(
            f"change {change.get('id', '<unknown>')} has no exact expected text"
        )
    if not replacement:
        raise ValueError(
            f"change {change.get('id', '<unknown>')} has no replacement text"
        )
    if expected == replacement:
        raise ValueError(f"change {change.get('id', '<unknown>')} is a no-op")

    original_ownership = detect_ownership(expected)
    replacement_ownership = detect_ownership(replacement)
    evidence_limit = max(ownership_rank(item.ownership) for item in evidence)
    allowed_rank = max(ownership_rank(original_ownership), evidence_limit)
    if ownership_rank(replacement_ownership) > allowed_rank:
        raise ValueError(
            f"ownership escalation: {original_ownership} to {replacement_ownership} "
            f"exceeds supporting evidence"
        )

    original_numbers = _numbers(expected)
    evidence_numbers = set().union(*(_numbers(item.text) for item in evidence))
    introduced_numbers = _numbers(replacement) - original_numbers - evidence_numbers
    if introduced_numbers:
        raise ValueError(
            "unsupported numeric claims introduced: "
            + ", ".join(sorted(introduced_numbers))
        )

    evidence_text = "\n".join(item.text for item in evidence)
    introduced_terms = _unsupported_terms(expected, replacement, evidence_text)
    if introduced_terms:
        raise ValueError(
            "unsupported qualification terms introduced: "
            + ", ".join(sorted(introduced_terms))
        )
