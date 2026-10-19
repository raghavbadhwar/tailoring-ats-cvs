# Coverage Confidence to 91%

Status: implemented on `agent/evidence-os-guided-proof` pending final release
verification.

## Outcome

Turn the existing branch-aware coverage threshold into a release-confidence
signal for the approval and evidence boundaries. This work does not treat
coverage as proof of ATS success and does not change candidate evidence,
proposals, approvals, source CVs, or job applications.

## Decisions

- Keep `[tool.coverage.report].fail_under = 90` as the hard floor.
- Use 91% as the canonical runner's working target.
- Reuse `unittest`, coverage.py, the 270-case benchmark, and the current CLI
  propose-review-approve-apply-validate lifecycle.
- Require 100% execution of added or modified executable statement lines under
  `src/ats_agent`, relative to the PR/push base.
- Fail closed on missing or malformed coverage data in required PR/push runs;
  scheduled/manual runs without a base are explicitly non-gating.
- Keep the document corpus synthetic, bounded to eight files, 128 KiB per file,
  and validated by SHA-256 before parsing.
- Pin Cosmic Ray 8.7.0 and sample one deterministic mutation in each of four
  authority-critical modules from a detached worktree. Keep the job
  scheduled/manual and non-blocking until two Linux baselines pass within ten
  minutes.

## Acceptance

- Canonical runner reports at least 91.00% branch-aware coverage without
  lowering the 90% project floor.
- Changed-source guard proves pass, failure, malformed-report, missing-report,
  invalid-base, comment-only, and report-only behavior.
- Synthetic TXT/DOCX fixtures pass; malformed DOCX and manifest tampering fail
  before unsafe output or source mutation.
- Mutation artifacts identify the imported package path, runtime, selected
  mutations, killed/survived outcomes, and leave the primary checkout unchanged.
- Ruff, Mypy, compile, benchmark, adapters, build, installed-wheel, and the real
  approval-gated CLI lifecycle pass.

## Rollback

Revert the CI/test commit. There is no migration, external service, candidate
artifact, or production data to roll back.
