# Changelog

## Unreleased

- Established a visible, reproducible release baseline from the last green ordinary-source tree.
- Added a release-integrity checker that rejects encoded source payloads and self-replacing workflows.
- Enforced release-tree integrity before linting, tests, benchmarks, packaging, and the end-to-end workflow.
- Upgraded GitHub Actions to the current Node 24-compatible checkout and Python setup actions.
- Restored and verified the Python 3.10, 3.11, 3.12, and 3.13 compatibility matrix.

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
- Added a 100-case benchmark and CI regression gates.
