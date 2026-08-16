# Roadmap

## v1.0.0-beta.1 — trustworthy engineering beta

Implemented on the `agent/trustworthy-v1` release branch:

- Candidate-scoped provenance ledger, atomic claims, metric/unit/scope binding, and ownership protection.
- Clause-level requirement extraction, hard-gate evaluation, and requirement-to-evidence mapping.
- Evidence-backed conservative, balanced, and compact rewrite variants behind deterministic validation.
- Digest-bound explicit approval, redacted/full review bundles, transactional apply, and audit receipts.
- TXT/Markdown/DOCX output with DOCX preserve/rebuild modes and malformed-input limits.
- Benchmark v3 public, adversarial, document, smoke, and human-evaluation queue infrastructure.
- Linux and Windows compatibility matrix for Python 3.10–3.13.
- Dedicated dependency, Bandit, CodeQL, secret-scan, SBOM, clean-wheel, and protected release gates.

Beta publication remains fail-closed until the protected 60-case private holdout is configured in the GitHub `release` environment and passes the release workflow.

## v1.0 — stable release criteria

- Complete the 25-pair anonymized real-document pilot.
- At least 95% of pilot DOCX outputs pass visual review without manual repair.
- Approved-change correction rate remains below 10% in the pilot.
- Complete the blinded 50-pair human rewrite evaluation and publish the methodology/results separately from automated benchmark scores.
- Resolve any P0/P1 safety defects found by the private holdout, pilot, or human evaluation.
- Promote only the exact beta lineage that passes all stable-release gates.

## Later, only after v1.0 safety gates

- Authenticated local web application.
- VS Code integration.
- Additional document templates.
- Opt-in official-company context retrieval.

Out of scope: automatic application submission, autonomous approval, and universal ATS or employer-acceptance scores.
