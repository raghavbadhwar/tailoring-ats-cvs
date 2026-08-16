# Changelog

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
