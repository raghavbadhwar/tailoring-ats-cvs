"""Evidence-backed rewrite variants and supported evidence surfacing."""
from __future__ import annotations

import re
from typing import Iterable

from .evidence import EvidenceItem, EvidenceLedger
from .validation import validate_change

GENERIC_PREFIXES = (
    r"^Results[- ]driven\s+",
    r"^Innovative\s+",
    r"^Passionate about\s+",
    r"^Cutting[- ]edge\s+",
)


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
    for pattern, replacement in rules:
        updated = re.sub(pattern, replacement, text, count=1, flags=re.IGNORECASE)
        if updated != text:
            return updated
    return text


def _remove_generic(text: str) -> str:
    result = text.strip()
    for pattern in GENERIC_PREFIXES:
        result = re.sub(pattern, "", result, count=1, flags=re.IGNORECASE)
    result = re.sub(r"\b(?:leveraged|utilized)\s+AI\b", "used AI", result, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", result).strip()


def _surface_term(text: str, term: str) -> str:
    if term.lower() in text.lower():
        return text
    replacements: dict[str, tuple[tuple[str, str], ...]] = {
        "workflow automation": (
            (r"(?:building\s+)?automated\s+order\s+workflows", "workflow automation for orders"),
            (r"(?:building\s+)?automated\s+procurement\s+workflows", "workflow automation for procurement"),
            (r"automated\s+workflows", "workflow automation"),
            (r"workflow\s+systems", "workflow automation systems"),
        ),
        "human-in-the-loop": (
            (r"approval-first", "human-in-the-loop"),
            (r"approval[- ]gated", "human-in-the-loop"),
            (r"human approval", "human-in-the-loop approval"),
        ),
        "product requirements": ((r"\bPRD\b", "product requirements document (PRD)"),),
        "retrieval-augmented generation": ((r"\bRAG\b", "retrieval-augmented generation (RAG)"),),
        "git": ((r"\bGitHub\b", "Git/GitHub"),),
    }
    for pattern, replacement in replacements.get(term, ()):
        updated = re.sub(pattern, replacement, text, count=1, flags=re.IGNORECASE)
        if updated != text:
            return updated
    return text


def _compact(text: str) -> str:
    result = re.sub(r"\b(?:successfully|various|multiple|really|very)\b", "", text, flags=re.IGNORECASE)
    result = re.sub(r"workflow automation for orders", "order-workflow automation", result, flags=re.IGNORECASE)
    result = re.sub(r"workflow automation for procurement", "procurement-workflow automation", result, flags=re.IGNORECASE)
    result = re.sub(r"\s+", " ", result).strip()
    return result


def _variants(original: str, terms: Iterable[str]) -> list[dict]:
    conservative = _safe_ownership_language(_remove_generic(original))
    balanced = conservative
    introduced: list[str] = []
    for term in terms:
        updated = _surface_term(balanced, term)
        if updated != balanced:
            balanced = updated
            introduced.append(term)
    compact = _compact(balanced)
    variants: list[dict] = []
    for variant_id, text in (
        ("conservative", conservative),
        ("balanced", balanced),
        ("compact", compact),
    ):
        if text and all(existing["text"] != text for existing in variants):
            variants.append({"id": variant_id, "text": text})
    return variants


def _matches_by_evidence(matches: Iterable[dict]) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for match in matches:
        if match.get("coverage") not in {"direct", "transferable"}:
            continue
        for evidence_id in match.get("evidence_ids", []):
            index.setdefault(evidence_id, []).append(match)
    return index


def _anchor_for(item: EvidenceItem) -> dict:
    return {
        "part": item.part,
        "paragraph_index": item.paragraph_index,
        "line_number": item.line_number,
        "source_span": item.source_span,
    }


def _default_variant(variants: list[dict]) -> str:
    ids = {variant["id"] for variant in variants}
    return "balanced" if "balanced" in ids else variants[0]["id"]


def _validated_change(change: dict, ledger: EvidenceLedger) -> dict:
    variants = change.get("variants") or []
    valid_variants: list[dict] = []
    for variant in variants:
        candidate = {**change, "replacement_text": variant["text"]}
        try:
            validate_change(candidate, ledger)
        except ValueError:
            continue
        valid_variants.append(variant)
    if not valid_variants:
        raise ValueError(f"no safe rewrite variants for {change.get('id')}")
    change["variants"] = valid_variants
    change["default_variant"] = _default_variant(valid_variants)
    change["replacement_text"] = next(
        variant["text"]
        for variant in valid_variants
        if variant["id"] == change["default_variant"]
    )
    return change


def _find_projects_anchor(cv: str, ledger: EvidenceLedger) -> dict:
    lines = cv.splitlines()
    for index, line in enumerate(lines, 1):
        if line.strip().rstrip(":").lower() in {"projects", "selected projects", "project experience"}:
            return {"part": "text", "line_number": index, "heading": line.strip()}
    resume_items = [item for item in ledger.items if item.source == "resume"]
    if resume_items:
        item = resume_items[-1]
        return _anchor_for(item)
    return {"part": "text", "line_number": len(lines), "heading": ""}


def propose_supported_changes(
    cv: str,
    requirements: Iterable[dict],
    matches: Iterable[dict],
    ledger: EvidenceLedger,
) -> list[dict]:
    requirement_index = {item["id"]: item for item in requirements}
    matches = list(matches)
    match_index = _matches_by_evidence(matches)
    changes: list[dict] = []

    for item in ledger.items:
        if item.source != "resume" or item.text not in cv:
            continue
        terms = [
            term
            for match in match_index.get(item.id, [])
            for term in match.get("normalized_terms", [])
        ]
        variants = _variants(item.text, terms)
        if not variants or all(variant["text"] == item.text for variant in variants):
            continue
        change = {
            "id": f"C{len(changes) + 1}",
            "kind": "language-rewrite",
            "operation": "replace_span",
            "anchor": _anchor_for(item),
            "expected_text": item.text,
            "variants": variants,
            "evidence_ids": [item.id],
            "supported": True,
            "ownership_before": item.ownership,
            "terms_introduced": sorted(set(terms)),
            "reason": "Improve clarity and surface job terminology already supported by candidate evidence.",
        }
        try:
            changes.append(_validated_change(change, ledger))
        except ValueError:
            continue

    # Surface supporting evidence that matches the JD but is absent from the CV.
    resume_ids = {item.id for item in ledger.items if item.source == "resume"}
    surfaced_ids: set[str] = set()
    anchor = _find_projects_anchor(cv, ledger)
    for match in matches:
        if match.get("coverage") not in {"direct", "transferable"}:
            continue
        supporting_ids = [eid for eid in match.get("evidence_ids", []) if eid not in resume_ids]
        for evidence_id in supporting_ids:
            if evidence_id in surfaced_ids:
                continue
            item = ledger.by_id()[evidence_id]
            terms = list(match.get("normalized_terms", []))
            variants = _variants(item.text, terms)
            if not variants:
                continue
            change = {
                "id": f"C{len(changes) + 1}",
                "kind": "surface-evidence",
                "operation": "insert_after",
                "anchor": anchor,
                "expected_text": str(anchor.get("heading") or ""),
                "variants": variants,
                "evidence_ids": [item.id],
                "supported": True,
                "ownership_before": item.ownership,
                "terms_introduced": sorted(set(terms)),
                "reason": "Surface verified candidate evidence that is relevant to a supported job requirement but absent from the current CV.",
            }
            try:
                changes.append(_validated_change(change, ledger))
                surfaced_ids.add(evidence_id)
            except ValueError:
                continue

    matched_requirement_ids = {match["requirement_id"] for match in matches if match.get("coverage") in {"direct", "transferable"}}
    for requirement_id, requirement in requirement_index.items():
        if requirement_id in matched_requirement_ids:
            continue
        changes.append(
            {
                "id": f"C{len(changes) + 1}",
                "kind": "qualification-gap",
                "operation": "none",
                "expected_text": "",
                "replacement_text": "",
                "variants": [],
                "evidence_ids": [],
                "supported": False,
                "requirement_id": requirement_id,
                "reason": "No candidate evidence supports this requirement; do not insert it into the CV.",
            }
        )
    return changes
