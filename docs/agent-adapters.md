# Agent adapters

`ats-agent` is one local engine with thin CLI, Codex, and Claude Code entry points. Start with `python scripts/ensure_cli.py --check`; it only reports readiness or pinned installation commands. Run an installer only after explicit approval. Bootstrap exits are 20–25.

Use a fresh run directory outside the skill and plugin. Prepare creates proposal and review artifacts; summarize them and obtain explicit approval of change IDs and variants before approval, application, or validation. Candidate files remain local. In restricted or offline environments, use the documented pinned manual virtual environment installation.

For public-job research, use the existing AI Job Search discovery workspace
first, including its existing low-volume public LinkedIn skill when relevant.
Retain roles without eligibility filtering, keep its export and tracker
read-only, then pass the unfiltered JSON export to `ats-agent research-jobs`.
The command also accepts repeatable `--evidence` candidate files and
`--context-url` official public URLs for the whole batch.
The AI Job Search legacy `{"seen": ...}` export is accepted directly.
It captures the first 20 imported roles by default and visibly retains the
rest; use repeatable `--job-id <stable-import-id>` to choose a later or larger
explicit batch.
Standard JSON-list items require `id` and HTTPS `job_url`, and may include
`company`, `role`, and up to four `official_context_urls`. A direct
capture failure may use a `fallback` only when it records `description`,
`source_url`, `provider`, and `fetched_at`; the output labels it as an
aggregator fallback. The input export and every tracker remain read-only.

When an unsupported gap is role-relevant, ask the candidate neutrally whether
they genuinely did the activity. A bare yes never becomes CV text. After yes,
require a confirmed activity plus its setting or timeframe, write the truthful
response to a candidate-owned supplemental evidence artifact in the run
directory, and rebuild a draft with the existing `--evidence` option. This
does not edit the source CV or approve anything; the fresh draft has its own
digest and remains subject to explicit approval before apply.

Release archives are deterministic and verified with `SHA256SUMS`. Claude structural loading is tested in CI; interactive `claude --plugin-dir .` remains a manual host check when Claude Code is available.
