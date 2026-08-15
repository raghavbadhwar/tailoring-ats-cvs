# Roadmap to a 9/10-Usability Release

The repository uses measured capability gates rather than a universal ATS score. The current branch targets a safe and useful `0.2.0` alpha; a stable `1.0` requires broader semantic intelligence, document fixtures, and human evaluation.

## Implemented in `0.2.0`

- Candidate-specific evidence ledger with file/line provenance.
- Candidate identity isolation and real evidence-ID validation.
- Protected ownership levels that block unsupported escalation.
- Traceable requirement extraction for common skills and eligibility gates.
- Direct, transferable, and unsupported requirement-to-evidence mappings.
- Conservative complete rewrites for supported language improvements.
- Deterministic protection against unsupported known skills and numbers.
- Qualitative recruiter signals without a fake acceptance score.
- Read-only `PROPOSE`, local `REVIEW`, and approval-gated `APPLY` stages.
- Self-contained Markdown and HTML approval reports.
- Source hashing, stale proposal rejection, unique-match editing, no-op detection, diff, hashes, and applied logs.
- TXT/Markdown workflow and ordinary DOCX preserve/rebuild modes.
- DOCX header/footer extraction and preservation tests.
- Fake PDF output rejection; optional text-based PDF input.
- Packaged benchmark smoke cases.
- CI across Python 3.10, 3.12, and 3.13 with lint, typing, coverage, package build, installed-wheel smoke tests, and end-to-end examples.

## `0.3` — Structured resume and broader hard gates

- Normalize contact, summary, education, experience, projects, and skills into a structured resume model.
- Expand degree, graduation, location, work authorization, sponsorship, CGPA, certification, language, travel, and schedule extraction.
- Add source-span and confidence calibration fixtures for every hard-gate family.
- Support explicit candidate confirmation or correction of ambiguous evidence.
- Add conflict detection across CV and supporting files.

### Exit gate

- At least 90% hard-gate precision and recall on a human-reviewed golden set.
- No cross-candidate evidence accepted in adversarial tests.

## `0.4` — Semantic requirement matching

- Add provider-neutral lexical ranking and optional embedding retrieval.
- Distinguish direct, transferable, implied-but-unverified, unsupported, and hard-gate-blocked coverage.
- Add skill/acronym normalization and role/domain taxonomies.
- Explain every mapping with source evidence and confidence.

### Exit gate

- At least 90% supported-requirement recall on the golden dataset.
- Zero unsupported keyword insertions in the adversarial suite.

## `0.5` — Model-backed language generation behind validators

- Add a `RewriteProvider` interface and deterministic `NullProvider`.
- Add one optional reviewed model adapter with schema-constrained output.
- Generate conservative, balanced, and compact rewrite variants.
- Add critique/revision loops for summaries, bullets, skills, and role positioning.
- Redact personal data from external calls by default and log what was sent.
- Run all drafts through deterministic protected-fact validators before review.

### Exit gate

- Zero critical unsupported claims or ownership escalations in the adversarial benchmark.
- At least 80% human preference for approved rewrites over originals.

## `0.6` — Document robustness

- Add a structured DOCX document map with paragraph/run anchors and hashes.
- Extend preserve mode to common hyperlinks and fields where technically safe.
- Add an ATS-safe rebuild template with controlled typography and spacing.
- Add Windows/macOS fixture validation.
- Add an explicit PDF renderer adapter before enabling PDF output.

### Exit gate

- At least 95% successful DOCX edits on supported fixtures.
- At least 90% style-preservation pass rate.
- Zero source overwrite incidents.

## `0.7` — Benchmark and safety expansion

Build at least 100 anonymized or synthetic cases:

- 20 hard-gate cases;
- 20 requirement-mapping cases;
- 20 rewrite-quality cases;
- 20 hallucination/ownership adversarial cases;
- 20 document-ingestion/editing cases.

Measure:

- hard-gate precision/recall;
- supported-requirement recall;
- unsupported insertion rate;
- evidence-provenance coverage;
- ownership-escalation rate;
- apply accuracy;
- stale/ambiguous/no-op rejection rate;
- parser-risk delta;
- DOCX preservation;
- human rewrite preference.

Unimplemented metrics must remain `null`; they may never default to perfect values.

## `0.8` — Product usability

- Add `doctor` and `prepare` convenience commands.
- Add review notes and rewrite-variant selection.
- Add a run-directory manifest and resumable local workflow.
- Improve error messages and troubleshooting diagnostics.
- Add local-only privacy mode and optional provider configuration.
- Add accessible keyboard navigation and reduced-motion handling to review HTML.

## `0.9` — Release candidate

- Complete the 100+ case benchmark.
- Reach at least 90% coverage for core safety/workflow modules.
- Add dependency/security/secret scans in CI.
- Add architecture, threat model, privacy, evidence model, and release documentation.
- Reproduce the full DOCX demonstration from a clean wheel installation.
- Conduct a human evaluation before making screening-improvement claims.

## `1.0` — Stable 9/10-usability release

A release is stable only when a user can supply a real DOCX CV, JD, and project bank; receive traceable requirements and evidence mappings; approve complete factual rewrites in a local review interface; generate a verified styled duplicate; and reproduce the process from a clean installation with all safety and benchmark gates passing.

## Explicit non-goals before `1.0`

- Automatic job applications.
- Autonomous approval.
- A universal ATS score.
- Employer acceptance-rate claims.
- Arbitrary PDF editing.
- More named agents without new measured capability.
