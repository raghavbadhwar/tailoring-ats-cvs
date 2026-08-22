"""Human-readable chat-first summaries for CLI payloads.

Summaries go to stderr so stdout stays machine-readable JSON. They report
only what is already in the payload — no scores, probabilities, or claims
about ATS outcomes.
"""
from __future__ import annotations

from typing import Any

_COVERAGE_RANK = {
    "direct": 0,
    "transferable": 1,
    "equivalent": 1,
    "unknown": 2,
    "conservative unknown": 2,
    "unsupported": 3,
}

_TEXT_LIMIT = 96


def _truncate(text: str, limit: int = _TEXT_LIMIT) -> str:
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _anchor_label(change: dict[str, Any]) -> str:
    anchor = change.get("anchor") or {}
    heading = str(anchor.get("heading") or "").strip()
    if heading:
        return f'after "{heading}"'
    section = change.get("target_section")
    paragraph = anchor.get("paragraph_index")
    line = anchor.get("line_number")
    if paragraph is not None:
        return f"near paragraph {paragraph}"
    if line is not None:
        return f"near line {line}"
    return f"into {section}" if section else "into document"


def _coverage_rows(proposal: dict[str, Any]) -> list[tuple[str, str, int]]:
    """Aggregate duplicate term rows into one line per unique term set."""

    aggregated: dict[tuple[str, ...], dict[str, Any]] = {}
    for mapping in proposal.get("requirement_evidence") or []:
        terms = tuple(
            str(term)
            for term in (mapping.get("normalized_terms") or [])
        )
        if not terms:
            continue
        coverage = str(mapping.get("coverage") or "unknown").lower()
        slot = aggregated.setdefault(
            terms,
            {"rank": 99, "label": coverage, "evidence": set()},
        )
        slot["rank"] = min(slot["rank"], _COVERAGE_RANK.get(coverage, 99))
        if _COVERAGE_RANK.get(coverage, 99) < _COVERAGE_RANK.get(
            slot["label"], 99
        ):
            slot["label"] = coverage
        for evidence_id in mapping.get("evidence_ids") or []:
            slot["evidence"].add(str(evidence_id))
    ordered = sorted(
        aggregated.items(),
        key=lambda pair: (
            pair[1]["rank"],
            -len(pair[1]["evidence"]),
            pair[0],
        ),
    )
    return [
        (" ".join(terms), data["label"], len(data["evidence"]))
        for terms, data in ordered
    ]


def render_proposal_summary(proposal: dict[str, Any]) -> str:
    """Render a compact operator summary for a proposal payload."""

    lines: list[str] = []
    candidate = proposal.get("candidate_id") or "unknown-candidate"
    proposal_id = proposal.get("proposal_id") or "unknown-proposal"
    status = proposal.get("status") or "unknown"
    digest = str(proposal.get("proposal_digest") or "")
    lines.append("── CV tailoring summary ─────────────────────────────")
    lines.append(f"candidate : {candidate}")
    lines.append(f"proposal  : {proposal_id} ({status})")
    if digest:
        lines.append(f"digest    : {digest[:16]}…")

    requirements = proposal.get("requirements") or []
    lines.append(f"requirements analysed : {len(requirements)}")
    rows = _coverage_rows(proposal)
    if rows:
        lines.append("coverage")
        for terms, label, evidence_count in rows:
            note = f" ({evidence_count} evidence)" if evidence_count else ""
            lines.append(f"  {terms:<28} {label}{note}")

    changes = proposal.get("changes") or []
    supported = [c for c in changes if c.get("kind") == "surface-evidence"]
    gaps = [c for c in changes if c.get("kind") != "surface-evidence"]

    lines.append(f"proposed changes : {len(supported)} supported")
    for change in supported:
        default = change.get("default_variant") or ""
        variants = change.get("variants") or []
        variant_ids = ", ".join(
            f"{v.get('id')}{'*' if v.get('id') == default else ''}"
            for v in variants
        )
        lines.append(
            f"  {change.get('id')} insert {_anchor_label(change)}"
            f"  variants[{variant_ids}]"
        )
        first_text = str(variants[0].get("text")) if variants else ""
        lines.append(f"      {_truncate(first_text)}")

    if gaps:
        lines.append(f"refused gaps : {len(gaps)} (never inserted without evidence)")
        for gap in gaps[:3]:
            reason = _truncate(gap.get("reason") or "", 72)
            lines.append(f"  {gap.get('id')}: {reason}")

    lines.append("next steps")
    if supported:
        selections = []
        for change in supported:
            default = change.get("default_variant") or (
                (change.get("variants") or [{}])[0].get("id")
            )
            if default:
                selections.append(f"--select {change.get('id')}:{default}")
        shown = " ".join(selections[:4])
        more = "" if len(selections) <= 4 else " …"
        lines.append(
            "  ats-agent approve <proposal.json> "
            f"{shown}{more} --output approval.json --output-document tailored.docx"
        )
        lines.append("  ats-agent apply approval.json")
        lines.append("  ats-agent validate tailored.docx")
    else:
        lines.append(
            "  no supported changes to approve; close evidence gaps and re-run propose"
        )
    lines.append("─────────────────────────────────────────────────────")
    return "\n".join(lines) + "\n"
