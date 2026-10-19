"""Human-readable proposal, evidence, and approval review artifacts."""
from __future__ import annotations

import html
import json
from pathlib import Path


def proposal_markdown(proposal: dict) -> str:
    lines = [
        "# CV Tailoring Proposal",
        "",
        f"**Candidate:** `{proposal.get('candidate_id', 'candidate')}`  ",
        f"**Status:** `{proposal.get('status')}`  ",
        f"**Source:** `{proposal.get('source')}`",
        "",
        "## Hard Gates",
        "",
    ]
    gates = proposal.get("hard_gates") or []
    if gates:
        for gate in gates:
            lines.append(f"- **{gate['status'].upper()}** — {gate['requirement']}")
    else:
        lines.append("- No deterministic hard gate was extracted.")
    lines.extend(["", "## Requirement-to-Evidence Map", ""])
    req_index = {r["id"]: r for r in proposal.get("requirements", [])}
    for mapping in proposal.get("requirement_evidence", []):
        requirement = req_index.get(mapping["requirement_id"], {})
        terms = ", ".join(mapping.get("normalized_terms", []))
        evidence = ", ".join(mapping.get("evidence_ids", [])) or "none"
        lines.append(
            f"- **{mapping['coverage']}** — {terms} — evidence: `{evidence}` — {requirement.get('text', '')}"
        )
    lines.extend(["", "## Proposed Changes", ""])
    for change in proposal.get("changes", []):
        lines.append(f"### {change['id']} — {change['kind']}")
        lines.append("")
        lines.append(f"**Supported:** `{change.get('supported')}`  ")
        lines.append(f"**Evidence:** `{', '.join(change.get('evidence_ids', [])) or 'none'}`  ")
        lines.append(f"**Reason:** {change.get('reason', '')}")
        lines.append("")
        if change.get("expected_text"):
            lines.append(f"**Current:** {change['expected_text']}")
            lines.append("")
        for variant in change.get("variants", []):
            lines.append(f"- **{variant['id']}**: {variant['text']}")
        lines.append("")
    lines.extend(["## Evidence Ledger", ""])
    for item in proposal.get("evidence_ledger", []):
        lines.append(
            f"- `{item['id']}` — {item['text']}  \n  Source: `{item['source_file']}` / {item['source_span']} / ownership `{item['ownership']}`"
        )
    lines.extend([
        "",
        "## Approval",
        "",
        "Approve only supported change IDs and select a variant for each. The source file is never overwritten.",
    ])
    return "\n".join(lines) + "\n"


def proposal_html(proposal: dict) -> str:
    proposal_json = json.dumps(proposal).replace("</", "<\\/")
    cards: list[str] = []
    for change in proposal.get("changes", []):
        supported = bool(change.get("supported"))
        options = "".join(
            f'<option value="{html.escape(variant["id"])}"{(" selected" if variant["id"] == change.get("default_variant") else "")}>{html.escape(variant["id"])} — {html.escape(variant["text"])}</option>'
            for variant in change.get("variants", [])
        )
        cards.append(
            f'''<article class="card {'supported' if supported else 'unsupported'}">
<h2>{html.escape(change['id'])} · {html.escape(change['kind'])}</h2>
<p>{html.escape(change.get('reason', ''))}</p>
<p><strong>Current:</strong> {html.escape(change.get('expected_text', '') or '—')}</p>
<p><strong>Evidence:</strong> {html.escape(', '.join(change.get('evidence_ids', [])) or 'none')}</p>
<label><input class="approve" type="checkbox" data-id="{html.escape(change['id'])}" {'disabled' if not supported else ''}> Approve</label>
<select class="variant" data-id="{html.escape(change['id'])}" {'disabled' if not supported else ''}>{options}</select>
</article>'''
        )
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CV Tailoring Review</title><style>
body{{font-family:system-ui,sans-serif;max-width:1100px;margin:0 auto;padding:32px;background:#f6f7f9;color:#172033}}
header,.card{{background:white;border:1px solid #d9dee8;border-radius:14px;padding:20px;margin-bottom:16px}}
.card.unsupported{{opacity:.65}} select{{width:100%;padding:10px;margin-top:10px}} button{{padding:12px 18px;font-weight:700}}
code{{word-break:break-all}} .meta{{color:#586174}}
</style></head><body>
<header><h1>CV Tailoring Review</h1><p class="meta">Evidence-grounded proposals. Unsupported changes cannot be approved.</p>
<p><code>{html.escape(str(proposal.get('source')))}</code></p></header>
{''.join(cards)}
<button id="download">Download approval-manifest.json</button>
<script id="proposal-data" type="application/json">{proposal_json}</script>
<script>
const proposal=JSON.parse(document.getElementById('proposal-data').textContent);
document.getElementById('download').addEventListener('click',()=>{{
 const selections=[...document.querySelectorAll('.approve:checked')].map(box=>{{
  const id=box.dataset.id; const select=document.querySelector(`.variant[data-id="${{id}}"]`);
  return {{change_id:id,variant_id:select.value}};
 }});
 const manifest={{proposal:'proposal.json',selections,approved_change_ids:selections.map(x=>x.change_id),mode:'preserve',output:'tailored-resume.docx'}};
 const blob=new Blob([JSON.stringify(manifest,null,2)],{{type:'application/json'}});
 const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='approval-manifest.json';a.click();URL.revokeObjectURL(a.href);
}});
</script></body></html>'''


def write_review_artifacts(proposal: dict, output_dir: Path) -> dict:
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown = output_dir / "proposal.md"
    review_html = output_dir / "review.html"
    markdown.write_text(proposal_markdown(proposal), encoding="utf-8")
    review_html.write_text(proposal_html(proposal), encoding="utf-8")
    return {"markdown": str(markdown), "html": str(review_html)}
