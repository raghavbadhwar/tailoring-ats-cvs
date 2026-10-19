# Capability Maximization Program

## Objective

Build the strongest evidence-grounded CV tailoring system we can verify, while
keeping the product's authority boundary intact:

```text
DISCOVER -> CAPTURE -> ANALYSE -> PROPOSE -> EXPLICIT APPROVAL -> APPLY -> VALIDATE
```

`ats-agent` remains the sole authority for candidate evidence, proposed wording,
approval, document mutation, and validation. No phase may claim employer
acceptance, universal ATS compatibility, or comparative superiority without the
corresponding independent evidence.

## Operating principles

1. Safety decisions are enforced at apply time, not merely displayed.
2. Every generated claim must be traceable to candidate-scoped evidence.
3. Benchmark reports identify the exact dataset expansion and source tree used.
4. Local deterministic improvements precede hosted product expansion.
5. Human, private-holdout, competitor, and candidate-outcome results are never
   simulated or replaced with synthetic proxies.
6. The smallest correct extension point is preferred over a parallel engine.

## Phase 0: Enforce trust and measurement boundaries

Deliverables:

- Block approval and apply when a mandatory hard gate is `unmet`.
- Require explicit, digest-bound acknowledgement of every `unknown` hard gate.
- Recursively redact nested candidate/JD prose and local paths in shareable
  review artifacts.
- Record both source-file and canonical expanded-case hashes in benchmark
  reports.
- Record commit, dirty/clean state, and a canonical digest over sorted tracked
  and non-ignored untracked repository files, including symlink link text but
  never target bytes, for benchmark code provenance. Ignored build/cache files
  are excluded.
- Mark real-JD corpus labels and metric status explicitly as heuristic,
  rule-derived, or human-validated.

Acceptance:

- Hand-edited approvals cannot bypass gate policy.
- Redaction regression fixtures leak no nested sentinel strings or paths.
- Reordering or changing expanded benchmark cases changes the expanded-case
  digest.
- A dirty checkout is never represented as the clean commit alone.

## Phase 1: Complete requirement and evidence understanding

Deliverables:

- Replace the small hand-maintained vocabulary ceiling with a versioned,
  reviewable ontology enrichment layer.
- Extract complete responsibility, qualification, eligibility, location,
  language, date, certification, and compensation clauses.
- Add context-aware negation, years-of-experience scope, and disjunction logic.
- Split evidence into atomic claims with explicit entailment and contradiction
  outcomes.
- Calibrate direct, transferable, unsupported, and unknown mappings against a
  human-labelled corpus.

Acceptance:

- Public extraction and matching precision/recall are reported separately with
  denominators and confidence intervals.
- Freeze a human-labelled train/dev/holdout corpus before ontology changes;
  predefine extraction and matching precision/recall thresholds, confidence
  intervals, adjudication, and safety non-regression gates. The 12-posting
  heuristic remains a diagnostic, not the primary acceptance set.
- No company-context term can become candidate evidence.

## Phase 2: Improve truthful rewrite quality

Deliverables:

- Plan changes jointly across the document to avoid duplicate or conflicting
  rewrites.
- Add sentence-level support checks for every generated clause.
- Improve section placement, chronology preservation, keyword use in context,
  concision, and document-level consistency.
- Reject rewrites whose only gain is keyword insertion without clearer evidence.
- Populate blinded human-evaluation outputs from frozen proposal artifacts.

Acceptance:

- Unsafe rewrite count remains zero on public and adversarial suites; the
  protected private-suite gate runs in the independent-evaluation phase.
- Produce frozen, blinded study artifacts and a preregistered factual-
  faithfulness/correction-rate rubric; execute and gate on the study in the
  independent-evaluation phase.
- Every accepted rewrite has a measurable supported coverage or clarity gain.

## Phase 3: Harden capture, privacy, and document fidelity

Deliverables:

- Remove the DNS validation/fetch time-of-check-to-time-of-use gap with
  connection-time peer-IP enforcement or an egress proxy that owns resolution
  and blocks non-global destinations.
- Add process-tree termination, CPU/memory/output limits, filesystem/network
  restrictions, unsupported-platform fail-closed behaviour, and per-platform
  tests for optional rewrite providers.
- Add field-level privacy threat tests and retention/deletion controls.
- Compare rendered DOCX pages as well as package structure before claiming
  strict preservation.

Acceptance:

- Redirect and rebinding tests cannot reach private or link-local addresses.
- Provider timeouts, malformed output, and resource exhaustion fail closed.
- Deterministic renderer comparisons detect page-count, overflow, clipping,
  font-substitution, and structural regressions before the real pilot begins.

## Phase 4: Independent comparative evaluation

Deliverables:

- Freeze task definitions, datasets, scorer versions, prompts, model/provider
  versions, seeds where available, and environment metadata.
- Maintain an optional, non-release-gating comparison track against named
  competitor outputs under equivalent input and policy constraints. Lack of
  competitor access must not block stable release.
- Complete the protected 60-case private holdout, 25-pair real-document pilot,
  and 50-pair blinded human rewrite study using predefined thresholds and an
  adjudication protocol.
- Track candidate corrections and output repair rate. Any interview-progression
  or longitudinal outcome research requires a separately approved consent,
  linkage, retention, ownership, power, and analysis protocol and is not a
  release gate.

Acceptance:

- Competitor wins, ties, losses, exclusions, and unavailable capabilities are
  all published with denominators.
- Human inter-rater agreement and disagreement handling are documented.
- At least 95% of pilot DOCX outputs pass visual review without manual repair,
  and approved-change correction rate remains below 10%.
- No release or marketing claim exceeds the evidence represented in the report.

## Phase 5: Stable release and continuous regression control

Deliverables:

- Pin private-holdout identity and reject public/private case overlap.
- Require exact beta lineage, clean source provenance, quality/security gates,
  pilot thresholds, and human-evaluation thresholds for stable promotion.
- Publish a model card/evaluation card describing intended use, limitations,
  datasets, metrics, and known failure modes.
- Monitor post-release safety regressions and candidate-reported corrections.

Stable-release gates remain external until real participant and protected
environment evidence exists. Passing local synthetic tests alone is not a
stable-release signal.

## Phase 6: Optional post-stable local product surface

This phase begins only after v1.0 safety gates and a separate browser/server
threat model, preserving the ordering in `ROADMAP.md`.

Deliverables:

- Add a single-user loopback-only HTTP adapter around canonical proposal,
  approval, apply, and receipt files.
- Reuse the engine's schemas and digest checks; do not duplicate policy in the
  UI.
- Require an unguessable startup capability token or equivalent local
  authentication in addition to CSRF and strict origin checks.
- Add session/file-access controls, upload limits, safe filenames, restrictive
  headers, startup cleanup, and explicit dependency/release review.
- Provide intake, requirement/evidence review, hard-gate decisions, change and
  variant approval, progress, output download, and local deletion.

Acceptance:

- The adapter binds only to loopback by default and requires no hosted account.
- Browser tests prove that unmet gates block and unknown gates require explicit
  acknowledgement.
- CLI and web adapter produce equivalent canonical artifacts for the same input.

Hosted accounts, remote storage, multi-user access, billing, and public sharing
remain out of scope until a separate threat model and data-governance review.

## Immediate execution order

1. Phase 0 hard-gate, redaction, and benchmark-provenance controls.
2. Human-labelled requirement/evidence corpus design and metric-contract repair.
3. Ontology/extraction and entailment improvements measured against that corpus.
4. Rewrite-quality and document-fidelity work.
5. Independent comparative study and stable-release evidence.
6. Loopback web alpha only after stable v1.0 and its separate threat model.
