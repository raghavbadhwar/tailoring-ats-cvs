"""Human-readable, offline proposal review reports."""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def _markdown_cell(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def _evidence_index(proposal: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("id")): item
        for item in proposal.get("evidence_ledger", [])
        if item.get("id")
    }


def _requirement_index(proposal: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("id")): item
        for item in proposal.get("requirements", [])
        if item.get("id")
    }


def _mapping_index(proposal: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("requirement_id")): item
        for item in proposal.get("requirement_evidence", [])
        if item.get("requirement_id")
    }


def render_markdown(proposal: dict[str, Any]) -> str:
    """Render an auditable review document without changing the proposal."""

    evidence = _evidence_index(proposal)
    requirements = _requirement_index(proposal)
    mappings = _mapping_index(proposal)
    recruiter = proposal.get("report", {}).get("agents", {}).get("recruiter", {})

    lines = [
        "# CV Tailoring Review",
        "",
        f"- **Status:** {_markdown_cell(proposal.get('status', 'unknown'))}",
        f"- **Candidate:** {_markdown_cell(proposal.get('candidate_id', 'candidate'))}",
        f"- **Source CV:** `{_markdown_cell(proposal.get('source', ''))}`",
        f"- **Job description:** `{_markdown_cell(proposal.get('job_description', ''))}`",
        "",
        "## Recruiter-Oriented Signals",
        "",
        f"- **Disposition:** {_markdown_cell(recruiter.get('decision', 'unknown'))}",
        f"- **Confidence:** {_markdown_cell(recruiter.get('confidence', 'unknown'))}",
    ]
    for signal in recruiter.get("positive_signals", []):
        lines.append(f"- Positive: {_markdown_cell(signal)}")
    for signal in recruiter.get("blocking_signals", []):
        lines.append(f"- Blocking: {_markdown_cell(signal)}")

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
        terms = ", ".join(requirement.get("normalized_terms", []))
        evidence_ids = mapping.get("evidence_ids", [])
        evidence_labels = []
        for evidence_id in evidence_ids:
            item = evidence.get(str(evidence_id), {})
            source = Path(str(item.get("source_file", ""))).name
            span = item.get("source_span", "")
            evidence_labels.append(f"{evidence_id} ({source} {span})".strip())
        coverage = str(mapping.get("coverage", "unsupported"))
        coverage_label = coverage.replace("-", " ").title()
        if coverage == "unsupported":
            coverage_label = "Unsupported"
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(terms or requirement.get("text", "")),
                    _markdown_cell(requirement.get("importance", "")),
                    _markdown_cell(coverage_label),
                    _markdown_cell(", ".join(evidence_labels) or "None"),
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
        status = "Supported — eligible for approval" if supported else "Unsupported — cannot apply"
        lines.extend(
            [
                f"### {change_id} — {status}",
                "",
                f"**Reason:** {_markdown_cell(change.get('reason', ''))}",
                "",
                "**Before**",
                "",
                f"> {_markdown_cell(change.get('expected_text', '')) or '(no existing text)'}",
                "",
                "**After / gap term**",
                "",
                f"> {_markdown_cell(change.get('replacement_text', '')) or '(none)'}",
                "",
                "**Evidence:** "
                + (_markdown_cell(", ".join(change.get("evidence_ids", []))) or "None"),
                "",
            ]
        )

    lines.extend(
        [
            "## Approval Boundary",
            "",
            "Only explicitly approved, supported change IDs may be passed to `ats-agent apply`. ",
            "Unsupported requirements remain gaps and must not be inserted into the CV.",
            "",
        ]
    )
    return "\n".join(lines)


def _escape(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def _safe_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def render_html(
    proposal: dict[str, Any],
    *,
    proposal_filename: str,
    default_output: str,
) -> str:
    """Render a self-contained local approval interface with no network assets."""

    evidence = _evidence_index(proposal)
    requirements = _requirement_index(proposal)
    mappings = _mapping_index(proposal)
    recruiter = proposal.get("report", {}).get("agents", {}).get("recruiter", {})

    requirement_rows: list[str] = []
    for requirement_id, requirement in requirements.items():
        mapping = mappings.get(requirement_id, {})
        coverage = str(mapping.get("coverage", "unsupported"))
        evidence_ids = [str(item) for item in mapping.get("evidence_ids", [])]
        evidence_text = "<br>".join(
            (
                f"<code>{_escape(evidence_id)}</code> — "
                f"{_escape(evidence.get(evidence_id, {}).get('text', 'Missing evidence record'))}"
            )
            for evidence_id in evidence_ids
        ) or "<span class=\"muted\">No supporting evidence</span>"
        terms = ", ".join(requirement.get("normalized_terms", []))
        requirement_rows.append(
            "<tr>"
            f"<td>{_escape(terms or requirement.get('text', ''))}</td>"
            f"<td><span class=\"pill importance\">{_escape(requirement.get('importance', ''))}</span></td>"
            f"<td><span class=\"pill coverage { _escape(coverage) }\">{_escape(coverage)}</span></td>"
            f"<td>{evidence_text}</td>"
            "</tr>"
        )

    change_cards: list[str] = []
    for change in proposal.get("changes", []):
        change_id = str(change.get("id", "unknown"))
        supported = bool(change.get("supported"))
        checked_control = (
            f'<input type="checkbox" name="change" value="{_escape(change_id)}" '
            f'aria-label="Approve {_escape(change_id)}">'
            if supported
            else (
                f'<input type="checkbox" name="change" value="{_escape(change_id)}" '
                f'aria-label="Unsupported {_escape(change_id)}" disabled>'
            )
        )
        status = "Supported" if supported else "Unsupported"
        evidence_ids = ", ".join(str(item) for item in change.get("evidence_ids", []))
        change_cards.append(
            f'<article class="change {"supported" if supported else "unsupported"}" '
            f'data-change-id="{_escape(change_id)}">'
            '<div class="change-head">'
            f'<div>{checked_control}<strong>{_escape(change_id)}</strong> '
            f'<span class="pill">{_escape(status)}</span></div>'
            f'<span class="kind">{_escape(change.get("kind", "change"))}</span>'
            "</div>"
            f'<p class="reason">{_escape(change.get("reason", ""))}</p>'
            '<div class="comparison">'
            '<section><h4>Before</h4>'
            f'<pre>{_escape(change.get("expected_text", "")) or "(no existing text)"}</pre></section>'
            '<section><h4>After / gap term</h4>'
            f'<pre>{_escape(change.get("replacement_text", "")) or "(none)"}</pre></section>'
            "</div>"
            f'<p class="evidence"><strong>Evidence IDs:</strong> {_escape(evidence_ids or "None")}</p>'
            "</article>"
        )

    positives = "".join(
        f"<li>{_escape(item)}</li>" for item in recruiter.get("positive_signals", [])
    ) or "<li class=\"muted\">None reported</li>"
    blockers = "".join(
        f"<li>{_escape(item)}</li>" for item in recruiter.get("blocking_signals", [])
    ) or "<li class=\"muted\">None reported</li>"

    proposal_json = _safe_json(proposal_filename)
    output_json = _safe_json(default_output)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CV Tailoring Review</title>
<style>
:root {{ color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
body {{ margin: 0; background: #f5f7fb; color: #172033; line-height: 1.5; }}
main {{ width: min(1120px, calc(100% - 32px)); margin: 32px auto 80px; }}
header, .panel, .change {{ background: #fff; border: 1px solid #dce2ec; border-radius: 14px; box-shadow: 0 6px 20px rgba(26,39,66,.06); }}
header, .panel {{ padding: 24px; margin-bottom: 20px; }}
h1, h2, h3, h4 {{ line-height: 1.2; }}
h1 {{ margin-top: 0; }}
.meta {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(220px,1fr)); gap: 10px; }}
.meta div {{ background: #f7f9fc; padding: 10px 12px; border-radius: 8px; overflow-wrap: anywhere; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ text-align: left; vertical-align: top; padding: 12px; border-bottom: 1px solid #e6eaf1; }}
th {{ background: #f7f9fc; }}
.pill {{ display: inline-block; border-radius: 999px; padding: 2px 9px; background: #e9eef8; font-size: .82rem; text-transform: capitalize; }}
.coverage.direct {{ background: #dff5e8; }} .coverage.transferable {{ background: #fff0c9; }} .coverage.unsupported {{ background: #ffe1e1; }}
.change {{ padding: 20px; margin: 14px 0; }}
.change.unsupported {{ border-left: 5px solid #c73b3b; }} .change.supported {{ border-left: 5px solid #198754; }}
.change-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: center; }}
.change-head input {{ width: 18px; height: 18px; margin-right: 8px; }}
.comparison {{ display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 14px; }}
pre {{ white-space: pre-wrap; overflow-wrap: anywhere; background: #f7f9fc; padding: 14px; border-radius: 8px; min-height: 52px; }}
.muted {{ color: #6b7280; }}
.approval {{ position: sticky; bottom: 12px; display: flex; flex-wrap: wrap; gap: 10px; align-items: end; background: #172033; color: #fff; padding: 16px; border-radius: 12px; box-shadow: 0 12px 30px rgba(0,0,0,.22); }}
.approval label {{ flex: 1 1 280px; }}
.approval input[type=text] {{ box-sizing: border-box; width: 100%; margin-top: 5px; padding: 10px; border-radius: 7px; border: 1px solid #8d98aa; }}
button {{ border: 0; padding: 11px 16px; border-radius: 8px; background: #4f7cff; color: #fff; font-weight: 700; cursor: pointer; }}
@media (max-width: 760px) {{ .comparison {{ grid-template-columns: 1fr; }} table {{ display: block; overflow-x: auto; }} }}
</style>
</head>
<body>
<main>
<header>
<h1>CV Tailoring Review</h1>
<p>Review evidence-backed changes. Unsupported gaps are disabled and cannot enter the approval manifest.</p>
<div class="meta">
<div><strong>Status</strong><br>{_escape(proposal.get('status', 'unknown'))}</div>
<div><strong>Candidate</strong><br>{_escape(proposal.get('candidate_id', 'candidate'))}</div>
<div><strong>Source CV</strong><br>{_escape(proposal.get('source', ''))}</div>
<div><strong>Job description</strong><br>{_escape(proposal.get('job_description', ''))}</div>
</div>
</header>
<section class="panel">
<h2>Recruiter-oriented signals</h2>
<p><strong>Disposition:</strong> {_escape(recruiter.get('decision', 'unknown'))} · <strong>Confidence:</strong> {_escape(recruiter.get('confidence', 'unknown'))}</p>
<div class="comparison"><section><h3>Positive signals</h3><ul>{positives}</ul></section><section><h3>Blocking signals</h3><ul>{blockers}</ul></section></div>
</section>
<section class="panel">
<h2>Requirement-to-Evidence Matrix</h2>
<table><thead><tr><th>Requirement</th><th>Importance</th><th>Coverage</th><th>Evidence</th></tr></thead><tbody>{''.join(requirement_rows)}</tbody></table>
</section>
<section>
<h2>Proposed changes</h2>
{''.join(change_cards) or '<div class="panel">No changes were proposed.</div>'}
</section>
<div class="approval">
<label>Output document name<input id="output" type="text" value="{_escape(default_output)}"></label>
<button type="button" onclick="downloadManifest()">Download approval manifest</button>
<span id="selection" aria-live="polite"></span>
</div>
</main>
<script>
const proposalFile = {proposal_json};
const defaultOutput = {output_json};
function selectedIds() {{
  return Array.from(document.querySelectorAll('input[name="change"]:checked:not(:disabled)')).map(item => item.value);
}}
function updateSelection() {{
  const ids = selectedIds();
  document.getElementById('selection').textContent = ids.length ? `${{ids.length}} approved` : 'No changes approved';
}}
document.querySelectorAll('input[name="change"]').forEach(item => item.addEventListener('change', updateSelection));
updateSelection();
function downloadManifest() {{
  const manifest = {{
    proposal: proposalFile,
    approved_change_ids: selectedIds(),
    output: document.getElementById('output').value || defaultOutput
  }};
  const blob = new Blob([JSON.stringify(manifest, null, 2) + '\\n'], {{type: 'application/json'}});
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = 'approval-manifest.json';
  document.body.appendChild(link);
  link.click();
  URL.revokeObjectURL(link.href);
  link.remove();
}}
</script>
</body>
</html>
"""
