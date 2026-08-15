"""Conservative, evidence-backed CV rewrite proposals."""
from __future__ import annotations

import re
from typing import Iterable

from .evidence import EvidenceLedger, detect_ownership
from .validation import validate_change


def _safe_ownership_language(text: str) -> str:
    rules = (
        (r"^Helped\s+build\b", "Contributed to building"),
        (r"^Helped\b", "Contributed to"),
        (r"^Worked\s+on\b", "Contributed to"),
        (r"^Assisted\s+with\b", "Supported"),
        (r"^Assisted\b", "Supported"),
        (r"^Participated\s+in\b", "Contributed to"),
        (r"^Collaborated\s+on\b", "Contributed to"),
        (r"^Responsible\s+for\b", "Contributed to"),
    )
    result = text
    for pattern, replacement in rules:
        updated = re.sub(pattern, replacement, result, count=1, flags=re.IGNORECASE)
        if updated != result:
            return updated
    return result


def _surface_term(text: str, term: str) -> str:
    if term.lower() in text.lower():
        return text
    if term == "workflow automation":
        patterns = (
            (r"(?:building\s+)?automated\s+order\s+workflows", "workflow automation for orders"),
            (r"(?:building\s+)?automated\s+procurement\s+workflows", "workflow automation for procurement"),
            (r"automated\s+workflows", "workflow automation"),
            (r"workflow\s+systems", "workflow automation systems"),
        )
        for pattern, replacement in patterns:
            updated = re.sub(pattern, replacement, text, count=1, flags=re.IGNORECASE)
            if updated != text:
                return updated
    if term == "human-in-the-loop":
        for pattern in (r"approval-first", r"approval[- ]gated", r"human approval"):
            updated = re.sub(pattern, "human-in-the-loop", text, count=1, flags=re.IGNORECASE)
            if updated != text:
                return updated
    if term == "product requirements":
        updated = re.sub(r"\bPRD\b", "product requirements document (PRD)", text, count=1)
        if updated != text:
            return updated
    return text


def _matches_by_evidence(matches: Iterable[dict]) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for match in matches:
        if match.get("coverage") not in {"direct", "transferable"}:
            continue
        for evidence_id in match.get("evidence_ids", []):
            index.setdefault(evidence_id, []).append(match)
    return index


def propose_supported_changes(
    cv: str,
    requirements: Iterable[dict],
    matches: Iterable[dict],
    ledger: EvidenceLedger,
) -> list[dict]:
    del requirements  # requirements are represented by the traceable match records
    match_index = _matches_by_evidence(matches)
    changes: list[dict] = []

    for item in ledger.items:
        if item.source != "resume" or item.text not in cv:
            continue
        original = item.text
        replacement = _safe_ownership_language(original)
        introduced_terms: list[str] = []
        for match in match_index.get(item.id, []):
            for term in match.get("normalized_terms", []):
                updated = _surface_term(replacement, term)
                if updated != replacement:
                    replacement = updated
                    introduced_terms.append(term)

        if replacement == original:
            continue

        change = {
            "id": f"C{len(changes) + 1}",
            "kind": "language-rewrite",
            "operation": "replace_span",
            "expected_text": original,
            "replacement_text": replacement,
            "evidence_ids": [item.id],
            "supported": True,
            "ownership_before": item.ownership,
            "ownership_after": detect_ownership(replacement),
            "terms_introduced": introduced_terms,
            "reason": "Improve clarity and surface job terminology already supported by candidate evidence.",
        }
        validate_change(change, ledger)
        changes.append(change)

    covered_requirement_ids = {match["requirement_id"] for match in matches if match.get("coverage") in {"direct", "transferable"}}
    for match in matches:
        if match["requirement_id"] in covered_requirement_ids:
            continue
        for term in match.get("normalized_terms", []):
            changes.append(
                {
                    "id": f"C{len(changes) + 1}",
                    "kind": "qualification-gap",
                    "operation": "none",
                    "expected_text": "",
                    "replacement_text": term,
                    "evidence_ids": [],
                    "supported": False,
                    "reason": "No candidate evidence supports this requirement; do not insert it into the CV.",
                }
            )
    return changes
