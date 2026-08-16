# Agent Instructions

## Source of truth

`ats-agent` is the source of truth for CV ingestion, evidence extraction,
requirement mapping, rewriting, approval, document application, and validation.
Do not recreate those behaviours in a Claude or Codex adapter.
In plain terms, ats-agent is the source of truth.

## Required workflow

1. PROPOSE: run `ats-agent prepare`; do not edit the CV.
2. APPROVE: require an explicit list of change IDs and variants.
3. APPLY: run `ats-agent approve`, then `ats-agent apply`.
4. VALIDATE: run `ats-agent validate` on the generated output.

## Safety rules

- Never treat the job description as candidate evidence.
- Never silently install or upgrade the CLI.
- Never auto-approve all changes or overwrite the source CV.
- Never use `shell=True` or lower benchmark, coverage, security, or approval gates.
- Keep candidate artifacts in a user-selected run directory, never `.agents/`, `.claude-plugin/`, `bin/`, or package directories.

## Verification commands

```bash
ruff check src tests scripts
mypy src/ats_agent
coverage run --branch --source=ats_agent -m unittest discover -s tests -v
coverage report --fail-under=90
python scripts/check_benchmark.py
python scripts/validate_agent_adapters.py
python -m build
```
