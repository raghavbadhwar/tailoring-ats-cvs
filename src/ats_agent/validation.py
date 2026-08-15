"""Deterministic safety checks for proposed CV edits."""
from __future__ import annotations

import re

from .evidence import EvidenceLedger, detect_ownership, ownership_rank


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"(?<![A-Za-z])\d+(?:[.,]\d+)?%?", text))


def validate_change(change: dict, ledger: EvidenceLedger) -> None:
    if not change.get("supported"):
        raise ValueError(f"change {change.get('id', '<unknown>')} is unsupported")
    evidence_ids = change.get("evidence_ids") or []
    if not evidence_ids:
        raise ValueError(f"change {change.get('id', '<unknown>')} has no evidence references")
    evidence = ledger.require(evidence_ids)

    expected = str(change.get("expected_text", ""))
    replacement = str(change.get("replacement_text", ""))
    if not expected:
        raise ValueError(f"change {change.get('id', '<unknown>')} has no exact expected text")
    if not replacement:
        raise ValueError(f"change {change.get('id', '<unknown>')} has no replacement text")
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
            "unsupported numeric claims introduced: " + ", ".join(sorted(introduced_numbers))
        )
