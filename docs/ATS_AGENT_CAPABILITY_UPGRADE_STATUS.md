# ATS Agent Capability Upgrade Status

This is the execution record for
[`ATS_AGENT_CAPABILITY_UPGRADE_PLAN.md`](ATS_AGENT_CAPABILITY_UPGRADE_PLAN.md).
It distinguishes implemented, verified work from private-data and release
gates. It does not authorize application submission, tracker mutation, or
publication.

## Milestone 0 — baseline and sanitized corpus

- [x] Branch: `codex/ats-capability-upgrade` from
  `agent/public-job-research` / `e5bcc71a46bb827726d29fc24d2b294e4463076d`.
- [x] Editable local CLI recorded as `1.0.0b3`; `ats-agent doctor --strict`
  passed before implementation.
- [x] Sanitized TikTok, Zurich, CheQ, duplicate, and CGPA-conflict shapes are
  test fixtures under `tests/fixtures/capability-upgrade/`.
- [ ] Private pilot bundles: blocked pending candidate-approved local inputs;
  they must not be committed.
- [x] Focused and full local regression baseline captured: 154 tests pass.
- [x] The repository CI coverage sequence passes the unchanged 90% branch
  threshold. (A test-only subset measures 82%; it is not the defined CI gate.)

## Implementation milestones

- [x] 1. Proposal integrity — one canonical finalizer binds and verifies every
  persisted full proposal; altered/redacted reviews are non-approvable; failed
  persistence writes a blocked marker.
- [x] 2. Conflicts, duplicates, and value — scoped CGPA/GPA, dates,
  graduation, count/money/percentage, authorization, and employment conflicts
  block only affected changes; exact, normalized, and near duplicate handling
  is fail-closed or review-only.
- [x] 3. Sourced role dossiers — cleaned public capture, complete clauses,
  pilot ontology, source-bound dossier additions, and provenance-preserving
  merges are implemented.
- [x] 4. AI Job Search handoff — unfiltered JSON is canonical; shared evidence
  and official-context inputs, visible batch statuses, source manifests,
  labelled fallbacks, and seven-day apply-time liveness checks are implemented.
- [x] 5. Rewrite providers — deterministic default and explicit no-shell command
  provider are bounded, validated, digest-recorded, and never auto-approved.
- [x] 6. Strict DOCX — replacement-only mode, structural fingerprint, growth
  budget, transactional write, reparse, and an honest `rendered_layout:
  unverified` receipt are implemented.
- [x] 7. Coverage reporting — baseline, per-variant, and validated-output
  coverage; ranked evidence-building gaps; conflicts; and source quality are
  rendered without an opaque ATS score.
- [~] 8. Evaluation and release — the existing public synthetic benchmark has
  180 public cases (270 across public/adversarial/document checks), full local
  tests, CI coverage at 90%, package build, and a genuinely fresh wheel
  environment pass. Protected private holdout, consented real pilots, blinded
  human review, and hosted Linux/Windows CI remain external gates.

## Verification record

- Passed: `unittest discover -s tests -v` (154 tests), Ruff, Mypy,
  `check_benchmark.py` (270 cases), adapter validation, release-tree check,
  `python -m build`, and the exact CI coverage sequence at 90%.
- Passed: the built wheel installed its declared dependencies into a new
  temporary virtual environment outside the source tree. Its `--version`,
  strict doctor, and smoke benchmark passed.
- Fixed: release-workflow beta metadata now matches package version `1.0.0b3`.
- Blocked: private holdout and real-document pilots require candidate consented
  local documents and must not be replaced by sanitized fixtures.
