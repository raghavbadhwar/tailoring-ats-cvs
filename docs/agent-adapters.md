# Agent adapters

`ats-agent` is one local engine with thin CLI, Codex, and Claude Code entry points. Start with `python scripts/ensure_cli.py --check`; it only reports readiness or pinned installation commands. Run an installer only after explicit approval. Bootstrap exits are 20–25.

Use a fresh run directory outside the skill and plugin. Prepare creates proposal and review artifacts; summarize them and obtain explicit approval of change IDs and variants before approval, application, or validation. Candidate files remain local. In restricted or offline environments, use the documented pinned manual virtual environment installation.

Release archives are deterministic and verified with `SHA256SUMS`. Claude structural loading is tested in CI; interactive `claude --plugin-dir .` remains a manual host check when Claude Code is available.
