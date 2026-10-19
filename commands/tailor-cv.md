---
description: Tailor a CV against a job description with explicit approval before any change is applied. Arguments: [cv-path] [job-description-path] [evidence-paths...]
---

# Tailor CV (approval-first)

You are driving the local `ats-agent` engine. Never edit the CV directly and
never invent qualifications. Follow these steps in order.

## Arguments

`$ARGUMENTS` may contain, space-separated: the CV path, the job-description
path, then any number of evidence file paths. If any required path is
missing, ask the user for it before continuing.

## 1. Resolve the skill directory

```sh
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:-}/.agents/skills/tailor-cv"
[ -d "$SKILL_DIR" ] || SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/tailor-cv"
[ -d "$SKILL_DIR" ] || SKILL_DIR=".agents/skills/tailor-cv"
```

## 2. Ensure the engine (one explicit consent)

Run `python "$SKILL_DIR/scripts/ensure_cli.py" --check`.

- On `ready`: continue.
- On `bootstrap_required` or `upgrade_required`: read the `attempts` list from
  the JSON aloud to the user — every tier that may be tried, in order — then
  ask exactly once: "May I install the ats-agent engine using this chain?
  [y/N]". Only after an explicit yes run:
  `python "$SKILL_DIR/scripts/ensure_cli.py" --install --manager auto`.
  A refusal stops here; offer the manual commands instead.
- On `unhealthy` or other statuses: show the JSON `message` verbatim and stop.

## 3. Propose (read-only)

Preferred fast path when the host supports it:

```sh
python "$SKILL_DIR/scripts/run_cli.py" -- tailor "<cv>" "<jd-or-urls>"   --candidate-id "<id>" [--evidence <evidence>...]   --run-dir "<run-dir>" --approve-from <approvals.json>
```

Otherwise use the granular flow:

Create a fresh run directory under the user's project (never inside the
plugin). Then:

```sh
python "$SKILL_DIR/scripts/run_cli.py" -- propose "<cv>" "<jd>" \
  --candidate-id <candidate-id> [--evidence <evidence>...] \
  --output <run-dir>/proposal.json
```

The stderr chat summary already shows coverage, supported changes, refused
gaps, and next-step commands. Present those results faithfully — including
what was REFUSED — without inventing scores or probabilities.

## 4. Stop for explicit approval

Ask the user to reply with an explicit list such as `C1:conservative,
C3:balanced`. Never select on their behalf.

## 5. Approve → Apply → Validate

Only for the changes the user named:

```sh
python "$SKILL_DIR/scripts/run_cli.py" -- approve "<run-dir>/proposal.json" \
  --select <id>:<variant> ... --output "<run-dir>/approval.json" \
  --output-document "<run-dir>/tailored-resume.docx"
python "$SKILL_DIR/scripts/run_cli.py" -- apply "<run-dir>/approval.json"
python "$SKILL_DIR/scripts/run_cli.py" -- validate "<run-dir>/tailored-resume.docx"
```

Report the final validation status and receipt paths. The source CV is never
modified.
