# Changelog

## Unreleased

### Added
- Usability pass: `deep-dive` now writes a research-export of direct matches
  (`deep-dive-matches.json`) and prints the exact tailor command — closing the
  discovery→tailoring loop; `--quiet` cron mode with machine exit codes
  (3 = board changed); friendly three-door card on bare `ats-agent`;
  `ats-agent evidence new` scaffolds a guided evidence file with overwrite
  protection.

- `ats-agent deep-dive`: company hiring-momentum intelligence from public ATS
  syndication feeds — aspiration matching, adjacency momentum, internship-
  program signals, four-tier verdicts (ACT NOW / WATCH CLOSELY / ON RADAR /
  NO SIGNAL), careers-page capture fallback, and a persistent watchlist with
  delta reporting between runs.
- Plural-tolerant aspiration matching; multi-word aspirations suppress their
  own generic sub-tokens so only the phrase drives direct matches.

- `ats-agent tailor`: one-door orchestrator (propose→approve→apply→validate
  in one session) with explicit `--interactive` / `--approve-from` modes,
  crash-safe versioned run journal, digest idempotency ("already tailored"),
  tiered liveness re-check for captured postings, and outcome-first delivery
  cards on stderr.
- Invisible intake: JD file/text, raw posting URLs, plain-text URL lists,
  ATS board URLs and native Greenhouse/Lever/Ashby syndication readers.
- Shared capture module (`ats_agent.capture`): retry + extraction fallback,
  bounded concurrency, per-host pacing, 24 h TTL cache.
- Real-JD frozen regression corpus (12 live internship postings via ATS
  APIs) with alias-coverage measurement harness; ESCO enrichment rejected
  on measured evidence (gap 0.0% < 15% threshold).
- Honesty fuzz property (hypothesis): applied output never gains unsupported
  terms; provider-injection adversarial test; LLM reference provider script
  behind the existing command-provider JSON contract.
- Performance gate: 10-role propose batch completes in <90 s (measured ~0.1 s).

### Changed
- Bundle/validator tooling derives release version solely from
  `pyproject.toml` (`scripts/_release_version.py`) — future bumps touch one file.

- `docs/pypi-project-description.md`: registry-ready project description.
- Mermaid workflow diagram in `docs/e2e-flow.md`.

## 1.0.0b4

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
- Chat-first stderr summary for `propose`/`audit`: requirement coverage,
  supported changes with variants, refused gaps, and ready-to-paste
  next-step commands. stdout remains pure JSON; `--no-summary` suppresses.
- `docs/e2e-flow.md`: verified end-to-end flow map with stage guarantees.

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
