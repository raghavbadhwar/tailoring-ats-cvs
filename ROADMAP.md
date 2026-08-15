# Roadmap

## v1.1 — current foundation

- CI for skill validation, tests, and Python lint/compile checks.
- Versioned benchmark case schema with hallucination and evidence-preservation metrics.
- Dependency-free CLI contract for `audit`, `propose`, and approval-gated `apply`.
- Deterministic multi-agent report contract spanning ATS, role, language, recruiter, hiring-manager, and evidence review.
- Formatting audit for extractable text, reading order, spacing, bullets, and section headings.
- Integration boundaries for skill-compatible clients.

## v1.2 — evidence adapters

- Read-only PDF/DOCX/TXT extraction adapters with per-file diagnostics.
- Deterministic requirement/evidence matrix and change proposal serialization.
- Golden fixtures with anonymized CV/JD pairs and human-reviewed expected outcomes.

## v2.0 — reviewed integrations

- Optional Codex/ChatGPT and Claude loaders.
- VS Code command surface and local web dashboard backed by the same CLI contract.
- Human evaluation study before claiming improvement in screening outcomes.

Out of scope until evidence supports it: automatic application submission, a universal ATS score, and autonomous edits.
