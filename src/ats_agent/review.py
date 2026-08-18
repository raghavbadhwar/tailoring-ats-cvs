"""Unified, privacy-aware review and explicit approval artifacts."""
from __future__ import annotations

import copy
import html
import json
import re
from pathlib import Path
from typing import Any, Iterable, Literal

from .hashing import verify_proposal_digest

DocumentMode = Literal["preserve", "strict-preserve", "rebuild"]
REDACTED = "[redacted]"


def _escape(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def _cell(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def _index(
    proposal: dict[str, Any],
    collection: str,
    key: str,
) -> dict[str, dict[str, Any]]:
    return {
        str(item[key]): item
        for item in proposal.get(collection, [])
        if isinstance(item, dict) and item.get(key)
    }


def _review_view(proposal: dict[str, Any], *, redacted: bool) -> dict[str, Any]:
    view = copy.deepcopy(proposal)
    view["review_mode"] = "redacted" if redacted else "full"
    view["approval_disabled"] = redacted
    if not redacted:
        return view

    for key in ("candidate_id", "source", "job_description", "company_context"):
        if key in view and view[key] is not None:
            view[key] = REDACTED
    view["evidence_files"] = [REDACTED for _ in view.get("evidence_files", [])]
    for artifact in view.get("artifacts", []):
        if isinstance(artifact, dict):
            artifact["path"] = REDACTED
            if artifact.get("candidate_id") is not None:
                artifact["candidate_id"] = REDACTED
    for item in view.get("evidence_ledger", []):
        if not isinstance(item, dict):
            continue
        item["text"] = REDACTED
        item["source_file"] = REDACTED
        item["source_span"] = REDACTED
        for claim in item.get("atomic_claims", []):
            if isinstance(claim, dict):
                claim["text"] = REDACTED
                claim["source_file"] = REDACTED
                claim["source_span"] = REDACTED
                for metric in claim.get("metrics", []):
                    if isinstance(metric, dict):
                        metric["scope"] = REDACTED
    for change in view.get("changes", []):
        if not isinstance(change, dict):
            continue
        if change.get("expected_text"):
            change["expected_text"] = REDACTED
        if change.get("replacement_text"):
            change["replacement_text"] = REDACTED
        for variant in change.get("variants", []):
            if isinstance(variant, dict) and variant.get("text"):
                variant["text"] = REDACTED
    recruiter = view.get("report", {}).get("agents", {}).get("recruiter", {})
    for key in ("positive_signals", "blocking_signals", "unknowns"):
        if recruiter.get(key):
            recruiter[key] = [REDACTED]
    return view


def _privacy_notice(redacted: bool) -> str:
    if redacted:
        return "Privacy-safe redacted review. Approval is disabled in this shareable copy."
    return "Contains sensitive candidate evidence. Keep this review local and access-controlled."


def render_markdown(
    proposal: dict[str, Any],
    *,
    redacted: bool = False,
) -> str:
    """Render the canonical Markdown review."""

    view = _review_view(proposal, redacted=redacted)
    evidence = _index(view, "evidence_ledger", "id")
    requirements = _index(view, "requirements", "id")
    mappings = _index(view, "requirement_evidence", "requirement_id")
    recruiter = view.get("report", {}).get("agents", {}).get("recruiter", {})
    lines = [
        "# CV Tailoring Review",
        "",
        f"> **Privacy:** {_privacy_notice(redacted)}",
        "",
        f"- **Status:** {_cell(view.get('status', 'unknown'))}",
        f"- **Candidate:** {_cell(view.get('candidate_id', 'candidate'))}",
        f"- **Proposal:** {_cell(view.get('proposal_id', 'unknown'))}",
        f"- **Proposal digest:** `{_cell(view.get('proposal_digest', ''))}`",
        f"- **Source CV:** `{_cell(view.get('source', ''))}`",
        f"- **Job description:** `{_cell(view.get('job_description', ''))}`",
        "",
        "## Recruiter-Oriented Signals",
        "",
        f"- **Disposition:** {_cell(recruiter.get('decision', 'unknown'))}",
        f"- **Confidence:** {_cell(recruiter.get('confidence', 'unknown'))}",
    ]
    for signal in recruiter.get("positive_signals", []):
        lines.append(f"- Positive: {_cell(signal)}")
    for signal in recruiter.get("blocking_signals", []):
        lines.append(f"- Blocking: {_cell(signal)}")

    lines.extend(["", "## Hard Gates", ""])
    hard_gates = view.get("hard_gates", [])
    if hard_gates:
        for gate in hard_gates:
            lines.append(
                f"- **{_cell(gate.get('status', 'unknown')).upper()}** — "
                f"{_cell(gate.get('requirement', gate.get('kind', 'gate')))}"
            )
    else:
        lines.append("- No deterministic hard gate was extracted.")

    lines.extend(
        [
            "",
            "## Requirement-to-Evidence Matrix",
            "",
            "| Requirement | Importance | Coverage | Evidence |",
            "|---|---|---|---|",
        ]
    )
    for requirement_id, requirement in requirements.items():
        mapping = mappings.get(requirement_id, {})
        terms = ", ".join(
            str(item) for item in requirement.get("normalized_terms", [])
        )
        labels = []
        for evidence_id in mapping.get("evidence_ids", []):
            item = evidence.get(str(evidence_id), {})
            source = Path(str(item.get("source_file", ""))).name
            span = str(item.get("source_span", ""))
            labels.append(f"{evidence_id} ({source} {span})".strip())
        coverage = str(mapping.get("coverage", "unsupported"))
        coverage_label = (
            "Unsupported"
            if coverage == "unsupported"
            else coverage.replace("-", " ").title()
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(terms or requirement.get("text", "")),
                    _cell(requirement.get("importance", "")),
                    _cell(coverage_label),
                    _cell(", ".join(labels) or "None"),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Proposed Changes", ""])
    changes = view.get("changes", [])
    if not changes:
        lines.append("No changes were proposed.")
    for change in changes:
        change_id = str(change.get("id", "unknown"))
        supported = bool(change.get("supported"))
        status = (
            "Supported — eligible for approval"
            if supported and not redacted
            else "Unsupported — cannot apply"
            if not supported
            else "Supported — approval disabled in redacted review"
        )
        variants = change.get("variants") or []
        after = change.get("replacement_text", "")
        if variants:
            after = " / ".join(
                f"{variant.get('id')}: {variant.get('text')}"
                for variant in variants
            )
        lines.extend(
            [
                f"### {change_id} — {status}",
                "",
                f"**Reason:** {_cell(change.get('reason', ''))}",
                "",
                "**Before:** "
                + (_cell(change.get("expected_text", "")) or "(no existing text)"),
                "",
                f"**After / gap term:** {_cell(after) or '(none)'}",
                "",
                "**Evidence:** "
                + (
                    _cell(", ".join(str(item) for item in change.get("evidence_ids", [])))
                    or "None"
                ),
                "",
            ]
        )

    lines.extend(["## Evidence Ledger", ""])
    for item in view.get("evidence_ledger", []):
        lines.append(
            f"- `{_cell(item.get('id'))}` — {_cell(item.get('text'))}  \n"
            f"  Source: `{_cell(item.get('source_file'))}` / "
            f"{_cell(item.get('source_span'))} / ownership "
            f"`{_cell(item.get('ownership'))}` / verification "
            f"`{_cell(item.get('verification_status', 'unknown'))}`"
        )
    lines.extend(
        [
            "",
            "## Approval Boundary",
            "",
            (
                "Only explicitly approved, supported changes may be applied. "
                "Unsupported requirements remain gaps."
                if not redacted
                else "Approval is disabled in this redacted review."
            ),
            "",
        ]
    )
    coverage = view.get("coverage", {})
    if coverage:
        baseline = coverage.get("baseline", [])
        covered = [item for item in baseline if item.get("coverage") != "unsupported"]
        unsupported = [item for item in baseline if item.get("coverage") == "unsupported"]
        lines.extend(
            [
                "## Coverage",
                "",
                f"- **Baseline requirements:** {len(baseline)}",
                f"- **Already covered requirements:** {len(covered)}",
                f"- **Unsupported requirements:** {len(unsupported)}",
                f"- **Proposed variants:** {len(coverage.get('proposed_variants', []))}",
                "",
            ]
        )
    recommendations = view.get("gap_recommendations", [])
    if recommendations:
        lines.extend(["## Ranked Evidence-Building Gaps", ""])
        for item in recommendations:
            quality = item.get("source_quality", {})
            lines.append(
                f"- **{_cell(item.get('importance', 'preferred')).upper()}** — "
                f"{_cell(', '.join(item.get('keywords', [])))}: "
                f"{_cell(item.get('recommendation', ''))} "
                f"(source: {_cell(quality.get('source_type', 'unknown'))}, "
                f"{_cell(quality.get('source_url', 'unknown'))})"
            )
        lines.append("")
    conflicts = view.get("evidence_conflicts", [])
    if conflicts:
        lines.extend(["## Factual Conflicts", ""])
        for conflict in conflicts:
            lines.append(
                f"- **UNRESOLVED** — {_cell(conflict.get('kind', 'fact'))}: "
                "supply reconciled candidate evidence before changing this fact."
            )
        lines.append("")
    duplicate_warnings = view.get("duplicate_warnings", [])
    if duplicate_warnings:
        lines.extend(["## Review-Only Near-Duplicates", ""])
        for warning in duplicate_warnings:
            lines.append(
                f"- `{_cell(warning.get('evidence_id', 'unknown'))}` — "
                f"{_cell(warning.get('reason', 'Review before inserting.'))}"
            )
        lines.append("")
    return "\n".join(lines)


def _safe_json(value: object) -> str:
    return (
        json.dumps(value, ensure_ascii=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_html(
    proposal: dict[str, Any],
    *,
    proposal_filename: str,
    default_output: str,
    redacted: bool = False,
    digest_reference: Literal["constant", "proposal"] = "constant",
) -> str:
    """Render the canonical self-contained review page."""

    view = _review_view(proposal, redacted=redacted)
    requirements = _index(view, "requirements", "id")
    mappings = _index(view, "requirement_evidence", "requirement_id")
    evidence = _index(view, "evidence_ledger", "id")

    gate_items = "".join(
        f"<li><strong>{_escape(str(gate.get('status', 'unknown')).upper())}</strong> — "
        f"{_escape(gate.get('requirement', gate.get('kind', 'gate')))}</li>"
        for gate in view.get("hard_gates", [])
    ) or "<li>No deterministic hard gate was extracted.</li>"

    rows = []
    for requirement_id, requirement in requirements.items():
        mapping = mappings.get(requirement_id, {})
        labels = []
        for evidence_id in mapping.get("evidence_ids", []):
            item = evidence.get(str(evidence_id), {})
            labels.append(
                f"{evidence_id} — {item.get('text', 'Missing evidence record')}"
            )
        terms = ", ".join(
            str(item) for item in requirement.get("normalized_terms", [])
        )
        evidence_html = "<br>".join(_escape(item) for item in labels)
        if not evidence_html:
            evidence_html = '<span class="muted">No supporting evidence</span>'
        rows.append(
            "<tr>"
            f"<td>{_escape(terms or requirement.get('text', ''))}</td>"
            f"<td>{_escape(requirement.get('importance', ''))}</td>"
            f"<td>{_escape(mapping.get('coverage', 'unsupported'))}</td>"
            f"<td>{evidence_html}</td>"
            "</tr>"
        )

    supported_changes = [
        change
        for change in view.get("changes", [])
        if isinstance(change, dict) and change.get("supported") and not redacted
    ]
    unavailable_changes = [
        change
        for change in view.get("changes", [])
        if isinstance(change, dict) and change not in supported_changes
    ]
    cards = []
    for change in supported_changes:
        change_id = str(change.get("id", "unknown"))
        variants = change.get("variants") or []
        options = "".join(
            (
                f'<option value="{_escape(variant.get("id"))}"'
                f'{" selected" if variant.get("id") == change.get("default_variant") else ""}>'
                f'{_escape(variant.get("id"))} — {_escape(variant.get("text"))}'
                "</option>"
            )
            for variant in variants
        )
        if not options:
            options = (
                '<option value="default">'
                f'{_escape(change.get("replacement_text", ""))}</option>'
            )
        cards.append(
            f'<article class="change" data-change-id="{_escape(change_id)}">'
            f'<label><input type="checkbox" name="change" '
            f'value="{_escape(change_id)}"> '
            f"<strong>{_escape(change_id)}</strong></label>"
            f"<p>{_escape(change.get('reason', ''))}</p>"
            f"<pre>{_escape(change.get('expected_text', ''))}</pre>"
            f'<select data-variant-for="{_escape(change_id)}">'
            f"{options}</select>"
            f"<p>Evidence: "
            f'{_escape(", ".join(str(item) for item in change.get("evidence_ids", [])) or "None")}'
            "</p></article>"
        )

    unavailable_html = "".join(
        f'<li data-change-id="{_escape(change.get("id", "unknown"))}">'
        f"<strong>{_escape(change.get('id', 'unknown'))}</strong> — "
        f"{_escape(change.get('reason', 'Approval is unavailable in this review.'))}"
        "</li>"
        for change in unavailable_changes
    )
    if redacted and unavailable_changes:
        unavailable_html = "".join(
            f'<li data-change-id="{_escape(change.get("id", "unknown"))}">'
            f"<strong>{_escape(change.get('id', 'unknown'))}</strong> — "
            "Approval is disabled in this redacted review."
            "</li>"
            for change in unavailable_changes
        )

    proposal_file_json = _safe_json(proposal_filename)
    proposal_digest_json = _safe_json(str(view.get("proposal_digest") or ""))
    default_output_json = _safe_json(default_output)
    if digest_reference == "proposal":
        digest_prelude = (
            f"const proposal={{proposal_digest:{proposal_digest_json}}};"
            "const proposalDigest=proposal.proposal_digest;"
        )
        digest_expression = "proposal.proposal_digest"
    else:
        digest_prelude = f"const proposalDigest={proposal_digest_json};"
        digest_expression = "proposalDigest"
    approval_disabled = "true" if redacted else "false"
    button_disabled = " disabled" if redacted else ""
    coverage = view.get("coverage", {})
    coverage_html = ""
    if coverage:
        baseline = coverage.get("baseline", [])
        covered = sum(item.get("coverage") != "unsupported" for item in baseline)
        coverage_html = (
            "<section><h2>Coverage</h2>"
            f"<p>Baseline: {len(baseline)} requirements; already covered: {covered}; "
            f"unsupported: {len(baseline) - covered}; proposed variants: "
            f"{len(coverage.get('proposed_variants', []))}.</p></section>"
        )
    gap_html = "".join(
        "<li><strong>"
        + _escape(item.get("importance", "preferred").upper())
        + "</strong> — "
        + _escape(", ".join(item.get("keywords", [])))
        + ": "
        + _escape(item.get("recommendation", ""))
        + "</li>"
        for item in view.get("gap_recommendations", [])
    )
    if gap_html:
        gap_html = f"<h3>Ranked evidence-building gaps</h3><ul>{gap_html}</ul>"
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CV Tailoring Review</title><style>
body{{font-family:system-ui,sans-serif;max-width:1100px;margin:32px auto;padding:0 16px;background:#f6f7fb;color:#172033}}
section,.change,.notice{{background:#fff;border:1px solid #d9dfeb;border-radius:12px;padding:18px;margin:14px 0}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #e6eaf1;text-align:left;vertical-align:top}}
pre{{white-space:pre-wrap;background:#f7f9fc;padding:10px;border-radius:8px}}select{{width:100%;padding:8px}}.muted{{color:#687386}}
</style></head><body>
<h1>CV Tailoring Review</h1>
<p class="notice"><strong>Privacy:</strong> {_escape(_privacy_notice(redacted))}<br><strong>Proposal digest:</strong> <code>{_escape(view.get('proposal_digest', ''))}</code></p>
<section><h2>Decision summary</h2>
<p>Selecting a supported change only downloads a schema-v2 approval manifest. It does not approve, apply, or modify the source CV.</p>
<h3>Selectable supported changes ({len(supported_changes)})</h3>{''.join(cards) or '<p>No supported changes are available for selection.</p>'}
<h3>Unavailable changes ({len(unavailable_changes)})</h3><p>Unavailable changes cannot be selected or applied.</p><ul>{unavailable_html or '<li>None</li>'}</ul></section>
<section><h2>Hard Gates</h2><ul>{gate_items}</ul></section>
<details><summary>Requirement-to-Evidence Matrix ({len(rows)} requirements)</summary><table><thead><tr><th>Requirement</th><th>Importance</th><th>Coverage</th><th>Evidence</th></tr></thead><tbody>{''.join(rows)}</tbody></table></details>
<details><summary>Gap details</summary>{coverage_html}{gap_html or '<p>No ranked evidence-building gaps.</p>'}</details>
<button type="button" id="download"{button_disabled}>Download approval manifest</button>
<script>
const proposalFile={proposal_file_json};{digest_prelude}const outputDocument={default_output_json};const approvalDisabled={approval_disabled};
document.getElementById('download').addEventListener('click',()=>{{
 if(approvalDisabled) return;
 const selections=[...document.querySelectorAll('input[name="change"]:checked:not(:disabled)')].map(box=>{{
  const id=box.value; const select=document.querySelector(`[data-variant-for="${{id}}"]`); return {{change_id:id,variant_id:select.value==='default'?null:select.value}};
 }});
 const manifest={{schema_version:2,proposal:proposalFile,proposal_digest:{digest_expression},approved_change_ids:selections.map(x=>x.change_id),selections,output:outputDocument,document_mode:'preserve',force:false}};
 const blob=new Blob([JSON.stringify(manifest,null,2)],{{type:'application/json'}}); const a=document.createElement('a');
 a.href=URL.createObjectURL(blob); a.download='approval-manifest.json'; a.click(); URL.revokeObjectURL(a.href);
}});
</script></body></html>'''


def build_approval_manifest(
    proposal: dict[str, Any],
    *,
    proposal_filename: str,
    selections: Iterable[tuple[str, str | None]],
    output_document: str,
    document_mode: DocumentMode = "preserve",
    force: bool = False,
    max_character_growth: int = 120,
) -> dict[str, Any]:
    """Validate explicit selections and return a schema-v2 manifest."""

    if proposal.get("review_mode") == "redacted" or proposal.get("approval_disabled"):
        raise ValueError("redacted reviews cannot be approved")
    if proposal.get("status") != "draft":
        raise ValueError("only a draft proposal can be approved")
    if not isinstance(max_character_growth, int) or not 0 <= max_character_growth <= 2000:
        raise ValueError("max_character_growth must be an integer from 0 to 2000")
    digest = str(proposal.get("proposal_digest") or "").lower()
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("proposal has no valid proposal digest")
    verify_proposal_digest(proposal)
    changes = {
        str(change.get("id")): change
        for change in proposal.get("changes", [])
        if isinstance(change, dict) and change.get("id")
    }
    normalized: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for change_id, requested_variant in selections:
        if change_id in seen:
            raise ValueError(f"duplicate approval selection: {change_id}")
        seen.add(change_id)
        change = changes.get(change_id)
        if change is None:
            raise ValueError(f"unknown approval change: {change_id}")
        if not change.get("supported"):
            raise ValueError(f"change {change_id} is unsupported")
        variants = change.get("variants") or []
        if variants:
            variant_ids = {str(item.get("id")) for item in variants}
            selected = (
                requested_variant
                or change.get("default_variant")
                or str(variants[0].get("id"))
            )
            if selected not in variant_ids:
                raise ValueError(
                    f"change {change_id} has no variant {selected}"
                )
        else:
            if requested_variant not in {None, "default"}:
                raise ValueError(
                    f"change {change_id} has no variant {requested_variant}"
                )
            selected = None
        normalized.append({"change_id": change_id, "variant_id": selected})
    if not normalized:
        raise ValueError("no changes were selected for approval")
    return {
        "schema_version": 2,
        "proposal": proposal_filename,
        "proposal_digest": digest,
        "selections": normalized,
        "approved_change_ids": [item["change_id"] for item in normalized],
        "document_mode": document_mode,
        "output": output_document,
        "force": force,
        "max_character_growth": max_character_growth,
    }


def write_review_bundle(
    proposal: dict[str, Any],
    output_dir: Path,
    *,
    default_output: str = "tailored-resume.docx",
    redacted: bool = False,
) -> dict[str, str]:
    """Write proposal JSON, Markdown, and HTML from one review model."""

    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    proposal_path = output_dir / (
        "proposal.redacted.json" if redacted else "proposal.json"
    )
    markdown_path = output_dir / "proposal.md"
    html_path = output_dir / "review.html"
    persisted = _review_view(proposal, redacted=True) if redacted else proposal
    proposal_path.write_text(
        json.dumps(persisted, indent=2) + "\n",
        encoding="utf-8",
    )
    if not redacted:
        try:
            verify_proposal_digest(
                json.loads(proposal_path.read_text(encoding="utf-8"))
            )
        except (ValueError, json.JSONDecodeError):
            proposal_path.unlink(missing_ok=True)
            (output_dir / "blocked.json").write_text(
                json.dumps({"status": "blocked", "reason": "proposal digest verification failed"}) + "\n",
                encoding="utf-8",
            )
            raise
    markdown_path.write_text(
        render_markdown(proposal, redacted=redacted),
        encoding="utf-8",
    )
    html_path.write_text(
        render_html(
            proposal,
            proposal_filename=proposal_path.name,
            default_output=default_output,
            redacted=redacted,
        ),
        encoding="utf-8",
    )
    return {
        "proposal": str(proposal_path),
        "markdown": str(markdown_path),
        "html": str(html_path),
    }
