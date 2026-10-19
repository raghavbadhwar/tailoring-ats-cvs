# Agent adapters

`ats-agent` is one local engine with thin CLI, Codex, and Claude Code entry points. Start with `python scripts/ensure_cli.py --check`; it only reports readiness or pinned installation commands. Run an installer only after explicit approval. Bootstrap exits are 20–25.

Use a fresh run directory outside the skill and plugin. Prepare creates proposal and review artifacts; summarize them and obtain explicit approval of change IDs and variants before approval, application, or validation. Candidate files remain local. In restricted or offline environments, use the documented pinned manual virtual environment installation.

For public-job research, pass an unfiltered AI Job Search JSON export to
`ats-agent research-jobs`. The command also accepts repeatable `--evidence`
candidate files and `--context-url` official public URLs for the whole batch.
Each item requires `id` and HTTPS `job_url`, and may
include `company`, `role`, and up to four `official_context_urls`. A direct
capture failure may use a `fallback` only when it records `description`,
`source_url`, `provider`, and `fetched_at`; the output labels it as an
aggregator fallback. The input export and every tracker remain read-only.

Release archives are deterministic and verified with `SHA256SUMS`. Claude structural loading is tested in CI; interactive `claude --plugin-dir .` remains a manual host check when Claude Code is available.
