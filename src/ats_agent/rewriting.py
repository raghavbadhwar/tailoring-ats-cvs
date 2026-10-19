"""Evidence-backed, section-aware rewrite proposals."""
from __future__ import annotations

import re
import hashlib
from collections.abc import Iterable

from .evidence import EvidenceItem, EvidenceLedger
from .providers import (
    DeterministicRewriteProvider,
    RewriteContext,
    RewriteProvider,
    generate_with_fallback,
)
from .requirements import TERM_ALIASES
from .hashing import canonical_json
from .validation import near_duplicate_cv_lines, validate_change

_SECTION_HEADINGS: dict[str, tuple[str, ...]] = {
    "summary": ("summary", "profile", "professional summary"),
    "experience": (
        "experience",
        "work experience",
        "professional experience",
        "employment",
    ),
    "projects": ("projects", "selected projects", "project experience"),
    "education": ("education", "academic background"),
    "leadership": ("leadership", "positions of responsibility"),
    "certifications": ("certifications", "certificates", "licenses"),
    "skills": ("skills", "technical skills", "core skills"),
}


def _matches_by_evidence(matches: Iterable[dict]) -> dict[str, list[dict]]:
    """Index only skill/capability matches that are safe to phrase-optimize."""

    index: dict[str, list[dict]] = {}
    for match in matches:
        if (
            match.get("kind") != "skill"
            or match.get("coverage") not in {"direct", "transferable"}
        ):
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


def _validated_change(change: dict, ledger: EvidenceLedger, cv: str) -> dict:
    valid_variants: list[dict] = []
    for variant in change.get("variants") or []:
        candidate = {**change, "replacement_text": variant["text"]}
        try:
            validate_change(candidate, ledger, resume_text=cv)
        except ValueError:
            continue
        coverage_delta = [
            term
            for term in change.get("terms_introduced", [])
            if any(
                re.search(
                    rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])",
                    variant["text"].lower(),
                )
                and not re.search(
                    rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])",
                    str(change.get("expected_text", "")).lower(),
                )
                for alias in TERM_ALIASES.get(term, (term,))
            )
        ]
        valid_variants.append({**variant, "coverage_delta": coverage_delta})
    if not valid_variants:
        raise ValueError(f"no safe rewrite variants for {change.get('id')}")
    change["variants"] = valid_variants
    change["default_variant"] = _default_variant(valid_variants)
    change["replacement_text"] = next(
        variant["text"]
        for variant in valid_variants
        if variant["id"] == change["default_variant"]
    )
    selected = next(
        variant
        for variant in valid_variants
        if variant["id"] == change["default_variant"]
    )
    change["coverage_delta"] = selected["coverage_delta"]
    change["value_reason"] = (
        "Adds supported requirement terminology."
        if change["coverage_delta"]
        else "Improves wording without changing the supported candidate claim."
    )
    return change


def _normalized_heading(text: str) -> str:
    return text.strip().rstrip(":").lower()


def _heading_section(text: str) -> str | None:
    normalized = _normalized_heading(text)
    for section, headings in _SECTION_HEADINGS.items():
        if normalized in headings:
            return section
    return None


def _resume_section_for_item(cv: str, item: EvidenceItem) -> str:
    if item.line_number is None:
        return "projects"
    section = "summary"
    for index, line in enumerate(cv.splitlines(), 1):
        if index > item.line_number:
            break
        detected = _heading_section(line)
        if detected:
            section = detected
    return section


def _supporting_section(item: EvidenceItem) -> str:
    body = f"{item.source_file} {item.text}".lower()
    if re.search(
        r"\b(?:bachelor|master|degree|university|college|cgpa|gpa|education)\b",
        body,
    ):
        return "education"
    if re.search(
        r"\b(?:certificate|certification|certified|license|licensed)\b",
        body,
    ):
        return "certifications"
    if re.search(
        r"\b(?:worked at|intern(?:ed|ship)?|employed|employment|"
        r"work experience|professional experience|role at|analyst at|"
        r"associate at|consultant at)\b",
        body,
    ):
        return "experience"
    if re.search(
        r"\b(?:president|secretary|chair|headed|led a team|managed a team|"
        r"leadership)\b",
        body,
    ):
        return "leadership"
    return "projects"


def _target_section(cv: str, item: EvidenceItem) -> str:
    return (
        _resume_section_for_item(cv, item)
        if item.source == "resume"
        else _supporting_section(item)
    )


def _find_section_anchor(
    cv: str,
    ledger: EvidenceLedger,
    target_section: str,
) -> dict:
    headings = set(_SECTION_HEADINGS.get(target_section, (target_section,)))
    lines = cv.splitlines()
    for index, line in enumerate(lines, 1):
        if _normalized_heading(line) in headings:
            return {
                "part": "text",
                "line_number": index,
                "heading": line.strip(),
            }
    if target_section != "projects":
        project_anchor = _find_section_anchor(cv, ledger, "projects")
        if project_anchor.get("heading"):
            return project_anchor
    resume_items = [item for item in ledger.items if item.source == "resume"]
    if resume_items:
        return _anchor_for(resume_items[-1])
    return {"part": "text", "line_number": len(lines), "heading": ""}


def _variants_for(
    provider: RewriteProvider,
    *,
    text: str,
    terms: Iterable[str],
    target_section: str,
    evidence_ids: tuple[str, ...],
    ownership_ceiling: str,
) -> tuple[list[dict], str, str, str | None, str, str]:
    context = RewriteContext(
        original_text=text,
        terms=tuple(dict.fromkeys(str(term) for term in terms)),
        target_section=target_section,
        max_characters=max(120, min(500, len(text) * 2 + 40)),
        evidence_ids=evidence_ids,
        ownership_ceiling=ownership_ceiling,
    )
    variants, provider_id, provider_version, fallback = generate_with_fallback(provider, context)
    return (
        variants,
        provider_id,
        provider_version,
        fallback,
        hashlib.sha256(canonical_json(context.__dict__)).hexdigest(),
        hashlib.sha256(canonical_json(variants)).hexdigest(),
    )


def propose_supported_changes(
    cv: str,
    requirements: Iterable[dict],
    matches: Iterable[dict],
    ledger: EvidenceLedger,
    provider: RewriteProvider | None = None,
) -> list[dict]:
    """Create evidence-bound proposals without editing the source document."""

    selected_provider = provider or DeterministicRewriteProvider()
    requirement_ids = {item["id"] for item in requirements}
    matches = list(matches)
    match_index = _matches_by_evidence(matches)
    changes: list[dict] = []
    normalized_resume = {
        " ".join(re.findall(r"[a-z0-9]+", item.text.lower()))
        for item in ledger.items
        if item.source == "resume"
    }

    for item in ledger.items:
        if item.source != "resume" or item.text not in cv:
            continue
        terms = [
            term
            for match in match_index.get(item.id, [])
            for term in match.get("normalized_terms", [])
        ]
        if not terms:
            continue
        section = _target_section(cv, item)
        variants, provider_id, provider_version, fallback_reason, input_digest, output_digest = _variants_for(
            selected_provider,
            text=item.text,
            terms=terms,
            target_section=section,
            evidence_ids=(item.id,),
            ownership_ceiling=item.ownership,
        )
        if not variants or all(
            variant["text"] == item.text for variant in variants
        ):
            continue
        change = {
            "id": f"C{len(changes) + 1}",
            "kind": "language-rewrite",
            "operation": "replace_span",
            "anchor": _anchor_for(item),
            "target_section": section,
            "expected_text": item.text,
            "variants": variants,
            "evidence_ids": [item.id],
            "supported": True,
            "ownership_before": item.ownership,
            "terms_introduced": sorted(set(terms)),
            "provider": provider_id,
            "provider_version": provider_version,
            "provider_fallback": fallback_reason,
            "provider_input_digest": input_digest,
            "provider_output_digest": output_digest,
            "reason": (
                "Improve clarity and surface job terminology already "
                "supported by candidate evidence."
            ),
        }
        try:
            changes.append(_validated_change(change, ledger, cv))
        except ValueError:
            continue

    resume_ids = {item.id for item in ledger.items if item.source == "resume"}
    surfaced_ids: set[str] = set()
    for match in matches:
        if (
            match.get("kind") != "skill"
            or match.get("coverage") not in {"direct", "transferable"}
        ):
            continue
        supporting_ids = [
            evidence_id
            for evidence_id in match.get("evidence_ids", [])
            if evidence_id not in resume_ids
        ]
        for evidence_id in supporting_ids:
            if evidence_id in surfaced_ids:
                continue
            item = ledger.by_id()[evidence_id]
            if " ".join(re.findall(r"[a-z0-9]+", item.text.lower())) in normalized_resume:
                continue
            if near_duplicate_cv_lines(item.text, cv):
                continue
            terms = list(match.get("normalized_terms", []))
            section = _target_section(cv, item)
            anchor = _find_section_anchor(cv, ledger, section)
            variants, provider_id, provider_version, fallback_reason, input_digest, output_digest = _variants_for(
                selected_provider,
                text=item.text,
                terms=terms,
                target_section=section,
                evidence_ids=(item.id,),
                ownership_ceiling=item.ownership,
            )
            if not variants:
                continue
            change = {
                "id": f"C{len(changes) + 1}",
                "kind": "surface-evidence",
                "operation": "insert_after",
                "anchor": anchor,
                "target_section": section,
                "expected_text": str(anchor.get("heading") or ""),
                "variants": variants,
                "evidence_ids": [item.id],
                "supported": True,
                "ownership_before": item.ownership,
                "terms_introduced": sorted(set(terms)),
                "provider": provider_id,
                "provider_version": provider_version,
                "provider_fallback": fallback_reason,
                "provider_input_digest": input_digest,
                "provider_output_digest": output_digest,
                "reason": (
                    "Surface candidate evidence relevant to a supported job "
                    "requirement in the correct CV section."
                ),
            }
            try:
                changes.append(_validated_change(change, ledger, cv))
                surfaced_ids.add(evidence_id)
            except ValueError:
                continue

    matched_requirement_ids = {
        match["requirement_id"]
        for match in matches
        if match.get("coverage") in {"direct", "transferable"}
    }
    for requirement_id in requirement_ids:
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
                "reason": (
                    "No candidate evidence supports this requirement; do not "
                    "insert it into the CV."
                ),
            }
        )
    return changes
