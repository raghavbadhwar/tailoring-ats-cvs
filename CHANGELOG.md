# Changelog

## Unreleased

### Added

- Native Claude Code distribution: self-hosted plugin marketplace
  (`/plugin marketplace add raghavbadhwar/tailoring-ats-cvs`) and a bundled
  `/tailor-cv` slash command driving the full approval-first flow.
- Native Codex installer (`scripts/install_codex_skill.py`): idempotent
  skill install into `$CODEX_HOME/skills` with version checks and
  `--check/--uninstall/--force`.
- Bootstrap v2: ordered install attempts (PyPI → pinned GitHub tag →
  isolated venv) under one informed consent, with an install-state manifest
  so the engine resolves even when no tier touches PATH.

### Changed

- `ensure_cli.py --check` now enumerates the full attempt chain and reports
  how the executable was resolved; every status carries a human-readable
  `message`.

- Chat-first stderr summary for `propose`/`audit`: requirement coverage,
  supported changes with variants, refused gaps, and ready-to-paste
  next-step commands. stdout remains pure JSON; `--no-summary` suppresses.
- `docs/e2e-flow.md`: verified end-to-end flow map with stage guarantees.

### Fixed

- Requirement segmentation now keeps unpunctuated bullet lines; JD bullet
  lists no longer collapse into a single dropped run.
- Degree requirements match Indian degree spellings (B.Com, B.Tech, BSc,
  MBA, and similar) instead of reporting supported education as gaps.
- Alias matching ignores occurrences inside negation scopes, so evidence
  lines such as "No A/B testing experience" or "no AWS/GCP/Azure" are no
  longer counted as direct coverage.
- Disavowal lines from evidence files are never surfaced into the CV as
  proposed content.
- Surface-evidence insertions anchor to distinct related resume lines so
  multiple approved changes apply without anchor conflicts.

### Changed

- Deterministic rewrites emit a distinct balanced variant for semicolon-
  joined statements (sentence split) plus additional compact trims.

## 1.0.0b3

- Added approval-gated public job-list research through the local Scrapling CLI.
- Added per-role evidence-bound keyword coverage and genuine-evidence gap recommendations.
- Added a read-only Career-Ops pending-pipeline handoff.

## 1.0.0b2

- Added portable Agent Skill for Codex and Claude Code plugin launchers.
- Added explicit permission-gated CLI bootstrap and reproducible adapter bundles.
- Added adapter CI and approval-boundary end-to-end tests.

## 1.0.0-beta.1 — pending protected release gate

- Replaced hidden/encoded release payloads with one ordinary, reviewable source tree.
- Added candidate-scoped artifact fingerprints, canonical proposal digests, and schema-v2 explicit approvals.
- Added atomic evidence claims with metric value/unit/scope binding and ownership ceilings.
- Added clause-level requirement extraction, hard-gate evaluation, and indexed evidence matching.
- Added deterministic section-aware conservative, balanced, and compact rewrite variants.
- Added transactional output application, existing-output protection, and post-write verification.
- Improved DOCX preservation for mixed runs, table-cell insertions, headers, and unrelated OOXML parts.
- Unified review generation with full and redacted modes and an explicit `approve` CLI command.
- Added Benchmark v3 public, adversarial, document, smoke, and human-evaluation queue infrastructure with hashes, confidence intervals, baselines, and diversity checks.
- Added Python 3.10–3.13 Linux/Windows compatibility checks and a 90% branch-coverage release gate.
- Added dependency auditing, Bandit, CodeQL, dependency review, credential-shaped secret scanning, CycloneDX SBOM generation, and a protected tag-based release workflow.
- Added a fail-closed private-holdout release hook; the private cases themselves are never committed or uploaded as release artifacts.
- Added portable Codex and Claude Code adapters, approval-gated pinned bootstrap guidance, and deterministic skill/plugin ZIP release bundles.

## 0.9.0

- Added candidate-scoped evidence provenance and ownership protection.
- Added expanded JD requirements and hard-gate extraction.
- Added requirement-to-evidence mapping and safe external-evidence surfacing.
- Added conservative, balanced, and compact rewrite variants.
- Added deterministic factual, skill, metric, organization, status, and ownership validators.
- Added local Markdown and HTML approval review artifacts.
- Added anchored text editing, DOCX preserve mode, ATS-safe rebuild mode, and PDF-output blocking.
- Added final re-parse, hashes, diff, formatting audit, and applied-change log.
- Added `prepare`, `validate`, and `doctor` CLI commands.
- Added the legacy regression benchmark and CI gates.
