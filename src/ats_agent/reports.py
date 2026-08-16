"""Backward-compatible, self-contained human review renderers.

The primary proposal artifacts live in :mod:`ats_agent.reporting`. This module
keeps the public ``render_markdown`` / ``render_html`` contract used by earlier
clients while rendering schema-v5 proposals safely.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


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


def render_markdown(proposal: dict[str, Any]) -> str:
    """Render a readable, auditable Markdown proposal review."""

    evidence = _index(proposal, "evidence_ledger", "id")
    requirements = _index(proposal, "requirements", "id")
    mappings = _index(proposal, "requirement_evidence", "requirement_id")
    recruiter = proposal.get("report", {}).get("agents", {}).get("recruiter", {})

    lines = [
        "# CV Tailoring Review",
        "",
        f"- **Status:** {_cell(proposal.get('status', 'unknown'))}",
        f"- **Candidate:** {_cell(proposal.get('candidate_id', 'candidate'))}",
        f"- **Source CV:** `{_cell(proposal.get('source', ''))}`",
        f"- **Job description:** `{_cell(proposal.get('job_description', ''))}`",
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
        evidence_labels = []
        for evidence_id in mapping.get("evidence_ids", []):
            item = evidence.get(str(evidence_id), {})
            source = Path(str(item.get("source_file", ""))).name
            span = str(item.get("source_span", ""))
            evidence_labels.append(
                f"{evidence_id} ({source} {span})".strip()
            )
        coverage = str(mapping.get("coverage", "unsupported"))
        label = (
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
                    _cell(label),
                    _cell(", ".join(evidence_labels) or "None"),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Proposed Changes", ""])
    changes = proposal.get("changes", [])
    if not changes:
        lines.append("No changes were proposed.")
    for change in changes:
        change_id = str(change.get("id", "unknown"))
        supported = bool(change.get("supported"))
        status = (
            "Supported — eligible for approval"
            if supported
            else "Unsupported — cannot apply"
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
                (
                    "**Before:** "
                    + (_cell(change.get("expected_text", "")) or "(no existing text)")
                ),
                "",
                f"**After / gap term:** {_cell(after) or '(none)'}",
                "",
                (
                    "**Evidence:** "
                    + (
                        _cell(", ".join(str(item) for item in change.get("evidence_ids", [])))
                        or "None"
                    )
                ),
                "",
            ]
        )
    lines.extend(
        [
            "## Approval Boundary",
            "",
            (
                "Only explicitly approved, supported changes may be applied. "
                "Unsupported requirements remain gaps."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def render_html(
    proposal: dict[str, Any],
    *,
    proposal_filename: str,
    default_output: str,
) -> str:
    """Render a self-contained local approval page with no network assets."""

    requirements = _index(proposal, "requirements", "id")
    mappings = _index(proposal, "requirement_evidence", "requirement_id")
    evidence = _index(proposal, "evidence_ledger", "id")

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

    cards = []
    for change in proposal.get("changes", []):
        change_id = str(change.get("id", "unknown"))
        supported = bool(change.get("supported"))
        disabled = "" if supported else " disabled"
        variants = change.get("variants") or []
        options = "".join(
            (
                f'<option value="{_escape(variant.get("id"))}">'
                f'{_escape(variant.get("id"))} — '
                f'{_escape(variant.get("text"))}</option>'
            )
            for variant in variants
        )
        if not options:
            options = (
                f'<option value="default">'
                f'{_escape(change.get("replacement_text", ""))}</option>'
            )
        cards.append(
            f'<article class="change" data-change-id="{_escape(change_id)}">'
            f'<label><input type="checkbox" name="change" '
            f'value="{_escape(change_id)}"{disabled}> '
            f'<strong>{_escape(change_id)}</strong></label>'
            f'<p>{_escape(change.get("reason", ""))}</p>'
            f'<pre>{_escape(change.get("expected_text", ""))}</pre>'
            f'<select data-variant-for="{_escape(change_id)}"{disabled}>'
            f'{options}</select>'
            f'<p>Evidence: '
            f'{_escape(", ".join(str(item) for item in change.get("evidence_ids", [])) or "None")}'
            f'</p></article>'
        )

    proposal_file_json = json.dumps(proposal_filename).replace("</", "<\\/")
    default_output_json = json.dumps(default_output).replace("</", "<\\/")
    proposal_digest_json = json.dumps(
        str(proposal.get("proposal_digest") or "")
    ).replace("</", "<\\/")
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CV Tailoring Review</title><style>
body{{font-family:system-ui,sans-serif;max-width:1100px;margin:32px auto;padding:0 16px;background:#f6f7fb;color:#172033}}
section,.change{{background:#fff;border:1px solid #d9dfeb;border-radius:12px;padding:18px;margin:14px 0}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #e6eaf1;text-align:left;vertical-align:top}}
pre{{white-space:pre-wrap;background:#f7f9fc;padding:10px;border-radius:8px}}select{{width:100%;padding:8px}}.muted{{color:#687386}}
</style></head><body>
<h1>CV Tailoring Review</h1>
<section><h2>Requirement-to-Evidence Matrix</h2><table><thead><tr><th>Requirement</th><th>Importance</th><th>Coverage</th><th>Evidence</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section>
<section><h2>Proposed changes</h2>{''.join(cards) or '<p>No changes proposed.</p>'}</section>
<button type="button" id="download">Download approval manifest</button>
<script>
const proposalFile={proposal_file_json}; const outputDocument={default_output_json};
const proposalDigest={proposal_digest_json};
document.getElementById('download').addEventListener('click',()=>{{
 const selections=[...document.querySelectorAll('input[name="change"]:checked:not(:disabled)')].map(box=>{{
  const id=box.value; const select=document.querySelector(`[data-variant-for="${{id}}"]`); return {{change_id:id,variant_id:select.value}};
 }});
 const manifest={{schema_version:2,proposal:proposalFile,proposal_digest:proposalDigest,approved_change_ids:selections.map(x=>x.change_id),selections,output:outputDocument,document_mode:'preserve'}};
 const blob=new Blob([JSON.stringify(manifest,null,2)],{{type:'application/json'}}); const a=document.createElement('a');
 a.href=URL.createObjectURL(blob); a.download='approval-manifest.json'; a.click(); URL.revokeObjectURL(a.href);
}});
</script></body></html>'''
