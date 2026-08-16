# Release Verification — 2026-08-16

This record documents the verification performed on the exact release candidate published to `agent/9of10-usability-complete`.

## Local release gates

- 117 tests passed.
- Branch coverage: 93%, above the 90% release threshold.
- Deterministic benchmark: 150 cases.
- Hard-gate precision: 1.0.
- Hard-gate recall: 1.0.
- Supported-requirement recall: 1.0.
- Evidence-provenance coverage: 1.0.
- Ownership-escalation rate: 0.0.
- Unsupported-claim rate: 0.0.
- Apply accuracy: 1.0.
- Document reparse rate: 1.0.
- Style-preservation rate: 1.0.
- Rewrite-quality pass rate: 1.0.
- Rewrite-variant completeness rate: 1.0.
- Skill validation, source compilation and secret scan passed.
- The real propose → approve → apply example passed.
- The wheel built, installed and the CLI ran outside the source checkout.

## Safety invariants verified

- A job description is never treated as candidate evidence.
- Ownership cannot be escalated without explicit evidence.
- Supported factual additions reference real evidence IDs.
- Candidate identity isolation is enforced.
- Only explicitly approved changes are applied.
- Stale, unsupported, ambiguous, zero-match, no-op, source-overwriting and fake-PDF operations are blocked.
- The source CV is never overwritten.

## Claims deliberately not made

The project does not claim a universal ATS score, guaranteed employer acceptance, measured human rewrite preference or verified real-world interview outcomes. Those require external human evaluation and longitudinal outcome studies.

GitHub Actions is the authoritative online clean-install, lint, typing, package and security verification for the published branch.
