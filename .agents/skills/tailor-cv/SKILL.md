---
name: tailor-cv
description: Audit and tailor a candidate CV against a job description using the local ats-agent CLI. Use for CV assessment, evidence mapping, review, explicit approval, application, or validation.
metadata:
  author: raghavbadhwar
  version: "1.0.0-beta.2"
  repository: "https://github.com/raghavbadhwar/tailoring-ats-cvs"
---

# Tailor CV

Use `ats-agent` as the authoritative engine. Do not recreate its analysis or edit a CV directly.

Resolve the skill directory before running any bundled script:

```sh
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/tailor-cv"
[ -f "$SKILL_DIR/SKILL.md" ] || SKILL_DIR=".agents/skills/tailor-cv"
```

1. Run `python "$SKILL_DIR/scripts/ensure_cli.py" --check`. If it reports `bootstrap_required` or `upgrade_required`, show the recommended command and ask for permission. Do not run `--install` before permission.
2. Require a CV and job-description path; use a fresh user-selected run directory outside the skill or plugin. Evidence files are optional candidate evidence; company context is not candidate evidence.
3. Prepare only: `python "$SKILL_DIR/scripts/run_cli.py" -- prepare "<resume>" "<job-description>" --candidate-id "<candidate-id>" --out "<run-directory>"`.
4. Summarize: `python "$SKILL_DIR/scripts/summarize_proposal.py" "<run-directory>/proposal.json" --output "<run-directory>/summary.json"`. Present hard gates, evidence mapping, gaps, supported changes, variants, evidence IDs, sections, and digest. Stop for explicit approval such as `C1:balanced, C3:compact`.
5. Only after explicit approval: `python "$SKILL_DIR/scripts/run_cli.py" -- approve "<run-directory>/proposal.json" --select C1:balanced --output "<run-directory>/approval.json" --output-document "<run-directory>/tailored-resume.docx"`; then run `apply` and `validate` through `scripts/run_cli.py`.

Read `references/approval-policy.md` before approval or application, and `references/troubleshooting.md` if the CLI cannot be verified.
