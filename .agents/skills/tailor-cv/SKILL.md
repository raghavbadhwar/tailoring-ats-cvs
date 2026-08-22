---
name: tailor-cv
description: Audit and tailor a candidate CV against a job description using the local ats-agent CLI. Use for CV assessment, evidence mapping, review, explicit approval, application, or validation.
metadata:
  author: raghavbadhwar
  version: "1.0.0-beta.4"
  repository: "https://github.com/raghavbadhwar/tailoring-ats-cvs"
---

# Tailor CV

Use `ats-agent` as the authoritative engine. Do not recreate its analysis or edit a CV directly.

Resolve the skill directory before running any bundled script:

```sh
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/tailor-cv"
[ -f "$SKILL_DIR/SKILL.md" ] || SKILL_DIR=".agents/skills/tailor-cv"
```

1. Run `python "$SKILL_DIR/scripts/ensure_cli.py" --check`. If it reports `bootstrap_required` or `upgrade_required`, read the listed `attempts` chain aloud (every tier, in order) and ask exactly once: "May I install the ats-agent engine using this chain? [y/N]". Do not run `--install --manager auto` before an explicit yes; one yes covers the whole ordered chain, including automatic fall-through from PyPI to the pinned GitHub tag and finally an isolated venv.
2. Require a CV and job-description path; use a fresh user-selected run directory outside the skill or plugin. Evidence files are optional candidate evidence; company context is not candidate evidence.
3. Preferred one-door run when approvals are known up front:
   `python "$SKILL_DIR/scripts/run_cli.py" -- tailor "<resume>" "<jd-or-url-or-list>" --candidate-id "<candidate-id>" --run-dir "<run-directory>" --approve-from <approvals.json>` (JSON mapping `{"role-id | *": ["C1:variant", ...]}`). It proposes, applies named approvals, validates, and prints a delivery card.
   Otherwise prepare only: `python "$SKILL_DIR/scripts/run_cli.py" -- prepare "<resume>" "<job-description>" --candidate-id "<candidate-id>" --out "<run-directory>"`.
4. Summarize: `python "$SKILL_DIR/scripts/summarize_proposal.py" "<run-directory>/proposal.json" --output "<run-directory>/summary.json"`. Present hard gates, evidence mapping, gaps, supported changes, variants, evidence IDs, sections, and digest. Stop for explicit approval such as `C1:balanced, C3:compact`.
5. Only after explicit approval: `python "$SKILL_DIR/scripts/run_cli.py" -- approve "<run-directory>/proposal.json" --select C1:balanced --output "<run-directory>/approval.json" --output-document "<run-directory>/tailored-resume.docx"`; then run `apply` and `validate` through `scripts/run_cli.py`.

For public job research, use the existing AI Job Search discovery workspace first, including its existing low-volume public LinkedIn skill when relevant. Retain roles without eligibility filtering; leave its export and tracker read-only, then pass the unfiltered export to `ats-agent research-jobs "<resume>" "<ai-job-search-export.json>" --candidate-id "<candidate-id>" --evidence "<candidate-evidence>" --context-url "<official-context-url>" --out "<fresh-run-directory>"` as applicable. Its legacy `{"seen": ...}` export is accepted directly: it captures the first 20 imported roles by default and visibly retains the rest; use repeatable `--job-id <stable-import-id>` to choose a later or larger explicit batch. Standard JSON-list items must provide an HTTPS `job_url` and may provide up to four `official_context_urls`; a fallback description is allowed only with its source URL, provider, and fetch time, and is always labelled non-official. Career-Ops Markdown uses pending `- [ ] URL | Company | Role` rows and remains a read-only backward-compatible input. This uses ordinary Scrapling capture only; it creates draft proposals, capture manifests, keyword-coverage reports, and evidence-building gap recommendations, never tracker writes, approvals, tailored CVs, or submissions.

For an unsupported but role-relevant gap, ask neutrally whether the candidate genuinely did the activity. A bare yes never becomes CV text. After yes, require the candidate to confirm the activity and its setting or timeframe; then write their truthful response to a candidate-owned supplemental evidence artifact in the run directory and rebuild a draft with the existing `--evidence` option. That artifact is candidate evidence, not a source-CV edit or approval: the rebuilt draft gets a fresh digest and still needs explicit approval before any apply step.

Read `references/approval-policy.md` before approval or application, and `references/troubleshooting.md` if the CLI cannot be verified.
