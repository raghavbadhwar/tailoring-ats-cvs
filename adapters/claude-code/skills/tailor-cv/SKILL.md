---
name: tailor-cv
description: Use the local ats-agent CLI to prepare, review, explicitly approve, apply, and validate evidence-grounded CV changes. Use for resume tailoring and diagnostics; never bypass the human approval boundary.
---

# Tailor CV

Use the installed `ats-agent` CLI as the authoritative engine. Do not reproduce CV analysis or document editing in the conversation.

First run `command -v ats-agent`, `ats-agent doctor`, and `ats-agent benchmark --suite smoke`.

If the CLI is unavailable or unhealthy, show this pinned command and ask for explicit permission before running it:

```bash
uv tool install "git+https://github.com/raghavbadhwar/tailoring-ats-cvs.git@f666ab5a6a3b074fad6f470f986436814b56a3d3"
```

If `uv` is unavailable, offer the equivalent `pipx install` command or a manual virtual-environment install. Never install software silently and never write CV data inside the plugin directory.

Follow `PROPOSE → EXPLICIT APPROVAL → APPLY → VALIDATE`:

1. Use `ats-agent prepare <resume> <job-description> --candidate-id <id> --out <fresh-run-dir>`, with repeatable `--evidence` files where available.
2. Read the generated proposal and review bundle; summarize hard gates, evidence-backed changes, and unsupported gaps.
3. Ask for exact `CHANGE_ID:VARIANT` selections.
4. Only after the user gives those selections, create an approval manifest with `ats-agent approve`, then run `ats-agent apply`.
5. Validate the new output with `ats-agent validate`.

Never treat the job description or company context as candidate evidence. Never infer qualifications, approve all changes by default, overwrite the source CV, or submit an application.
