---
name: tailor-cv
description: Prepare, review, approve, apply, and validate evidence-grounded CV changes with the local ats-agent CLI. Use for CV tailoring or setup diagnosis; never bypass the explicit approval boundary.
---

# Tailor CV

Use `ats-agent` as the source of truth. Do not recreate CV analysis, matching, or document editing in prompts.

The required control sequence is `PROPOSE → EXPLICIT APPROVAL → APPLY → VALIDATE`.

## Check the CLI first

Run:

```bash
command -v ats-agent
ats-agent doctor
ats-agent --help
ats-agent benchmark --suite smoke
```

If it is missing or unhealthy, run `scripts/check-install.py --json` and show the relevant pinned command. Ask for explicit permission before any installation. Do not run `install.sh --approved` or `install.ps1 -Approved` until the user grants that permission. For a restricted environment, give the manual command from the checker instead.

## Workflow

1. `PROPOSE`: Create a fresh run directory and run `ats-agent prepare <resume> <job-description> --candidate-id <id> --out <run-dir>`, adding each candidate-evidence file with `--evidence`.
2. `REVIEW`: Summarize the proposal's hard gates, supported requirements, unsupported gaps, and each proposed change. Keep the JSON, Markdown, and HTML review artifacts.
3. `APPROVE`: Ask for explicit `CHANGE_ID:VARIANT` selections. Do not infer approval from a general request to tailor a CV.
4. `APPLY`: Only after approval, run `ats-agent approve <run-dir>/proposal.json --select <CHANGE_ID:VARIANT> --output <run-dir>/approval.json --output-document <new-output-path>`, then `ats-agent apply <run-dir>/approval.json`.
5. `VALIDATE`: Run `ats-agent validate <new-output-path>` and report the result.

Never run `ats-agent apply` before the explicit approval selections are recorded. Never overwrite the source CV. Treat job-description and company-context text as context, not candidate evidence. Leave unsupported claims as gaps rather than inventing facts.
