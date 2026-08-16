# Threat Model

## Scope

This document covers the local evidence-grounded CV workflow: document ingestion, job-description analysis, evidence mapping, proposal generation, human review, approved document patching, and validation artifacts.

## Protected assets

- Candidate identity and contact information.
- Employment, education, dates, metrics, skills, certifications, ownership level, deployment status, and outcomes.
- Source CV and supporting evidence files.
- Evidence provenance records and approval decisions.
- Generated tailored documents, diffs, and audit logs.

## Trust boundaries

1. **Candidate files:** treated as untrusted input and parsed locally.
2. **Job description/company context:** vocabulary and requirements only; never candidate evidence.
3. **Optional public job research:** user-listed public HTTPS pages are untrusted context. Capture uses ordinary direct requests without credentials, redirects, proxies, stealth mode, or browser automation.
4. **Optional model provider:** untrusted drafting assistant; output must pass deterministic validators.
5. **Approval manifest:** user-controlled allow-list, but still validated against the proposal and evidence ledger.
6. **Document writer:** may change only anchored, approved spans and must never overwrite the source.

## Principal threats and controls

### Unsupported qualification injection

**Threat:** A JD, prompt injection, model, or manually altered proposal introduces a skill, employer, metric, certification, result, or production claim not supported by candidate evidence.

**Controls:** candidate-scoped evidence ledger; real evidence-ID validation; protected-fact comparison; unsupported changes marked ineligible; benchmark adversarial cases.

### Ownership escalation

**Threat:** Contributor language is rewritten as sole ownership or leadership.

**Controls:** protected ownership levels; rewrite validators; conservative wording rules; forbidden escalation benchmark cases.

### Cross-candidate contamination

**Threat:** Evidence belonging to another account user or candidate is used.

**Controls:** mandatory candidate ID; evidence-source identity checks; ledger rejects mismatched records.

### Stale or ambiguous edits

**Threat:** A proposal is applied after the source changed, or to multiple matching spans.

**Controls:** source SHA-256 binding; anchored paragraph/line metadata; zero-match, multi-match, conflict, and no-op rejection.

### Source destruction

**Threat:** The original CV is overwritten or a fake PDF is emitted.

**Controls:** output-path inequality check; duplicate output only; PDF output blocked unless a genuine renderer is introduced; output reparsing and hashes.

### Malicious document content

**Threat:** Corrupt archives, XML abuse, image-only PDFs, or prompt instructions embedded in documents influence behavior.

**Controls:** supported-format allow-list; extraction quality gates; parser failures become blocked results; document text is data, never executable instruction; optional PDF dependency.

### Sensitive-data disclosure

**Threat:** Candidate data is unintentionally sent to an external provider or logged publicly.

**Controls:** local-first default; no network provider in the core release; audit artifacts remain local; future providers require explicit opt-in and redaction controls.

### Supply-chain compromise

**Threat:** Vulnerable dependencies or unreviewed automation affect generated files.

**Controls:** minimal dependencies; dependency audit in CI; pinned GitHub Action major versions; wheel build/install smoke test; MIT-licensed source review.

## Residual risks

- Employer ATS behavior is proprietary and cannot be guaranteed.
- Deterministic semantic matching may miss unusual role terminology.
- Text extraction from highly complex DOCX/PDF layouts can lose visual meaning.
- Human reviewers must still verify that source evidence itself is truthful.
- The benchmark is synthetic/anonymized and does not establish real-world acceptance-rate improvement.

## Security invariants

- A job description is never evidence.
- Every factual addition references candidate-scoped evidence.
- Unsupported changes cannot be applied.
- Approval cannot bypass evidence validation.
- The source document is never overwritten.
- Unimplemented measurements are reported as unmeasured, not perfect.
