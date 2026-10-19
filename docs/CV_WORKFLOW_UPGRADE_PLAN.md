# CV workflow upgrade: correctness, speed, and reliable delivery

Date: 2026-09-05
Last current-state audit: 2026-09-08
Status: local implementation and clean-wheel verification are complete for the current source engine SHA-256 `e7ebd4808d4b4b36a0cb67905010f7d3ad72556fea236472ef2e3e8be80d738d`. The current tested wheel is `/tmp/ats-final-wheel.cLDbV2/tailoring_ats_cvs-1.0.0b4-py3-none-any.whl` (SHA-256 `9538d3dd25428ea791f095dba008343d91d91dae1b3cdcc079841baa6b7774df`) and is not installed pending fresh explicit approval. The managed `ats-agent 1.0.0b4` remains the separately verified prior engine SHA-256 `fb4fc67af048e55eb11049bb7e623a59b8358276eaccfdf615eb050b3233d52e` and still passes strict doctor. Candidate-specific, live-provider, manual, hosted, protected-holdout, and release/publication gates remain open. Historical execution records below are retained for auditability; the detailed 2026-09-08 refresh and the final status at the end are the current evidence.
Assessed checkout: `feat/capability-maximization-safety`, HEAD `d62d01c`; the initial assessment preserved 14 pre-existing modified files, and subsequent authorized implementation changes remain in the working tree.
Scope: repair the current local CLI workflow and its thin adapters.

## Decision

Keep `ats-agent` as the sole engine. Repair the existing entry points so they
share its evidence, capture, approval, and document guarantees. Reuse the
existing journal, capture cache, bounded fetch helper, review bundle, and
validation code after closing their identified gaps.

This is the immediate remediation sequence for the current workflow. It
complements [the capability program](CAPABILITY_MAXIMIZATION_PROGRAM.md) and
[the operating contract](../agent.md); it does not replace their independent
evaluation or stable-release gates. Historical checked milestones are not
evidence that the current checkout passes.

No new service, database, scheduler, agent framework, hosted UI, or mandatory
model dependency is needed. No automatic approvals, application submissions,
tracker writes, source-CV edits, or silent CLI installations are included.

## Current acceptance audit — 2026-09-08

This is a status audit, not a replacement for the detailed execution records
below. “Complete locally” means the current source and clean-wheel fixture
evidence cover the requirement; it does not mean a real candidate application
or stable release has occurred.

| Acceptance area | Current status | Authoritative evidence and limit |
|---|---|---|
| Sole-engine, provenance, approval, and source-CV protections | Complete locally | The source and clean wheel preserve `ats-agent` as the only CV engine. The cross-process fixture completed proposal → explicit digest-bound approval → apply → validate, with a distinct output and `source_overwrite: false`. New shared atomic-write and input/run-directory alias checks also reject receipt, review, capture-cache, and recovery sidecars that would target a source input. It is fixture evidence, not an approval for a real CV. |
| Network boundary, public-capture hardening, and output bounds | Complete locally; generic transport previously exercised | Current `Scrapling`/cURL coverage enforces public HTTPS/DNS, peer pinning, no redirects/proxies, scrubbed child environment, 45-second deadline, atomic output, and a 4 MiB declared/chunked-response boundary. The clean wheel's generic IANA capture and controlled low-limit probe are transport evidence only, not job-posting provenance. |
| Interrupted `research-jobs` recovery and bounded scheduling | Complete locally | Atomic journal/recovery writes and corrupt-artifact `blocked_recovery` tests passed. The scheduling regression proves only capture-needed roles enter the four-worker pool. A real candidate run still needs its selected directory and job. |
| Capture/provider/candidate reuse | Complete and measured locally | Canonical capture keys, provider-configuration identity, in-run coalescing, and locked per-batch candidate reuse are covered. The fresh synthetic run recorded 14 provider invocations for 14 unique contexts, 266 hits, zero coalesced waits, and zero resume captures/proposals. No paid provider was called. |
| Document truthfulness | Complete for fixture behaviour; real rendered output pending | Fixture receipt reports `content_validation: verified`, `rendered_layout: unverified`, and `delivery_ready: false`. The supplied source PDF had only a read-only format audit; no candidate output was created or visually approved. |
| Required local quality, coverage, performance, adapters, packaging, and installed-wheel checks | Complete locally | Current-source full workflow: 346 tests in 12.859 s; the unchanged `--fail-under=90` branch-coverage gate passed (reported 90%; raw 89.6164%). Benchmark, adapter, security, packaging, and clean-wheel checks passed. Measured synthetic p95 values and call counts are recorded in the final local refresh. |
| Managed CLI replacement | Pending explicit approval | The tested wheel is identified by SHA-256 `9538d3dd25428ea791f095dba008343d91d91dae1b3cdcc079841baa6b7774df`. The installed executable still verifies its older source SHA, so same version text is insufficient. |
| Live full-time role selection and real-document pilot | Pending candidate inputs and fresh official-board confirmation | A selected full-time role, candidate-confirmed standard full-time availability, location/work authorization, and a run directory remain necessary before `prepare`. Job text is never candidate evidence. |
| Live paid-provider measurement, hosted CI, protected holdout, blinded evaluation, and release/publication | External gates remain open | No credentials/cost authorization, protected holdout, hosted run, human layout review, or publication authority was supplied. These are intentionally not inferred from local results. |

The detailed current evidence record, exact artifacts, timings, role research,
and reproducible commands are in “Final local refresh and remaining external
gates”; the final status at the end explicitly supersedes the historical
records that follow it. Historical records remain audit history only.

## Baseline and limits of the evidence

These results were measured in this assessment, before implementation:

| Area | Observed result |
|---|---|
| Unit/integration suite | 281 tests ran; one bootstrap-test error |
| Coverage | 89% after adding the CI benchmark and CLI coverage steps; required threshold remains 90% |
| Typing | One Mypy assignment error in `workflow.py:311` |
| Other local gates | Ruff, adapter validation, whitespace, and 270 benchmark cases passed |
| Build | `--no-isolation` build blocked because the local environment lacks `setuptools.build_meta`; not proof of a packaging defect |
| CLI readiness | Both installed CLI and checkout passed strict doctor |
| Runtime identity | Both report `1.0.0b4`, but 18 Python modules differ |
| Sample proposal | Checkout CLI median 0.187 s; installed CLI median 0.157 s; five runs each |
| Startup | Installed `--version` median 0.126 s; adapter route median 0.326 s |
| In-process sample batch | Ten proposals took 0.167 s with profiling enabled |

The speed samples use small repository fixtures. They do not establish speed
for a real CV, large evidence bank, live website, or model provider. Live
capture and optional model latency remain unmeasured.

Reproduced defects: wildcard approval expansion; wrong board posting selected
from a URL list; board liveness `KeyError: 'path'`; JSON intake bypassing
capture/provenance; one capture failure aborting collection; and a corrupted
synthetic DOCX being reported as `already_tailored` on rerun.

Source inspection also found serial capture, repeated context fetches,
capture before resume checks, and repeated strict readiness checks. Existing
`fetch_many` changes a cached result's path to the requested destination
without copying the cached body there. Cache/concurrency helpers therefore
need verification and repair before callers adopt them.

## Intended user flow

```text
CV + candidate evidence + job inputs
  → normalize every role and record its identity/status
  → capture unique public sources with bounded work
  → analyse candidate evidence once per unchanged batch
  → emit each proposal, gaps, warnings, and review bundle as it completes
  → stop for explicit approval of persisted digest + change IDs + variants
  → verify approved inputs and posting freshness
  → apply to a distinct document
  → validate contents and report layout verification separately
```

`tailor` without approvals prepares review artifacts and exits successfully at
the proposal stage. It must not unexpectedly read stdin. Interactive review is
explicit. Supplying approvals resumes the exact persisted proposals; it does
not rebuild different wording under old selections. Corrected evidence or
changed requirements create a fresh proposal requiring fresh approval.

A zero-change proposal is a useful outcome. It produces a review explaining
why no supported edit is needed; it does not force a document rewrite.

## Phase sequence and exit gates

Execute in order. Each phase ends with a focused, reviewable change and the
checks below. Do not begin a broad refactor while a smaller shared fix works.

### Phase 0 — Establish a reproducible baseline

Primary files: `tests/test_agent_bootstrap.py`, `src/ats_agent/workflow.py`,
`scripts/perf_batch_benchmark.py`, existing diagnostic/reporting code.

- Record the dirty diff and preserve all pre-existing edits. Verify the
  checkout before execution; do not reset, stash, or overwrite others' work.
- Make the failing bootstrap test independent of the user's real install
  manifest. Fix the Mypy error without suppressing or weakening checks.
- Resolve the missing build backend through an explicitly authorized local
  environment setup if necessary; do not silently install or upgrade the CLI.
- Extend the existing performance script with realistic sanitized fixtures,
  stage times, operation counts, interpreter/platform metadata, and exact code
  identity. Use monotonic timing and exclude candidate text from diagnostics.
- Measure cold startup, warm analysis, capture, rewrite calls, review writing,
  apply, validation, and rerun separately. Record elapsed time, successes,
  blocked roles, cache hits, network calls, and time to first proposal.

Exit: the baseline is reproducible; the known test/type errors are resolved;
performance fixtures and targets below are frozen before optimization.

### Phase 1 — Close approval and output-integrity gaps

Primary files: `orchestrator.py`, `cli.py`, `review.py`, `models.py`,
`workflow.py`, and existing approval/orchestrator tests and adapter contracts.

- Consume persisted `ApprovalManifest` records for the exact reviewed role,
  proposal digest, changes, variants, hard-gate acknowledgements, document
  mode, and output path. Reuse the existing schema and verifier.
- Reject wildcard selections, `defaults`, and omitted variant choices where
  variants exist. Reject unknown/invalid selections instead of silently
  applying a surviving subset.
- Reject legacy token-only `--approve-from` maps with a migration explanation.
  If a batch index is needed, let it reference ordinary approval manifests;
  it must not define a second approval policy. Update CLI help, review output,
  adapter instructions, and tests together.
- Make proposal-only operation explicit and noninteractive by default.
- Before reporting a completed role on rerun, verify the proposal, approval,
  receipt, input identities, and output hash. Missing/corrupt output must be
  reported as requiring recovery; never silently overwrite it.
- Preserve apply-time source/evidence hash checks and hard-gate enforcement.

Exit: replaying approval after changing evidence, JD, proposal wording, variant,
or document mode cannot authorize new work; `*` cannot approve anything;
corrupted output never returns a ready status; the source CV is unchanged.

### Phase 2 — Unify role intake and public capture

Primary files: `intake.py`, `job_research.py`, `orchestrator.py`, `boards.py`,
`capture.py`, and existing job/network/orchestrator tests.

- Reuse `research-jobs` import normalization and provenance policy inside the
  convenience entry point. Support the existing standard and legacy `seen`
  exports without treating third-party descriptions as official captures.
- Retain stable source role IDs across list reordering. Represent every row,
  including invalid imports, duplicates, expired postings, failures, and rows
  beyond the active batch limit. Do not silently select or drop a role.
- For a posting URL, resolve its exact posting identity, allowing only
  provider-defined URL equivalences. A missing match is blocked. A board root
  expands to a bounded, visible role list; it never implicitly means the first
  posting. Fetch a board feed once per batch.
- Persist a complete capture record and actual body for board and page sources
  using the existing capture schema. Keep URL, time, hash, method, extraction
  result, and provenance type. Verify board liveness through the board API.
- Continue unrelated roles after one failure; persist each result immediately.
- Remove the implicit browser/dynamic third retry in `capture_url`, which
  conflicts with `agent.md`'s ordinary public HTTPS capture policy. Preserve
  HTTPS/public-address checks and no-redirect behavior. Do not weaken the
  existing network-hardening requirements to gain speed.
- Changed posting content requires review of a fresh draft; an unavailable
  required freshness check cannot silently authorize apply. Separate analysis
  cache freshness from apply-time verification.

Exit: the same inputs produce equivalent role identities, provenance, and
eligibility decisions through both entry points; no wrong-role fallback;
complete manifest after mixed success/failure; board liveness cannot fail for
missing capture fields; existing unsafe-network tests still pass.

### Phase 3 — Remove repeated work and bound waiting

Primary files: `capture.py`, `job_research.py`, `orchestrator.py`,
`workflow.py`, `doctor.py`, existing adapter runner/bootstrap scripts,
and `scripts/perf_batch_benchmark.py`.

- Repair and then reuse `capture_cached` and `fetch_many`. A cache hit must
  validate metadata and body hash and materialize the body at the returned
  destination. Write cache entries atomically; stale, missing, or tampered
  entries require a fresh capture. Preserve source classification per role.
- Deduplicate URLs and coalesce duplicate requests within a run. Fetch unique
  company context once and link it into each role's provenance.
- Use bounded capture concurrency across hosts, up to the existing four-worker
  ceiling. Preserve host pacing with synchronized scheduling; do not let
  workers race through the current shared timestamp dictionary. Surface
  results as they finish while preserving manifest input order.
- Introduce an end-to-end capture deadline, including DNS, retries, subprocess
  waits, and cleanup. Fail permanent errors promptly. Retry only transient errors within
  budget; honor `Retry-After` by deferring when it exceeds the remaining budget.
  Preserve timeout cleanup, cancellation, and a visible failed/deferred status.
- Reuse loaded CV/evidence and the candidate ledger within one unchanged batch.
  Key reuse by candidate identity and content hashes. Rebuild on input change;
  do not introduce a global candidate-data cache or bypass apply-time checks.
- Consult the journal before recapturing or regenerating completed stages.
  Resume interrupted work; preserve completed proposal digests. Keep fresh
  posting verification in the approved apply path where required.
- Consolidate strict readiness checks so one operation does not run them in
  both the adapter and engine. Reuse verified health only for the same resolved
  executable/environment identity; keep explicit `doctor --strict` and
  installation/upgrade checks. Do not use a version string alone as identity.
- Emit stage/progress information on stderr while preserving JSON stdout.
  Record redacted timings and counters alongside existing run artifacts.
- Measure optional model-provider time separately. Remove duplicate calls for
  identical contexts within the run. Only add bounded provider parallelism if
  it dominates measured latency and the existing provider contract permits it;
  retain per-result evidence validation, output limits, and timeout cleanup.

Exit: warm analysis reruns make zero unnecessary fetch/rewrite calls; shared
sources fetch once; failures cannot consume unbounded retry time; concurrency
respects host pacing; cached and uncached runs make equivalent evidence and
approval decisions; performance targets pass.

### Phase 4 — Make document delivery honest and easy to review

Primary files: `documents.py`, `workflow.py`, `cli.py`, `review.py`,
`summary.py`, and existing document/review tests.

- Default existing DOCX edits to strict preservation. For supported insertions
  that strict mode cannot perform, show the trade-off in the proposal and
  require explicit approval of preserve/rebuild mode; never switch silently.
- Verify the complete approved document change set, including section placement
  and unaffected structure, using existing document checks and fingerprints.
- Keep `content_validated`, structural preservation, and rendered-layout
  verification distinct. A parsable DOCX is not proof of pagination or layout.
- Use an already available renderer for before/after inspection where possible.
  If unavailable, report `layout_unverified` and require manual visual review
  before calling the document delivery-ready; do not silently install one.
- Persist hashes, diff, applied-change receipt, and validation status reliably.
  A post-write receipt failure must leave an explicit recoverable state.
- Adapt the existing CLI/HTML summary: supported changes, gaps, approvals
  needed, current stage, failures, and next action first; full audit detail
  remains available. No new visual surface is needed.

Exit: approved fixture changes land in the correct section, no unapproved
content changes occur, source hashes remain unchanged, and every delivered
file has an accurate receipt and visible layout-verification state.

### Phase 5 — Verify the installed product and release readiness

Primary files: existing CI/release workflows, package/version metadata,
adapter bootstrap policy, release documentation, and benchmark scripts.

- Run the full unchanged repository gates and the upgraded performance check.
  Include a synthetic CLI journey covering proposal-only exit, explicit
  approval, apply, validation, interrupted resume, and a mixed-result batch.
- Build and test a wheel outside the source checkout in a clean environment
  through the authorized development/release process. Test both thin adapters
  against that wheel, not just editable source imports.
- Record executable path, package version, and build/source identity so an
  installed binary cannot be confused with the current dirty checkout.
- Update compatibility guidance for legacy approval maps and old journals.
  Invalid/old state must fail clearly, never be reinterpreted as approval.
- With candidate consent and selected run directories, conduct real-document
  pilots and visually inspect the outputs. Report actual time to first review,
  total machine time, user correction count, and manual layout repairs.
- Follow the existing protected release process. Hosted compatibility/security
  jobs, private holdout, pilot, and blinded evaluation remain separate evidence
  requirements; local synthetic results do not establish stable readiness.

Exit: local gates and clean-wheel tests pass; remaining external gates are
explicitly listed. Publication, tagging, merging, and replacing the user's
installed CLI require separate authorization and are not part of this plan.

## Speed acceptance contract

The following are proposed upgrade targets, not current performance claims.
Phase 0 freezes fixture hashes and the reference environment before tuning.
Do not relax targets or correctness gates to make an implementation pass.

Use a sanitized two-page DOCX, 800–1,200 extracted CV words, five evidence
files totalling 2,500–5,000 words, and 20 varied JDs of 500–1,500 words each.
Measure cold subprocess startup separately from warmed engine timing. Use at
least 20 repetitions for p50/p95 reporting; exclude human approval waiting.

| Scenario | Acceptance target |
|---|---|
| One local deterministic proposal, including review bundle | p95 ≤ 2 s warm; ≤ 3 s cold |
| Ten / twenty local roles, including review bundles | p95 ≤ 15 s / 30 s |
| Resume 20 unchanged prepared roles, local inputs | p95 ≤ 2 s; zero recaptures or rewrite calls |
| Shared company/board context | One underlying fetch per unique URL/feed per batch |
| Healthy distinct-host captures under fixed mocked latency | Concurrent elapsed time ≤ 50% of sequential baseline; host pacing still enforced |
| One ordinary page capture | Default total deadline 45 s, including retry waits; no new attempt after expiry |
| Dead/blocked page among healthy roles | Healthy proposals appear without waiting for the blocked role's retry budget |
| Optional provider | Report invocation count and latency separately; no paid/live calls in ordinary CI |
| Cached versus fresh analysis | Equivalent substantive mappings/changes after excluding timestamps and cache diagnostics |

CI should use deterministic request/call-count assertions and controlled network
delays. Hardware-sensitive wall-clock targets also run on the recorded reference
machine; record CI timing separately. Live website latency is reported, not
treated as a controlled speed guarantee. Analysis cache hits never replace a
required apply-time freshness check.

## Verification and delivery

Use the existing test suite for behavior regressions; add focused cases for the
failures above rather than another framework or a duplicate test architecture.
Run focused checks per phase, then the required full gates at integration:

```sh
ruff check src tests scripts
mypy src/ats_agent
coverage run --branch --source=ats_agent -m unittest discover -s tests -v
# Append the existing benchmark/CLI coverage steps from CI before the report.
coverage report --fail-under=90
python scripts/check_benchmark.py
python scripts/validate_agent_adapters.py
python scripts/perf_batch_benchmark.py
python -m build
```

Run hosted compatibility/security, clean-wheel, adapter-bundle, and protected
release checks as specified by the existing workflows. Do not count a partial
local command sequence as those checks passing.

Each phase's review should contain the changed behavior, files, focused check
results, timing/call-count deltas where relevant, and unresolved limits.
Reverting an implementation patch must not delete candidate run artifacts;
unsupported state remains readable or explicitly blocked. Never resume old
approvals against a new proposal merely to make rollback convenient.

Execution is operator-led and sequential because the identified paths overlap.
No implementation workers are authorized by this planning request. At execution
start, disclose the configured operator-model mismatch noted by the session
policy: this session runs `gpt-6-astra`, while that policy expects
`gpt-5.6-sol`; the hook cannot switch it automatically.

## Deferred work

Defer a new UI, expanded ontology, broad rewrite-provider redesign, hosted
storage, cross-candidate caching, and competitor comparisons. The immediate
upgrade succeeds when the existing workflow selects the correct roles, keeps
approval bound to reviewed wording, avoids repeated work, survives interruption,
and delivers an honestly validated document. Broader capability work resumes
under the existing program after these exit gates pass.

## Earlier execution record — 2026-09-05

This is the earlier implementation report. The subsequent verification below
supersedes its completion claims where the review reproduced remaining defects.

### Completed locally

- Reused the existing `ats-agent` workflow and thin adapters. No dependencies,
  CLI installs, candidate CVs, trackers, applications, or external services
  were changed.
- Fixed the initial mypy failure and added deterministic sanitized performance
  fixtures under `benchmarks/perf-fixtures/`. The original baseline was 281
  tests in 5.883 s; the final suite was 297 tests in 7.921 s.
- Approval now requires the persisted proposal digest, exact ordered change IDs,
  and an explicit variant for every variant-bearing change. Legacy token maps,
  wildcards, defaults, and apply-time approval overrides fail closed. Output
  hashes and persisted receipts are checked before an idempotent rerun is
  reported complete; receipt-write failure leaves a recoverable
  `.receipt-pending.json` record.
- Role intake retains every requested role, captures ordinary public HTTPS
  sources only, rejects ambiguous board fallbacks, and isolates a failed capture
  to its own blocked outcome. Capture caching deduplicates shared URLs, keeps
  host pacing, and materializes each requested destination. Controlled tests
  verify one underlying capture for a cache miss followed by a hit, and one
  underlying capture for two duplicate batch destinations.
- Existing DOCX sources default to `strict-preserve`; document-mode changes
  remain approval-manifest data. Delivery separates verified content from
  structural preservation and unverified rendered layout.
- Repaired the packaged smoke benchmark so its fixture stays materialized while
  a wheel consumes it. The wheel at
  `dist/tailoring_ats_cvs-1.0.0b4-py3-none-any.whl` imported outside the
  checkout and completed `ats-agent benchmark --suite smoke` from bundled data.

### Measurements

The final deterministic offline benchmark used 10 roles × 20 repetitions on
CPython 3.14.6 / macOS 26.6.2 arm64. It recorded p50/p95 total time of
1.176 s / 1.606 s and p50/p95 time to first proposal of 0.105 s / 0.122 s,
against the 15 s ten-role target. It made zero network and provider calls by
design; cache performance is therefore reported separately through the
controlled call-count tests above. These synthetic results are not live-site,
provider, cold-start, or real-document performance claims.

### Checks actually run

- `ruff check src tests scripts` — passed
- `mypy src/ats_agent` — passed
- Full `coverage run --branch` unit/benchmark/CLI journey — 297 tests passed;
  `coverage report --fail-under=90` — passed at 90%
- `python scripts/check_benchmark.py` — 270 frozen cases passed
- `python scripts/validate_agent_adapters.py` — passed
- Release-tree, skill, benchmark-diversity, adapter-bundle, compile, and local
  dependency-audit checks — passed; audit reported no known vulnerabilities
- `python -m build --no-isolation` — passed with the existing Python 3.11
  build frontend and existing local packages, producing sdist and wheel in
  `dist/`. The default Python 3.14 development venv still lacks
  `setuptools.build_meta`; it was not modified or upgraded.

### Remaining external release gates

Hosted compatibility/security CI, a truly isolated dependency-installed wheel
environment, candidate-consented real-DOCX pilots, manual rendered-layout
inspection, live-site capture timings, provider latency/cost measurements,
private holdout, and protected release publication remain unperformed. This
local record does not claim stable-release readiness.

## Independent recheck and repairs — 2026-09-05

### Finding

The upgrade was not fully done. The recheck started with 297 passing tests but
reproduced incomplete legacy intake, incorrect board-posting selection,
recapture before resume, and approval/delivery integrity gaps. The existing
engine, normalization, cache, journal, and validation paths were adapted; no
new framework or dependency was introduced. Pre-existing edits were preserved
in place, with a starting diff saved at `/tmp/ats-upgrade-review-initial.diff`.

### Repairs verified locally

- Shared normalization now retains legacy `seen` entries, invalid/expired rows,
  duplicates, and rows outside the batch limit. Role IDs remain stable across
  reordering. Posting URLs match the exact posting; a shared board feed is read
  once during intake.
- Bounded workers capture independent roles and persist completed proposals
  before slower roles finish. Both entry points reuse the capture cache;
  concurrent identical requests share one underlying capture. Cache metadata,
  timestamps, body hashes, and materialized destinations are checked.
- Unchanged `tailor` runs restore verified journal stages before capture or
  rewriting. Changed approvals cannot be ignored on completed reruns, and
  changed inputs cannot rebuild a proposal under an old approval. Damaged
  delivery artifacts block recovery rather than being overwritten.
- Direct `apply` and `tailor` share source-integrity and posting-freshness
  enforcement. Unavailable or changed postings block application. Zero
  supported changes produce a useful `no_changes` review result.
- Candidate parsing and evidence-ledger work are reused within an unchanged
  candidate batch. Runtime identity includes an engine-source hash, including
  when imported from a wheel. Duplicate strict doctor work was removed from
  the engine's convenience entry point.
- Public capture bounds DNS waiting and subprocess execution, skips permanent
  HTTP failures, and synchronizes host pacing. Board capture rejects redirects,
  private DNS destinations, host-spoofing URLs, oversized responses, and retries
  whose delay exceeds the remaining budget.
- Existing structural DOCX protection and explicit approvals remain mandatory;
  rendered layout is reported as unverified. No candidate CV was changed.

### Comparable performance evidence

The pre-review dirty checkout was reconstructed from HEAD plus the saved diff
in `/tmp/ats-upgrade-before-lz665zs0`. Both versions used the same frozen
`benchmarks/perf-fixtures/workflow-v2/` corpus and measurement script: a synthetic
DOCX, five evidence files, twenty varied roles, and twenty repetitions on
CPython 3.14.6 / macOS 26.6.2 arm64. Proposal timings include review writing.
Capture is mocked with 50 ms latency; model-provider calls are not exercised.

| p95 seconds | Before recheck repairs | After repairs | Budget |
|---|---:|---:|---:|
| One warm role | 0.1893 | 0.2007 | 2 |
| One cold CLI prepare | 0.4822 | 0.3860 | 3 |
| Ten roles | 1.7329 | 1.4190 | 15 |
| Twenty roles | 3.6746 | 2.7505 | 30 |
| Unchanged twenty-role resume | 1.2790 | 0.2568 | 2 |

Across twenty resumes, repeated captures fell from 400 to zero; repeated
proposal calls were zero in both versions. The final run passed all measured
budgets. The small warm single-role increase is retained in the table; these
results do not establish a universal speedup or real-site performance.

Reports: `/tmp/ats-upgrade-before-performance.json` and
`/tmp/ats-upgrade-review-performance.json`. Final engine-source SHA-256:
`eb702a1e64c59e4db9291ea28e2caae1a02b83a37583516fe44692fdaf26886d`.

### Checks completed after the repairs

- Ruff and Mypy passed; full suite: **307 tests passed in 6.966 s**.
- Branch coverage plus the existing CI benchmark/CLI journey passed at **90%**;
  the 270-case frozen benchmark passed. No acceptance threshold was lowered.
- Adapter, skill, benchmark-diversity, release-tree, bundle, and whitespace
  validation passed.
- Wheel and sdist built with existing Python 3.11 build tools and existing
  packages, without installation. Final artifacts are under
  `/tmp/ats-upgrade-review-dist/`.
- The final wheel imported outside the checkout with isolated source paths,
  passed strict doctor and all eight bundled smoke cases, and completed
  adapter prepare → explicit synthetic approval → apply → validate. Existing
  dependencies were reused; this was not a clean dependency installation.

Detailed local evidence: `/tmp/ats-upgrade-review-tests.log`,
`/tmp/ats-upgrade-review-ci.log`, `/tmp/ats-upgrade-review-build.log`, and
`/tmp/ats-upgrade-review-wheel.json`.

### Superseded installation claim

The earlier report claimed that the tested wheel was installed after explicit
approval. Current strict-doctor comparison does not support that as the current
state: the user-installed executable remains on engine SHA-256
`eb702a1e64c59e4db9291ea28e2caae1a02b83a37583516fe44692fdaf26886d`, not
the current tested engine. That claim is not used as evidence; the current
continuation below records the verified installed-runtime boundary. No
installation or upgrade was performed in this continuation.

The external release gates listed above remain open. At that point, live/provider
and per-stage apply/validation timing evidence, provider-call deduplication,
and interrupted `research-jobs` resume were not established by these checks.
The current continuation below supersedes that local-status statement.
The verified resume path is `tailor`. DNS deadlines return control to the
caller but cannot portably cancel the operating-system resolver. Board
transport uses socket timeouts; hard cancellation under a trickling response
or connection-time DNS re-resolution, and connection-time peer-IP enforcement,
remain network-hardening gaps. They are not claimed complete by this record.

## Current continuation record — 2026-09-05

This section supersedes the preceding local-status statements for the current
checkout. It records only work executed in that local implementation
continuation; no candidate CV, application, tracker, hosted service, or
installed user CLI was changed at that stage. Later addenda record the
draft-only public job research and the separately authorized CLI replacement.

### Local requirements completed

| Requirement | Status | Evidence and boundary |
|---|---|---|
| Public-network hardening | Implemented and tested | Capture validates credential-free public HTTPS targets, bounds DNS/subprocess/retry time, strips ambient proxy/TLS/Python overrides, and writes through a same-directory temporary file. Direct capture now invokes the separately installed, pinned Scrapling `0.4.12` Python runtime with its bundled `curl_cffi.Session` and `CurlOpt.RESOLVE` set to the already validated public DNS answers; redirects and proxies are disabled and TLS verification is enabled before the response is converted through Scrapling's existing converter. Board feeds retain their numeric-peer, TLS-hostname, no-proxy/no-redirect transport, 45-second total read deadline, and 4 MiB response limit. Direct capture rejects a final temporary output over 4 MiB before decoding or publishing it. The parent still cannot observe the child socket or cap bytes received before that temporary-file check, and a timed-out caller cannot portably cancel the operating-system resolver thread. |
| Interrupted `research-jobs` recovery | Implemented and tested | Schema-2 manifests are atomically checkpointed and bound to normalized jobs, candidate/evidence digests, contexts, constraints, and provider identity. Only same-run proposals with a valid proposal digest, verified capture hashes, and review bundle are reused. A corrupt persisted proposal becomes a visible `blocked_recovery` row retaining job identity; it is never silently rebuilt. The interruption test proves a completed role resumes with zero recapture/rewrite calls. |
| Provider-call deduplication | Implemented and measured | `RewriteCache` coalesces equal contexts within one unchanged `tailor` or `research-jobs` run, returns defensive copies, releases waiters after provider failure, and reports invocation/hit/wait counts. It reuses the existing provider contract; no provider framework or dependency was added. |
| Concurrent candidate-input reuse | Implemented and measured | A cache-local standard-library lock now protects the existing per-run candidate cache. Four concurrent synthetic `research-jobs` roles load the CV/evidence/ledger once instead of four times, without creating a cross-run cache or changing content/evidence policy. |
| Performance coverage | Implemented and measured | The frozen 20-role corpus measures warm/cold preparation, first proposal, analysis, review writing, fresh/cache-hit capture, distinct-host sequential/parallel capture, DOCX apply, parse/audit validation, and resume. It records outcome states, cache/network/provider call counts, and deterministic provider latency rather than inferring them. |
| Synthetic document validation | Completed as a fixture-only check | A fresh fixture run used prepare → explicit digest-bound approval → strict-preserve apply → validate. Validation reported `valid`; Quick Look rendered a readable first-page thumbnail of source and result. The fixture still has `layout_unverified` because the local LibreOffice launcher is broken and a thumbnail is not a full-document layout review. |

### Phase exit-gate audit

| Gate | Current authoritative evidence | Boundary still retained |
|---|---|---|
| Phase 0 — reproducible baseline | Frozen fixture manifest; schema-5 `scripts/perf_batch_benchmark.py`; Ruff and Mypy pass. | Measurements are synthetic and use no candidate text or live network. |
| Phase 1 — approval/output integrity | `test_hash_binding`, `test_apply_atomicity`, `test_review_unified`, and `test_workflow_guards` pass in the final 328-test suite. | No real candidate approval or source document was used. |
| Phase 2 — intake/capture | `test_intake_normalization`, `test_orchestrator`, `test_job_research`, and `test_network_units` cover retained rows, exact board matching, provenance, and isolated failures. Six later public-job research attempts are recorded below: one successful Lever-hosted capture remains third-party provenance, and five failed direct Ashby captures remain explicit fallback evidence. | Employer-page freshness and candidate eligibility must be rechecked immediately before any application. |
| Phase 3 — reuse/deadlines | Cache, recovery, provider, candidate-cache concurrency, non-capture scheduling, and same-host pacing tests plus the measured 20-role resume prove local reuse, bounded mock work, and zero unnecessary resume calls. Direct Scrapling now pins its actual cURL connection to validated DNS answers. | OS DNS cancellation, child-socket observation, and streaming input-byte enforcement before the child writes its temporary file remain explicitly unclaimed. |
| Phase 4 — delivery honesty | DOCX preservation/fidelity tests and the approval-bound fixture output prove structural content validation, hashes, and receipts. | A real rendered-layout inspection remains required. |
| Phase 5 — local release readiness | Branch coverage, benchmark, adapters, isolated builds, and a current-source fresh wheel environment passed. The installed prior artifact also passes strict doctor. The local public release precheck passed with an explicit no-holdout disclosure; `--require-holdout` failed closed. | The current wheel is deliberately not installed without fresh explicit approval. Hosted CI for this checkout, the protected holdout, pilot, protected publication, and any stable promotion remain separate external gates. |

### Final synthetic measurements

Environment: CPython 3.14.6 on macOS 26.6.2 arm64; 20 repetitions; frozen
synthetic two-page DOCX, five evidence files, and 20 varied job descriptions.
The capture stage has a controlled 50 ms mock. No live public page or paid
provider was called.

| Stage | p50 seconds | p95 seconds | Target |
|---|---:|---:|---:|
| Warm prepare + review bundle | 0.1776 | 0.1854 | 2.0 |
| Time to first proposal | 0.1675 | 0.1754 | — |
| Ten roles + review bundles | 1.2512 | 1.2729 | 15.0 |
| Twenty roles + review bundles | 2.4641 | 2.4932 | 30.0 |
| Cold CLI prepare | 0.3411 | 0.4275 | 3.0 |
| Fresh mocked capture | 0.0593 | 0.0626 | 45 s deadline policy |
| Mocked capture cache hit | 0.0009 | 0.0013 | reported |
| Four distinct hosts, sequential mock capture | 0.2306 | 0.2396 | baseline |
| Four distinct hosts, four workers | 0.0598 | 0.0621 | paired ratio ≤ 0.50 |
| Strict-preserve DOCX apply | 0.0215 | 0.0219 | reported |
| DOCX parse + formatting audit | 0.0014 | 0.0015 | reported |
| Resume twenty unchanged roles | 0.1420 | 0.1433 | 2.0 |

Observed call counts: 20 fresh mocked captures and 20 capture-cache hits; 160
distinct-host mock captures (20 sequential-plus-parallel pairs); 20 initial
`tailor` captures; resume capture calls **0**; resume proposal calls **0**.
The initial and resumed 20-role outcomes were all `awaiting_approval`, with
**0** blocked roles. The deterministic provider made **14** calls for 14 unique
contexts, with **266** cache hits and **0** concurrent waits; its per-invocation
latency was p50 **0.000048 s**, p95 **0.000056 s**. The paired parallel/serial
distinct-host ratio was p50 **0.2605**, p95 **0.2787**, within the 0.50 target;
the focused same-host test verifies pacing remains enforced. The run passed all
measured budgets. These are synthetic local results, not live-site latency or
external-provider latency/cost.

### Synthetic document-validation evidence

`benchmarks/perf-fixtures/workflow-v2/resume.docx` was prepared into
`/tmp/ats-layout-render.9u6hOx`, explicitly approved against proposal digest
`6e34bcf32b4209c3c982eaa3b194dc0dc904bf05aa88009a4e5191a889a5d32f`, applied
in strict-preserve mode, and structurally validated as `valid`. The output
SHA-256 was `382720321a40bcfd8329a699e0ec5837210e4140c177f8a551d23aa1b3a4f044`.
macOS Quick Look generated readable first-page thumbnails for both source and
output; no gross first-page truncation was visible. Its exported fixture preview
(`Preview.html`) also retained the defined styles and explicit page-break marker.
`/opt/homebrew/bin/soffice` is only a broken launcher to an absent app, so
full-page rendering was not available. This remains a synthetic structural/
first-page check, not a real candidate document review or evidence that
rendered pagination is verified.

### Authorized source-CV intake (read-only)

On 2026-09-05 the user supplied a source PDF outside the repository for this
workflow. Its SHA-256 is
`cf416d911437c54bee134326d1c25e9a6f0a1073186696f1f091b225f9682aef`; it is a
two-page A4 PDF. Both the current checkout and the currently installed
`ats-agent` performed matching read-only format audits and reported `audited`,
873 extractable words, 99 lines, and `low` parser risk. Their sole
informational finding was that the conventional
heading `experience` was not detected; the supplied document instead uses
role-specific experience headings. This is source-intake evidence only, not a
proposal, generated-document validation, approval, or rendered-layout review.
No source bytes or candidate artifacts were changed.

No job description/job export, supplementary candidate-evidence file, or
fresh user-selected run directory has been supplied with this source PDF.
Accordingly, no `prepare`, approval, `apply`, or output `validate` command has
been run for a real candidate document.

### Verification actually run

- Focused network, recovery, cache, and workflow tests passed (64 tests), then
  the expanded focused set passed (63 tests).
- `ruff check src tests scripts`, `mypy src/ats_agent`, and `git diff --check`
  passed.
- The full branch-coverage sequence (326 tests, plus the existing benchmark and
  CLI journey in `.github/workflows/ci.yml`) passed at **90%** with the existing
  `--fail-under=90` gate unchanged (5,382 statements; 430 missed; 1,906
  branches; 283 partial branches).
- `python scripts/check_benchmark.py` passed all 270 frozen cases;
  `python scripts/validate_agent_adapters.py`, skill validation,
  benchmark-diversity validation, and reproducible adapter-bundle verification
  all passed.
- `python scripts/perf_batch_benchmark.py` passed with the measurements above.
- The focused same-host pacing test
  `tests.test_network_units.CaptureCacheTests.test_fetch_many_paces_same_host_workers`
  passed, proving three concurrent same-host workers begin their mocked fetches
  at least 25 ms apart under a 40 ms configured pacing interval.
- The direct development-venv build frontend lacks `setuptools.build_meta`, so
  its no-isolation build fails before packaging. The required `python -m build`
  was then run in an isolated, offline cached environment and passed; an
  additional `uv build --offline` passed. Neither operation changed the
  installed CLI.
- Fresh offline wheel environment: the final wheel installed with its ten
  required packages outside the checkout, imported from `site-packages`, passed
  strict doctor, and completed all eight bundled smoke cases. Both thin adapters
  were then pointed at that temporary executable and passed strict doctor. It
  used engine source SHA-256
  `ad172d138dc0493b3965f3ee05c941a19d3871559192fffe602cb417edc5cac3`.

Reproduce the principal local evidence with:

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=src .venv/bin/python scripts/check_benchmark.py
PYTHONPATH=src .venv/bin/python scripts/validate_agent_adapters.py
PYTHONPATH=src .venv/bin/python scripts/perf_batch_benchmark.py
PYTHONPATH=src .venv/bin/python -m unittest \
  tests.test_network_units.CaptureCacheTests.test_fetch_many_paces_same_host_workers -v
uv run --offline --isolated --no-project --with build \
  python -m build /Volumes/RAGHAV2/Projects/tailoring-ats-cvs \
  --outdir /tmp/ats-upgrade-python-build-dist
uv build --offline --out-dir /tmp/ats-upgrade-final-dist
```

For coverage, run the branch-enabled unit command above under `coverage`, then
append `scripts/check_benchmark.py` and the CLI journey at
`.github/workflows/ci.yml` before `coverage report --fail-under=90`; this is
the exact sequence used for the 90% result.

### Tested artifact and installed-runtime boundary

The final tested wheel is
`/tmp/ats-upgrade-uv-build-final.qpD8UC/tailoring_ats_cvs-1.0.0b4-py3-none-any.whl`
(SHA-256 `0eba4eb8e67ad60d75a27cbd873c29a4592fa19f397d0bf576f36828669d1172`).
The matching sdist is
`/tmp/ats-upgrade-uv-build-final.qpD8UC/tailoring_ats_cvs-1.0.0b4.tar.gz`
(SHA-256 `a0574a5147ffe939b98fb146091236203a87ca887bd25ab6f06c8b605b4756e1`).
Both `python -m build` in a temporary isolated offline environment and
`uv build --offline` completed before this wheel was installed in
`/tmp/ats-upgrade-final-wheel-env.60Fpio` for the clean-wheel checks.

`/Users/raghav/.local/bin/ats-agent` remains version `1.0.0b4` with the older
engine source SHA-256 `eb702a1e64c59e4db9291ea28e2caae1a02b83a37583516fe44692fdaf26886d`.
It was rechecked after the clean-wheel test on Python 3.14.5 and still passes
strict doctor, but it has **not** been upgraded to this tested artifact.
Replacing it requires a separate explicit approval.

### Overall status and exact blockers

**Overall stable-release/pilot acceptance is not complete.** Local code and
synthetic acceptance gates above are complete; the following require inputs,
consent, or external authority that were not available:

1. A user-supplied source CV now has the read-only intake evidence above. A
   selected job description/job export and fresh user-selected run directory
   are still required for a real prepare → explicit approval → apply → validate
   run; supplementary candidate evidence is needed only if it is intended to
   support changes. The source CV will remain untouched.
2. Manual rendered-layout inspection of that real DOCX in an appropriate
   document viewer; the current validation truthfully reports rendered layout
   as unverified.
3. Authorized public URLs for live capture timing and a selected configured
   optional provider (including permission for any provider cost) for live
   latency/call-cost measurements.
4. Hosted compatibility/security CI, protected private holdout, blinded human
   evaluation, and protected release/publication authority.
5. Explicit authorization to install the tested wheel into the existing
   `ats-agent` tool environment.

Do not mark the overall goal complete until those gates have evidence. The
local artifact, tests, performance record, and recovery/network requirements
are ready for that next authorized step.

## Live job research and final local recheck — 2026-09-05

This addendum supersedes only the preceding statements that no public role had
been captured or no job input was available. It records a user-authorized,
draft-only public role discovery run. It did not submit an application, write a
tracker, alter the source CV, create an approval, apply a proposal, or replace
the installed CLI.

### Live-capture regression found and repaired

The first live `research-jobs` run used five directly hosted public role URLs
and completed in **18.10 s**. It retained all five rows as `blocked_capture`,
made **0** deterministic-provider invocations, and exposed a real shared
defect: `capture_url` passed Scrapling a same-directory temporary filename
ending in `.tmp`; Scrapling accepts only `.txt`, `.md`, or `.html` output
paths. The failed run remains at
`/Users/raghav/Documents/Dev_Projects/ai-job-search/reports/raghav-live-roles-2026-09-05/`
as failure evidence.

The minimal root-cause repair is in `capture_url`, which now preserves a
Scrapling-supported destination suffix or uses `.txt` for an internal/cache
destination such as `.tmp`. This covers direct capture, cached capture,
research-jobs, deep-dive, and liveness callers without weakening the
HTTPS/DNS/proxy/deadline safeguards. The new regression test
`CaptureCacheTests.test_capture_uses_a_scrapling_supported_temporary_suffix`
asserts the internal destination passed to the scraper is `.txt` even when the
requested final destination is `.tmp`; the 21-test capture suite passed.

### Authorized live role discovery and ATS research

The input list is
`/Users/raghav/Documents/Dev_Projects/ai-job-search/reports/raghav-live-roles-2026-09-05-inputs.json`.
The repaired current-checkout command was:

```sh
PYTHONPATH=src .venv/bin/python -m ats_agent.cli research-jobs \
  /Users/raghav/Downloads/Raghav_Badhwar_.pdf \
  /Users/raghav/Documents/Dev_Projects/ai-job-search/reports/raghav-live-roles-2026-09-05-inputs.json \
  --out /Users/raghav/Documents/Dev_Projects/ai-job-search/reports/raghav-live-roles-2026-09-05-retry1 \
  --candidate-id raghav-badhwar
```

It completed in **10.84 s** (`user` 3.40 s, `sys` 0.77 s), with five visible
draft proposals, zero resumed rows, and the engine-reported deterministic
provider counters: **6 invocations, 0 cache hits, 0 coalesced waits, 6 unique
contexts**. Those are local deterministic-provider counters, not paid-model
calls or model-cost measurements. The run captured all five job descriptions;
the capture manifests record nine source attempts: eight successful cache
misses (two official job pages, three third-party/ATS job pages, and three
official company-context pages) and one visible failed Sprinto company-context
capture due to insufficient extractable text. The associated job-page evidence
was retained rather than silently upgrading its provenance.

| Role | Result preserved by `ats-agent` | Important boundary |
|---|---|---|
| Peakflo — Product Manager Intern | `proposal_draft` with `eligibility_warning` | YC-hosted job page captured as third-party provenance; one direct and six transferable requirement matches; remote/availability terms remain unknown from the source CV. |
| Outmarket — Product Intern | `proposal_draft` with `eligibility_warning` | Employer-owned job and company pages captured; workflow-automation evidence is direct; remote and user-research/feedback gaps remain visible. |
| Restat — Market/Product Analyst Intern | `proposal_draft` with `eligibility_warning` | Freshteam job page remains third-party/ATS provenance; the paid remote-friendly wording is an eligibility warning, not a CV claim. |
| Chiblu — Business Development Intern (Seller Growth) | `proposal_draft` | Employer-owned job and company pages captured; no hard-gate warning was synthesized, but the page's May posting date must still be checked before applying. |
| Sprinto — Finance Intern | `proposal_draft` with `eligibility_warning` | Lever page captured as third-party/ATS provenance; the official company-context capture failed visibly. Finance/accounting, credential, and audit gaps were not inserted into the CV. |

All five results are retained in the final manifest at
`/Users/raghav/Documents/Dev_Projects/ai-job-search/reports/raghav-live-roles-2026-09-05-retry1/manifest.json`.
They are role-research artifacts only. No proposal is approved and their
proposal digests remain the required approval boundary for any future CV
tailoring.

The exact same command and output directory were then resumed unchanged. That
live recovery check completed in **2.06 s** (`user` 0.25 s, `sys` 0.06 s),
reported **5 resumed jobs**, and reported **0** provider invocations, cache
hits, coalesced waits, and unique contexts. All five original draft/warning
statuses remained visible. This is live-run resume evidence; it is distinct
from the synthetic 20-role resume measurement below and does not claim an
unavailable external-provider cost measurement.

### Fresh reproducible synthetic measurements

`PYTHONPATH=src .venv/bin/python scripts/perf_batch_benchmark.py` passed on
CPython 3.14.6/macOS 26.6.2 arm64 against the frozen 20-role fixture, with 20
repetitions. Its JSON report is `/tmp/ats-perf.zpDJI5/report.json`; this is
offline synthetic evidence, not live-site or paid-provider latency.

| Stage | p50 seconds | p95 seconds | Target |
|---|---:|---:|---:|
| Warm prepare + review bundle | 0.3056 | 0.3241 | 2.0 |
| Time to first proposal | 0.2883 | 0.3005 | reported |
| Ten roles + review bundles | 2.1448 | 2.2990 | 15.0 |
| Twenty roles + review bundles | 4.2214 | 4.8908 | 30.0 |
| Cold CLI prepare | 0.6873 | 0.7429 | 3.0 |
| Fresh mocked capture | 0.0623 | 0.0647 | 45 s deadline policy |
| Mocked capture cache hit | 0.0011 | 0.0016 | reported |
| Strict-preserve DOCX apply | 0.0364 | 0.0375 | reported |
| DOCX parse + formatting audit | 0.0024 | 0.0025 | reported |
| Resume twenty unchanged roles | 0.2470 | 0.2578 | 2.0 |

The same run recorded 20 fresh mocked captures, 20 capture-cache hits, 160
distinct-host capture calls, 20 initial `tailor` captures, **0** resumed
captures, and **0** resumed proposal calls. Its deterministic provider made
14 invocations for 14 unique contexts with 266 cache hits and 0 coalesced
waits; p50/p95 provider work was 0.000083/0.000097 s. Parallel capture at four
distinct hosts had a p95 parallel-to-sequential ratio of 0.2819, below the
0.50 target. Initial and resumed batches each retained 20
`awaiting_approval` outcomes with zero blocked rows. The 130.18-second total
wall time includes all 20 repetitions and fixture operations, not a single
candidate request.

### Final local verification after the repair

- The focused 21-test capture suite passed. The full suite passed: **327 tests
  in 10.050 s**.
- `ruff check src tests scripts` and `mypy src/ats_agent` passed.
- The exact CI-style branch-coverage sequence (unit suite plus the existing
  benchmark and CLI journey from `.github/workflows/ci.yml`) passed at
  **90%**, preserving `--fail-under=90`: 5,385 statements, 430 missed, 1,908
  branches, and 283 partial branches. The bare unit-only coverage command is
  not represented as a passing 90% gate; it is 85% until the existing
  benchmark/CLI coverage steps are appended.
- `scripts/check_benchmark.py` passed all 270 frozen cases and
  `scripts/validate_agent_adapters.py` passed. The existing release security
  commands `python -m bandit -r src/ats_agent -q -ll` and
  `python -m pip_audit --local` passed; the latter reported no known
  vulnerabilities.
- `scripts/check_release_tree.py`, `scripts/validate_skill.py`, and
  `scripts/validate_benchmark_diversity.py` passed. Fresh Codex-skill and
  Claude-plugin bundles built in `/tmp/ats-agent-adapters-recheck.mZCNXw` and
  passed `scripts/verify_agent_bundle.py`; source/test and plan whitespace
  checks passed without altering unrelated working-tree changes.
- A fresh build completed with
  `PYTHONPATH=src .venv/bin/python -m build --outdir /tmp/ats-wheel-build.rqA1zV`.
  The only build output was setuptools's forward-looking license-metadata
  deprecation warning; it was not treated as a successful or failed security
  claim.
- A newly created isolated environment at
  `/tmp/ats-wheel-verify.CBc9W0/venv` installed the rebuilt wheel with its
  `documents` extra, from outside the checkout. Its CLI exposed the expected
  commands, reported the rebuilt engine SHA from `site-packages`, ran all eight
  bundled smoke cases with schema version 3, and performed a read-only format
  audit of the supplied source PDF: `audited`, 873 words, 99 lines, low risk,
  and only informational finding F5. It did not write the source document.

The rebuilt source runtime is SHA-256
`fb4fc67af048e55eb11049bb7e623a59b8358276eaccfdf615eb050b3233d52e`. The
new tested wheel is
`/tmp/ats-wheel-build.rqA1zV/tailoring_ats_cvs-1.0.0b4-py3-none-any.whl`
(SHA-256 `133aff94326dd6c790f6f34315850a0db50175ea8a0774ad1a355fa7a1de9b6c)
and its matching sdist is
`/tmp/ats-wheel-build.rqA1zV/tailoring_ats_cvs-1.0.0b4.tar.gz`
(SHA-256 `fa78018c87068dd61395395d2ae5a80c7e861409cdaf76212296a70208ea8c07`).
At this pre-install verification point, the installed user CLI still reported
the older engine SHA-256
`eb702a1e64c59e4db9291ea28e2caae1a02b83a37583516fe44692fdaf26886d`. The
later user-authorized replacement is recorded below.

### Current exact blockers

**Overall stable-release/pilot acceptance remains incomplete.** The remaining
requirements are not hidden by the successful local or live-research work:

1. A real tailored-document run cannot yet be approved from the retained
   drafts. The leading BJAK proposal
   (`57f2a3e0e6c1e96c4c3d2d6adc4e14d6df01295d2f4389a7d51abe840bcc3d78`)
   has unsupported `C1`/`C2` candidates and an unknown full-time/work-mode
   hard gate `R1`. The source CV does not itself evidence availability or work
   authorization. The user must select a role and provide that candidate fact;
   then a fresh proposal can be reviewed and the user can explicitly select
   only its supported digest-bound change IDs and variants. No apply or output
   validation may occur before that approval.
2. A real generated DOCX still needs manual rendered-layout inspection; the
   honest validator cannot claim that rendered pagination is verified.
3. Live capture timing is now recorded above, but optional external-provider
   latency and cost remain unmeasured because no paid provider was configured
   or authorized.
4. Hosted compatibility/security CI, protected private holdout, blinded human
   evaluation, and protected release/publication authority remain external
   gates.
5. The installed CLI is still the previous verified `fb4fc67…` engine. The
   current tested wheel below contains the concurrent candidate-cache repair
   at `d95e5c65…`; installing it requires a new explicit approval even though
   both artifacts report version `1.0.0b4`.
Do not mark the overall goal complete until these gates have their own
evidence. The local implementation and live draft-research evidence above are
ready for the next authorized step.

## Scope correction: full-time jobs, not internships — 2026-09-05

The candidate corrected the live-discovery scope: the requested recommendations
are **full-time jobs**, not internships. The earlier five internship records
remain valid only as live-capture/recovery implementation evidence; they are
not presented as the requested job shortlist. No candidate profile, source CV,
tracker, approval, application, or installed CLI was changed to make this
correction.

The existing AI Job Search configuration remains explicitly internship and
remote-search oriented, so it was not silently rewritten into a full-time
availability claim. A bounded public LinkedIn lead scan made three 14-day,
six-result queries (`associate product manager`, `product operations
associate`, and `strategy analyst`). Its location/remote labels were treated
only as leads after returning roles outside the requested geography. Employer
career-page research, not the portal filter, determines the list below.

### Full-time discovery and evidence-preserving ATS research

The five-role retained batch is
`/Users/raghav/Documents/Dev_Projects/ai-job-search/reports/raghav-fulltime-roles-2026-09-05-inputs.json`.
It deliberately retains location/work-right uncertainty rather than filtering
roles out. The reproducible command was:

```sh
PYTHONPATH=src .venv/bin/python -m ats_agent.cli research-jobs \
  /Users/raghav/Downloads/Raghav_Badhwar_.pdf \
  /Users/raghav/Documents/Dev_Projects/ai-job-search/reports/raghav-fulltime-roles-2026-09-05-inputs.json \
  --out /Users/raghav/Documents/Dev_Projects/ai-job-search/reports/raghav-fulltime-roles-2026-09-05 \
  --candidate-id raghav
```

It completed in **19.230 s** wall time with five retained
`proposal_draft`/`eligibility_warning` rows, zero resumed rows, and **4**
deterministic-provider invocations (**0** cache hits, **0** coalesced waits,
**4** unique contexts). Those are local deterministic-provider counters, not
paid-model calls. Each direct Ashby capture visibly failed as empty or
insufficient; the batch therefore used the separately recorded public-research
fallback text for all five rows. Every such description is marked
`aggregator_fallback` in its capture manifest, not `official_job_page` or
silently upgraded provenance.

| Full-time role retained | ATS result | Decision-relevant boundary |
|---|---|---|
| BJAK — Founder's Office, Finance Super App (India) | `proposal_draft` with `eligibility_warning` | The public job page says full-time, remote India and India-based candidates; the source CV does not establish full-time availability. Finance/strategy/startup fit is promising, but the captured evidence is fallback-only. |
| Panoptyc — Founder's Office: Growth/Ops | `proposal_draft` with `eligibility_warning` | Public research says remote across India and other markets but requires four hours daily overlap with US Pacific Time; full-time schedule feasibility remains candidate-confirmed. |
| Human Archive — Founder's Office | `proposal_draft` with `eligibility_warning` | Early-career global field-operations/partnerships fit is adjacent, but the page's work location and travel terms are not confirmed and its one-to-five-years/exceptional-dropout framing is a real qualification question. |
| Vetcove — Product Operations Associate | `proposal_draft` with `eligibility_warning` | The role is labelled remote and asks for one-to-four years of relevant operations experience; India payroll/work-location permission is unverified. |
| EvenUp — Product Operations Associate | `proposal_draft` with `eligibility_warning` | The role asks for two-to-three years in Product/AI Ops or technical program management and is labelled Remote-US with a Canada compensation range; it is not evidence that work can be performed from India. |

An additional direct full-time role was researched separately because it used a
server-readable Lever page:

```sh
PYTHONPATH=src .venv/bin/python -m ats_agent.cli research-jobs \
  /Users/raghav/Downloads/Raghav_Badhwar_.pdf \
  /Users/raghav/Documents/Dev_Projects/ai-job-search/reports/raghav-fulltime-weekday-2026-09-05-inputs.json \
  --out /Users/raghav/Documents/Dev_Projects/ai-job-search/reports/raghav-fulltime-weekday-2026-09-05 \
  --candidate-id raghav
```

The Weekday **Founder's Office (Growth & GTM)** run completed in **1.696 s**
with one `proposal_draft`/`eligibility_warning`, **2** deterministic-provider
invocations, and no cache hits or waits. Scrapling captured the career page
successfully, but the source is still correctly labelled
`third_party_job_page` because it is a Lever-hosted ATS page. Its own text says
both `On-site` and `Location: Remote`; this conflict is an explicit hard-gate
warning, not an assumed remote role. The page asks for revenue ownership,
inside-sales/outbound execution, and self-service scripting/API work; the
candidate's documented commercial execution and automation background are
relevant, while quota-carrying sales and a confirmed work arrangement remain
gaps.

All six outputs are draft-only review bundles with digest-bound proposals:

- `/Users/raghav/Documents/Dev_Projects/ai-job-search/reports/raghav-fulltime-roles-2026-09-05/manifest.json`
- `/Users/raghav/Documents/Dev_Projects/ai-job-search/reports/raghav-fulltime-weekday-2026-09-05/manifest.json`

### Additional current blockers for a real full-time application

1. The supplied CV supports finance/strategy, AI/product/agent operations,
   partnerships, and commercial execution; it does **not** prove a full-time
   work schedule while the degree is in progress, cross-border payroll, or
   location-specific work permission. Those are candidate inputs, not CV
   rewrites.
2. The five Ashby-hosted roles have usable, auditable fallback research but not
   successful direct capture. Their opening status, location, and eligibility
   must be rechecked on the employer page immediately before any application.
3. Any tailoring still requires the user's explicit choice of one proposal plus
   its exact digest-bound change IDs and variants. Apply and document validation
   remain prohibited until that approval; no source CV may be overwritten.

### User-authorized installed CLI replacement

After the tested artifact and its SHA-256 were presented, the user explicitly
authorized updating the installed CLI. The exact wheel was re-hashed before
installation and matched the tested value:

`133aff94326dd6c790f6f34315850a0db50175ea8a0774ad1a355fa7a1de9b6c`.

The first uv-tool replacement attempt used `--offline --no-index` and stopped
without modifying the existing environment because its resolver could not see
`defusedxml` in the supplied package location. The old executable still passed
strict doctor immediately afterward. The safe, minimal successful replacement
therefore kept the already-installed document dependencies and reinstalled only
the verified wheel, offline and without resolving or fetching dependencies:

```sh
uv pip install --offline --no-deps --reinstall \
  --python /Users/raghav/.local/share/uv/tools/tailoring-ats-cvs/bin/python \
  /tmp/ats-wheel-build.rqA1zV/tailoring_ats_cvs-1.0.0b4-py3-none-any.whl
```

The managed executable remains `/Users/raghav/.local/bin/ats-agent` at version
`1.0.0b4`, now with installed engine SHA-256
`fb4fc67af048e55eb11049bb7e623a59b8358276eaccfdf615eb050b3233d52e`.
`ats-agent doctor --strict` passed after installation, including its proposal,
digest-bound approval, transactional apply, and output-validation self-test;
both `pypdf` and `python_docx` remain available. `ats-agent format` then made a
read-only audit of the supplied PDF (873 words, 99 lines, low risk, only F5
informational) and the source PDF SHA-256 remained
`cf416d911437c54bee134326d1c25e9a6f0a1073186696f1f091b225f9682aef`.
No candidate document was replaced or generated by this installation.

### Current-state release audit — 2026-09-06

The installed CLI was rechecked through the skill's non-mutating readiness
check and strict doctor. It remains the verified `1.0.0b4` engine at
`fb4fc67af048e55eb11049bb7e623a59b8358276eaccfdf615eb050b3233d52e`, with
PDF/DOCX dependencies and the digest-bound approval, transactional-apply, and
output-validation self-test all passing.

The reproducible local public-release checks were:

```sh
python .agents/skills/tailor-cv/scripts/ensure_cli.py --check
/Users/raghav/.local/bin/ats-agent doctor --strict
PYTHONPATH=src .venv/bin/python scripts/release_check.py
PYTHONPATH=src .venv/bin/python scripts/release_check.py --require-holdout
```

The first three commands passed. The last command failed closed with
`stable releases must pass the protected holdout`, as required, because no
private holdout was supplied. The local environment has no
`PRIVATE_HOLDOUT_B64`; the authenticated read-only GitHub query returned no
release-environment secret names. The `release` environment exists but has no
protection rules. These observations do not disclose or replace a holdout.

Read-only GitHub inspection also found that this checkout is
`feat/capability-maximization-safety` at
`d62d01c63c9651f38727d993ea231cac620690bc`; that feature branch is absent
from `origin`, whose `main` is
`f17802df072895d115f1374f7190eacdcdcc54c5`. GitHub returned no workflow runs
for `d62d01c63c9651f38727d993ea231cac620690bc`. Consequently, the previously
successful hosted CI/security runs are evidence only for the older `main`
commit, not for this dirty, unpushed checkout. No push, tag, publication,
secret, or release-environment change was performed.

### Completion-audit repair: concurrent candidate reuse — 2026-09-06

The final local audit reproduced one remaining Phase-3 defect instead of
treating prior cache tests as proof: four concurrent `research-jobs` workers
could all miss the ordinary per-run candidate cache before any worker stored
the parsed source CV, evidence, and ledger. A controlled four-role probe
therefore read the source CV **four** times. This was not a provider issue:
the same probe already reported one provider invocation and three provider
cache hits.

`build_proposal` now uses one standard-library `threading.Lock`, retained only
inside the existing caller-owned per-run candidate cache, around candidate
load/ledger initialization and stale-entry replacement. It keeps the existing
candidate ID plus content-hash cache key, rebuilds when input hashes change,
and leaves all artifact/hash checks, evidence provenance, approval binding,
and apply-time validation unchanged. No global cache, service, dependency, or
adapter-side CV logic was introduced. The focused regression
`JobResearchTests.test_concurrent_jobs_load_candidate_inputs_once` synchronizes
four workers at capture time and proves exactly one candidate load. The direct
post-repair probe reported:

```json
{
  "status": "draft",
  "job_count": 4,
  "resume_loads_during_four_concurrent_jobs": 1,
  "provider_calls": {
    "provider_invocations": 1,
    "cache_hits": 3,
    "coalesced_waits": 0,
    "unique_contexts": 1
  }
}
```

This closes the remaining local candidate-input reuse requirement; it does
not make a candidate fact or a job description into evidence, and it does not
allow a stale proposal or approval to be reused.

### Current-source verification and performance record — 2026-09-06

All entries in this section apply to the current source engine SHA-256
`d95e5c650dd79f6b1a90bfd8264d4b9886f5862b744e78eab6935f84cd976185`.
They supersede earlier local count/timing entries when values differ. The
performance fixture is reproducible, offline, and synthetic: a frozen
two-page DOCX, five evidence files, twenty varied local job descriptions, a
mocked 50 ms capture, and a deterministic provider. It contains no candidate
text, live public fetch, paid model call, or claim about live latency/cost.

| Measured stage | p50 seconds | p95 seconds | Calls / result |
|---|---:|---:|---|
| Warm prepare plus review bundle | 0.1870 | 0.2344 | local fixture |
| Time to first proposal | 0.1764 | 0.2231 | local fixture |
| Ten roles plus reviews | 1.3307 | 1.5340 | within 15 s target |
| Twenty roles plus reviews | 2.6169 | 2.9776 | within 30 s target |
| Cold CLI prepare | 0.3631 | 0.4438 | within 3 s target |
| Fresh mocked capture | 0.0554 | 0.0574 | 20 fresh captures |
| Mocked capture-cache hit | 0.0003 | 0.0003 | 20 cache hits |
| Review write | 0.1979 | 0.2307 | reported separately |
| Strict-preserve apply | 0.0252 | 0.0436 | explicit synthetic approval |
| Parse/audit validation | 0.0016 | 0.0024 | structural/content audit only |
| Resume twenty unchanged roles | 0.1530 | 0.1770 | zero resume captures and proposal calls |

The controlled distinct-host parallel/serial capture ratio was p50 **0.2544**
and p95 **0.2633**, below the 0.50 target. The deterministic provider made
**14** unique invocations, **266** cache hits, and **0** coalesced waits; its
per-invocation p50/p95 was **0.000056 s / 0.000067 s**. Mock captures were
20 fresh, 20 cache-hit, and 160 distinct-host operations. These figures are
call-count evidence for local reuse and scheduling, not external-provider or
live-web measurements.

The following checks were rerun after the candidate-cache repair:

- focused concurrent-cache, interrupted-recovery, and provider-coalescing
  tests: **3 passed**;
- complete suite: **328 passed in 6.852 s**;
- Ruff passed with `.venv/bin/ruff check src tests scripts`;
- typing passed with
  `PYTHONPATH=src .venv/bin/python -m mypy src/ats_agent` (35 source files);
- the exact CI-style branch-coverage journey, including benchmark and CLI
  workflow steps, passed unchanged at **90%**: 5,397 statements, 430 missed,
  1,912 branches, and 283 partial branches;
- the 270-case benchmark, adapter validation, release-tree, skill,
  benchmark-diversity, bundle verification, compile check, Bandit, and local
  pip-audit all passed; pip-audit reported no known vulnerabilities;
- `scripts/release_check.py` passed its public local precheck with the explicit
  no-holdout disclosure, while `--require-holdout` failed closed as recorded
  above.

Reproduce the local code and performance evidence without installing the
user-facing executable:

```sh
PYTHONPATH=src .venv/bin/python -m unittest \
  tests.test_job_research.JobResearchTests.test_concurrent_jobs_load_candidate_inputs_once -v
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
.venv/bin/ruff check src tests scripts
PYTHONPATH=src .venv/bin/python -m mypy src/ats_agent
PYTHONPATH=src .venv/bin/python scripts/check_benchmark.py
PYTHONPATH=src .venv/bin/python scripts/validate_agent_adapters.py
PYTHONPATH=src .venv/bin/python scripts/perf_batch_benchmark.py
PYTHONPATH=src .venv/bin/python scripts/release_check.py
PYTHONPATH=src .venv/bin/python scripts/release_check.py --require-holdout
```

For the coverage result, run the exact `Test, benchmark, and CLI workflow with
branch coverage` command block in `.github/workflows/ci.yml`, using
`python -m coverage` through the same environment above; the unit-only command
is deliberately not substituted for that gate.

### Tested artifact, isolated installation check, and remaining boundary

The current source built successfully without changing the installed CLI:

| Artifact | SHA-256 |
|---|---|
| `/tmp/ats-candidate-cache-wheel.RXh9lQ/tailoring_ats_cvs-1.0.0b4-py3-none-any.whl` | `dc7b80602bf4c3ce0f39ae00d66652078497422e39623d3a34b1b0094f28fbc5` |
| `/tmp/ats-candidate-cache-wheel.RXh9lQ/tailoring_ats_cvs-1.0.0b4.tar.gz` | `cbf77207bdfd598228a1724ca2b7c6dfaa87146b8e08367810fa7d591e0bcb0b` |

The wheel was installed offline with its `documents` extra into the fresh
temporary environment `/tmp/ats-candidate-wheel-env.QcdNxn/venv`, outside the
checkout. Its `ats-agent --help`, `doctor --strict`, schema-3 smoke benchmark,
read-only supplied-PDF format audit, direct four-worker candidate-cache probe,
and both thin adapter strict-doctor paths all passed from `site-packages`. The
wheel-only probe again loaded the candidate exactly once. Fresh adapter bundles
also passed verification in `/tmp/ats-candidate-cache-adapters.BkLBFC`:
Codex-skill ZIP SHA-256
`361d3f0680bdcf9f7fa7d292e361eca4d6429eef8d52d2bb412e6ffdc4c6edb7` and
Claude ZIP SHA-256
`a1ce9618dda48a6853a129a9e914fb8936570a64da63fbd517bb7b710228b03b`.

The installed executable at `/Users/raghav/.local/bin/ats-agent` deliberately
remains the older, separately verified `1.0.0b4` engine SHA-256
`fb4fc67af048e55eb11049bb7e623a59b8358276eaccfdf615eb050b3233d52e`.
Both report the same version, so version text is not treated as runtime
identity. Replacing it with the newly tested wheel is a separate, reversible
user-facing change and requires a fresh explicit approval before execution.

The overall goal is therefore still open only for real/external gates: the
candidate must select a full-time role and provide the missing factual
availability/location/work-authorisation information; then a fresh proposal
must receive explicit digest-bound selection before apply. A real output needs
manual rendered-layout inspection. Optional live-provider latency/cost is
unavailable without a configured/authorized provider. Hosted CI for this
current unpushed checkout, protected private holdout, blinded human evaluation,
and protected release/publication remain independent external evidence and
authorization gates. None has been fabricated or marked complete.

### Final superseding local audit: network, recovery, and release evidence — 2026-09-06

This addendum supersedes earlier local status and timing values. It applies to
the current source engine SHA-256
`adf90d2a86e29f765af69107fa3375751f7edf971db7873dcd170c1a01944ca3`.
The local `.venv` launcher pointed at a deleted temporary interpreter, so
all current source checks used the reproducible isolated environment
`uv run --isolated --extra dev --extra documents`. That creates an ephemeral
verification environment only; it did not install, replace, or otherwise alter
`/Users/raghav/.local/bin/ats-agent`.

| Requirement | Current local result | Evidence and honest boundary |
|---|---|---|
| Direct public-capture peer binding | Complete locally and exercised live | `_scrape_once` obtains public DNS answers once, serializes them into a cURL `RESOLVE` entry, and runs the existing Scrapling `0.4.12` Python runtime with that entry. Scrapling's `Fetcher` does not accept per-request `curl_options`, so the runner uses the same runtime's supported `curl_cffi.Session(curl_options=...)` construction boundary, `allow_redirects=False`, `verify=True`, no proxy or impersonation, then Scrapling's `ResponseFactory` and `Convertor` for output. `CaptureCacheTests.test_capture_pins_validated_dns_answers_for_the_scrapling_runtime`, `test_pinned_resolve_entry_keeps_ipv4_and_ipv6_answers`, and the console-script fail-closed regression cover the contract. The installed runtime was checked for `CurlOpt.RESOLVE`, `Session`, and Scrapling conversion support. A read-only IANA reserved-domains probe then completed through the current runner as `scrapling_public_https`, producing 2,660 bytes at SHA-256 `532550a9c1d637396e5b6164d9593f6ee5cdb50dfffcaad0fe400178f57403ae` in `/tmp/ats-public-capture-probe.1Sss5y`. It is generic public-capture evidence, not a job draft or candidate artifact. The parent cannot inspect the child socket, and the 4 MiB direct-capture limit is checked after raw output is written and before decode/publish. |
| Capture environment and output hardening | Complete locally | Capture strips proxy, TLS trust-store, and Python path/user-site overrides; it forces `PYTHONNOUSERSITE=1`. Boards retain numeric-peer TLS transport, a 45-second deadline, and a 4 MiB streaming response cap. Direct capture rejects a final temporary file above 4 MiB before it is decoded or atomically published. The source still fails closed for private/malformed DNS answers and does not silently follow redirects. |
| Interrupted `research-jobs` recovery | Complete locally | Schema-2 manifests checkpoint atomically. Valid completed roles resume only after proposal digest, capture-hash, and review-artifact checks; corrupt draft artifacts remain visible `blocked_recovery` rows and are never rebuilt silently. Existing interruption and corrupt-recovery regressions pass. |
| Bounded research scheduling | Complete locally | Retained blocked/imported/expired rows are recorded synchronously. Only jobs that require capture are submitted to the existing four-worker pool, so retained historical exports cannot create unbounded queued futures. `JobResearchTests.test_non_capture_rows_do_not_consume_worker_futures` proves one normal, one expired, and one blocked row produce exactly one capture and one submitted future. |
| Provider reuse and manifest safety | Complete locally | The existing `RewriteCache` remains the sole provider deduplication mechanism; it reports invocation, hit, coalesced-wait, and unique-context counts. Shared `rewrite_provider_identity` records a deterministic configuration SHA-256 rather than raw provider instance state, so provider secrets are not copied into orchestration or research manifests. The default deterministic-provider identity and schema-2 resume compatibility are retained. |
| Candidate/source-document protection | Preserved | The supplied PDF SHA-256 was `cf416d911437c54bee134326d1c25e9a6f0a1073186696f1f091b225f9682aef` before and after source and wheel audits. Current-source format audit was `audited`, 873 extractable words, 99 lines, low risk, with only informational F5 (`experience` heading not detected). No proposal was approved, no candidate output was generated, and no source CV was written. |

#### Measured current-source performance

The following 20-repetition run is synthetic and offline: frozen two-page
DOCX, five synthetic evidence files, 20 varied local job descriptions, a
mocked 50 ms capture, and the deterministic provider. It is useful for
regression budgets and call-count assertions only; it is not a live-web or
paid-provider latency/cost claim.

| Stage | p50 seconds | p95 seconds | Result / calls |
|---|---:|---:|---|
| Warm prepare plus review | 0.2386 | 0.8810 | within 2 s budget |
| Time to first proposal | 0.2249 | 0.8453 | synthetic fixture |
| Ten roles plus review | 1.6649 | 6.6488 | within 15 s budget |
| Twenty roles plus review | 3.3785 | 12.1410 | within 30 s budget |
| Cold CLI prepare | 0.5086 | 1.8900 | within 3 s budget |
| Fresh mocked capture | 0.0567 | 0.0672 | 20 fresh calls |
| Mocked capture-cache hit | 0.0004 | 0.0016 | 20 cache hits |
| Review writing | 0.2641 | 0.9311 | included separately for visibility |
| Strict-preserve apply | 0.0297 | 0.0599 | explicit synthetic approval only |
| Parse/audit validation | 0.0019 | 0.0038 | structural/content audit only |
| Resume twenty unchanged roles | 0.1610 | 0.2356 | 0 captures; 0 proposal calls |

The paired four-worker distinct-host capture ratio was p50 **0.2575** and p95
**0.2739**, below the 0.50 target. Deterministic-provider counts were **14**
invocations, **266** cache hits, **0** coalesced waits, and **14** unique
contexts; per-invocation p50/p95 was **0.000055 s / 0.000073 s**. The run
observed 20 initial tailor captures, 160 distinct-host mock capture operations,
20 resumed `awaiting_approval` outcomes, and zero blocked outcomes. Its frozen
fixture hashes are emitted by `scripts/perf_batch_benchmark.py` and remain the
reproducibility binding.

#### Verification actually executed

- Full branch-coverage unit, benchmark, and CLI workflow: **334 tests passed
  in 13.444 s**; **5,439** statements, **431** missed, **1,926** branches,
  **285** partial branches, **90%** total (the unchanged threshold passed).
  The CI workflow's `propose → review → explicit approve → apply → validate →
  tailor → explicit approve → tailor` coverage path and smoke benchmark were
  executed against the same coverage data.
- Ruff, Mypy (35 source files), `scripts/check_benchmark.py` (270 cases),
  release-tree integrity, frozen-skill validation, benchmark-diversity
  validation, adapter validation, agent-bundle verification, `compileall`,
  Bandit (`-ll`), and local `pip-audit` all passed. `pip-audit` reported no
  known vulnerabilities.
- `scripts/release_check.py` passed its public prerelease check with an
  explicit no-holdout disclosure. `scripts/release_check.py --require-holdout`
  exited **1** with `stable releases must pass the protected holdout`; this is
  the required fail-closed result, not a completed private-holdout gate.
- Current-source and user-installed `doctor --strict` both passed. The user
  CLI remains `1.0.0b4` on engine SHA
  `fb4fc67af048e55eb11049bb7e623a59b8358276eaccfdf615eb050b3233d52e`, not
  the current source engine.
- `git diff --check` passed. The pre-existing dirty worktree was preserved.

#### Current tested artifact; not installed

| Artifact | SHA-256 |
|---|---|
| `/tmp/ats-network-recovery-wheel.hrgma7/tailoring_ats_cvs-1.0.0b4-py3-none-any.whl` | `cdc785140aa858d4c49237a07ba2f4d42aa3a1ea9b9317c9eab2561bc0d8ede1` |
| `/tmp/ats-network-recovery-wheel.hrgma7/tailoring_ats_cvs-1.0.0b4.tar.gz` | `dc382550d81b604336e16692f408040c90ca4727aa659f0344095363ee10440d` |

`python -m build --outdir` created the artifact in a fresh temporary directory
without overwriting the ignored historical `dist/` files. Setuptools emitted
only its forward-looking license-metadata deprecation warning. A fresh external
environment at `/tmp/ats-network-recovery-wheel-env.h2F9qd` installed the wheel
with its `documents` extra and, from `/tmp`, passed `ats-agent --help`,
`doctor --strict`, the eight-case schema-3 smoke benchmark, and the read-only
source-PDF format audit. Its engine path was in `site-packages` and its source
SHA matched `adf90d2a…`; it did not import the checkout. The fresh adapter
bundles at `/tmp/ats-current-adapters.fRTZVA` also verified, with Codex-skill
ZIP SHA `361d3f0680bdcf9f7fa7d292e361eca4d6429eef8d52d2bb412e6ffdc4c6edb7`
and Claude-plugin ZIP SHA
`a1ce9618dda48a6853a129a9e914fb8936570a64da63fbd517bb7b710228b03b`.
Both thin adapters then passed `doctor --strict` against that wheel from
`/tmp`, using the supported `ATS_AGENT_EXECUTABLE_OVERRIDE` only for this
isolated verification. Both reported the same `adf90d2a…` site-packages
engine; the override did not write the managed install manifest or alter the
user CLI.

#### Reproduce the current local evidence

```sh
# Does not touch the managed user CLI.
uv run --isolated --extra dev --extra documents -- ruff check src tests scripts
uv run --isolated --extra dev --extra documents -- mypy src/ats_agent
uv run --isolated --extra dev --extra documents -- python -m unittest discover -s tests -v
uv run --isolated --extra dev --extra documents -- python scripts/check_benchmark.py
uv run --isolated --extra dev --extra documents -- python scripts/validate_agent_adapters.py
uv run --isolated --extra dev --extra documents -- python scripts/perf_batch_benchmark.py
uv run --isolated --extra dev --extra documents -- bandit -r src/ats_agent -q -ll
uv run --isolated --extra dev --extra documents -- pip-audit --local
uv run --isolated --extra dev --extra documents -- python -m compileall -q src scripts tests
uv run --isolated --extra dev --extra documents -- python scripts/release_check.py
uv run --isolated --extra dev --extra documents -- python scripts/release_check.py --require-holdout
```

For branch coverage, run the exact `Test, benchmark, and CLI workflow with
branch coverage` command block in `.github/workflows/ci.yml` under the same
isolated environment and a single `COVERAGE_FILE`; do not substitute the
unit-only command for that approval/apply/validation coverage path. To build
without replacing the managed executable, use
`uv run --isolated --extra dev --extra documents -- python -m build --outdir
"$(mktemp -d /tmp/ats-wheel.XXXXXX)"`, then install that wheel only into a
fresh temporary virtual environment for its external smoke check.

#### Exact remaining blockers; overall goal remains open

1. A real full-time role must be selected and the missing factual availability,
   location, and work-authorisation information supplied. The retained BJAK
   draft digest `57f2a3e0e6c1e96c4c3d2d6adc4e14d6df01295d2f4389a7d51abe840bcc3d78`
   still contains unsupported candidates and an unknown work-mode/full-time
   hard gate. A job description is not candidate evidence.
2. After those facts are available, `ats-agent prepare` must create or refresh
   the selected proposal. The candidate must explicitly choose only supported
   `change-id:variant` values bound to that proposal digest before `approve`,
   `apply`, and `validate`. No automatic approval is permitted.
3. A real generated document still needs manual rendered-layout inspection.
   Current validation is truthful structural/content validation; it does not
   prove pagination, clipping, or visual layout.
4. There is no configured and authorized paid/external rewrite provider, so
   live provider latency and cost are intentionally unmeasured. The new direct
   Scrapling transport has local runtime/unit evidence plus the generic IANA
   probe above; no fresh live-job capture was written to a newly selected
   candidate run directory in this audit.
5. Hosted CI for this dirty unpushed checkout, the protected private holdout,
   blinded human evaluation, and protected release/publication are external
   gates. The no-holdout failure remains correct and must not be bypassed.
6. The current wheel above is tested but deliberately uninstalled. Re-hash it
   and obtain fresh explicit user approval before replacing the managed
   `ats-agent`; same version text is not sufficient identity evidence.

No item above has been marked complete without its required evidence. The plan
is locally complete through the safe, tested artifact boundary, but the overall
goal is **not complete** until these real/manual/external acceptance criteria
are separately satisfied.

### Final verification refresh — 2026-09-06

This entry supersedes earlier *current* source identities, wheel paths, and
performance figures. Historical records remain useful as execution history but
are not release evidence for the current source SHA-256
`d898020481786e4db35abcb1eaba6eb7465f021f751bef2e7e75ac41d6a39d33`.
All source checks below used
`uv run --isolated --extra dev --extra documents` because the checkout's
local virtualenv launcher points to a removed interpreter. That verification
route did not install or replace the managed CLI.

#### Completed local acceptance evidence

| Requirement | Current result | Evidence and boundary |
|---|---|---|
| Direct public capture peer binding | Complete and live-exercised | The existing pinned Scrapling 0.4.12 runtime now constructs its bundled curl_cffi Session with a CurlOpt.RESOLVE record from one validated public DNS lookup. It disables redirects, proxies, and impersonation, enables TLS verification, then converts the response through Scrapling's existing ResponseFactory and Convertor. The generic IANA reserved-domains probe completed as scrapling_public_https with 2,660 bytes and SHA-256 `532550a9c1d637396e5b6164d9593f6ee5cdb50dfffcaad0fe400178f57403ae` at `/tmp/ats-final-public-capture.BIkBOr/iana-reserved-domains.txt`. This is live transport evidence only, not a job draft or candidate artifact. |
| Network/output hardening | Complete locally | Credential-free public HTTPS and all-public DNS remain required. The child environment removes proxy, TLS trust-store, and Python path/user-site overrides; a 45-second deadline, atomic temporary output, and a 4 MiB pre-decode/publish limit remain enforced. Board capture retains numeric-peer TLS and its bounded streaming reader. The parent cannot inspect the child socket or portably cancel a blocked OS resolver thread; those limits are documented rather than claimed away. |
| Interrupted research-jobs recovery | Complete locally | Schema-2 journals checkpoint atomically. Resume accepts only verified proposal digest, capture hashes, and review artifacts; damaged state remains a visible blocked_recovery row and is never silently regenerated. Existing interruption and corrupt-artifact regressions passed in the 334-test suite. |
| Bounded research scheduling | Complete locally | Imported, expired, and already-blocked rows are retained synchronously. Only rows needing a capture enter the existing four-worker pool; the focused regression proves one normal, one expired, and one blocked row create one capture and one worker future. |
| Provider and candidate reuse | Complete and measured | The existing RewriteCache remains the one provider coalescing path, records invocation/hit/wait/unique-context counters, returns defensive copies, and releases waiters after failures. Shared provider identity serializes a configuration digest rather than a secret. The existing per-run candidate cache is protected by a standard-library lock; it loads unchanged candidate inputs once without creating a cross-run cache. |
| Source CV and truthful document validation | Preserved | The supplied PDF remained SHA-256 `cf416d911437c54bee134326d1c25e9a6f0a1073186696f1f091b225f9682aef`. The clean wheel's read-only format audit reported 873 extractable words, 99 lines, low risk, and only informational F5 (no recognised experience heading). No real proposal was approved, applied, or written; a format audit is not falsely reported as rendered-document validation. |

#### Reproduced performance evidence

The following 20-repetition, 20-role run is explicitly synthetic and offline:
a frozen two-page DOCX, five local evidence files, 20 local descriptions, a
50 ms mocked capture, and the deterministic provider. It measures regression
budgets, not real job-board or paid-provider latency/cost.

| Stage | p50 seconds | p95 seconds |
|---|---:|---:|
| Warm prepare plus review | 0.3920 | 0.8810 |
| Time to first proposal | 0.3591 | 0.7554 |
| Ten roles plus review | 3.0691 | 4.0551 |
| Twenty roles plus review | 6.0387 | 10.8360 |
| Analysis | 5.5653 | 9.9013 |
| Review writing | 0.4900 | 0.9329 |
| Cold prepare | 0.8146 | 1.8915 |
| Fresh mocked capture | 0.0571 | 0.0590 |
| Capture-cache hit | 0.0006 | 0.0014 |
| Explicit synthetic apply | 0.0438 | 0.0682 |
| Parse/audit validation | 0.0028 | 0.0043 |
| Resume twenty unchanged roles | 0.5183 | 0.6024 |
| Sequential distinct-host capture | 0.2208 | 0.2339 |
| Four-worker distinct-host capture | 0.0567 | 0.0600 |

Call counts were 20 fresh mocked captures, 20 capture-cache hits, 160
distinct-host captures, 20 initial tailor captures, and zero resume captures
or proposal calls. Provider counters were 14 observed/invoked contexts, 266
cache hits, zero coalesced waits, and 14 unique contexts. The paired
parallel-to-sequential ratio was 0.2570 p50 and 0.2745 p95, below the 0.50
target. All 20 initial and resumed outcomes remained awaiting_approval with
zero blocked outcomes. The report is
`/tmp/ats-final-perf.hxLiOl/report.json` and labels itself
synthetic_offline_with_review_and_mocked_capture.

#### Verification and tested artifact

- The exact CI coverage journey in .github/workflows/ci.yml passed: 334 tests
  plus the frozen benchmark and explicit propose → review → digest-bound
  approve → apply → validate coverage paths. It retained the 90% threshold:
  5,439 statements, 431 missed, 1,926 branches, and 285 partial branches.
  The complete run took 40.5 seconds wall-clock in this verification session.
- Ruff, Mypy (35 source files), the 270-case benchmark, adapter validation,
  release-tree integrity, frozen-skill validation, benchmark-diversity,
  compileall, Bandit at -ll, and local pip-audit all passed. Pip-audit found
  no known vulnerabilities.
- The public prerelease check passed. The require-holdout variant exited 1
  because no private holdout was supplied; this is the intended fail-closed
  result, not a completed holdout gate.
- Both the current source and managed CLI passed strict doctor. The managed
  executable remains version 1.0.0b4 at engine SHA-256
  `fb4fc67af048e55eb11049bb7e623a59b8358276eaccfdf615eb050b3233d52e`;
  it was not modified.

| Fresh artifact | SHA-256 |
|---|---|
| `/tmp/ats-final-wheel.6GANja/tailoring_ats_cvs-1.0.0b4-py3-none-any.whl` | `0e502df330b0f6a328157e1204c2d2e37123e393d04b3876c5087621ff1c8c35` |
| `/tmp/ats-final-wheel.6GANja/tailoring_ats_cvs-1.0.0b4.tar.gz` | `55e894deea5047617e9c1372e87b137a91baa11829a3a6fff3f2c3a67e31c612` |

The fresh wheel installed only into
`/tmp/ats-final-wheel-env.FXMnjv`, outside the checkout. From /tmp its
site-packages entry point passed help, strict doctor, the eight-case
schema-3 smoke benchmark, and the supplied-PDF audit. Both thin adapters
passed strict doctor against that same wheel using the temporary
ATS_AGENT_EXECUTABLE_OVERRIDE. Fresh bundles at
`/tmp/ats-final-adapters.nkrECC` verified with ZIP SHA-256
`361d3f0680bdcf9f7fa7d292e361eca4d6429eef8d52d2bb412e6ffdc4c6edb7`
(skill) and
`a1ce9618dda48a6853a129a9e914fb8936570a64da63fbd517bb7b710228b03b`
(plugin). Setuptools emitted only its existing forward-looking
license-metadata deprecation warning during the successful build.

#### Reproducible commands

    uv run --isolated --extra dev --extra documents -- ruff check src tests scripts
    uv run --isolated --extra dev --extra documents -- mypy src/ats_agent
    uv run --isolated --extra dev --extra documents -- python scripts/check_benchmark.py
    uv run --isolated --extra dev --extra documents -- python scripts/validate_agent_adapters.py
    uv run --isolated --extra dev --extra documents -- python scripts/perf_batch_benchmark.py
    uv run --isolated --extra dev --extra documents -- bandit -r src/ats_agent -q -ll
    uv run --isolated --extra dev --extra documents -- pip-audit --local
    uv run --isolated --extra dev --extra documents -- python -m compileall -q src scripts tests
    uv run --isolated --extra dev --extra documents -- python scripts/release_check.py
    uv run --isolated --extra dev --extra documents -- python scripts/release_check.py --require-holdout

For coverage, execute the full Test, benchmark, and CLI workflow with branch
coverage block in .github/workflows/ci.yml under one COVERAGE_FILE; the
unit-only subset is correctly below 90% and is not substituted for the CI gate.
Build an uninstalled artifact with:

    uv run --isolated --extra dev --extra documents -- python -m build --outdir "$(mktemp -d /tmp/ats-wheel.XXXXXX)"

#### Exact remaining blockers; overall goal remains open

1. The retained full-time discovery results are draft-only and must be refreshed
   against the employer page before any action. A selected role still needs
   candidate-confirmed availability, location, and work authorisation; a job
   description cannot supply those facts. The retained BJAK proposal digest
   `57f2a3e0e6c1e96c4c3d2d6adc4e14d6df01295d2f4389a7d51abe840bcc3d78`
   retains unsupported C1/C2 candidates and an unknown full-time/work-mode
   gate.
2. After fresh prepare, the candidate must explicitly name only supported
   change-id:variant selections bound to the fresh digest before approve,
   apply, and validate. There is no blanket approval path.
3. A real generated document needs human rendered-layout inspection. Current
   structural/content validation does not prove pagination, clipping, or
   visual layout.
4. No configured, authorised paid/external rewrite provider is available, so
   live provider latency and cost remain intentionally unmeasured. The live
   IANA probe is generic transport evidence, not current job research.
5. Hosted CI for the dirty unpushed checkout, the protected private holdout,
   blinded human review, and protected release/publication remain external
   gates and are not marked complete.
6. The tested wheel above is deliberately uninstalled. Re-hash that exact file
   and obtain fresh explicit approval before replacing the managed ats-agent.

No external/manual gate has been fabricated or waived. Local implementation is
complete through the tested-artifact boundary; the overall goal remains open
until every blocker above is independently satisfied.

### Full-time scope correction and official-board recheck — 2026-09-06

The candidate explicitly requested **jobs, not internships**. The canonical AI
Job Search configuration was therefore corrected in its existing profile,
evaluation rubric, and query files:

- /Users/raghav/Documents/Dev_Projects/ai-job-search/CLAUDE.md
- /Users/raghav/Documents/Dev_Projects/ai-job-search/.claude/skills/job-application-assistant/01-candidate-profile.md
- /Users/raghav/Documents/Dev_Projects/ai-job-search/.claude/skills/job-application-assistant/04-job-evaluation.md
- /Users/raghav/Documents/Dev_Projects/ai-job-search/.claude/skills/job-scraper/search-queries.md

They now target remote full-time entry-level or associate roles in AI/product
operations, finance/strategy, and partnerships/commercial operations. This is
a search-scope correction, not a fabricated availability claim: the profile
still records only 25–35 hours per week and requires a candidate confirmation
of standard full-time hours before a role can be treated as eligible to apply.
No CV, tracker, application, candidate-output run, or portal dependency was
changed.

The existing five-role full-time list was rechecked read-only through the
engine's official Ashby posting API adapter, not by treating failed page
scrapes or prior fallback text as employer confirmation:

| Retained lead | Current official result | Correct use |
|---|---|---|
| Human Archive — Founder's Office | Confirmed listed: exact job ID a670da53-a205-4d8f-ab0c-e9316366335d, title Founder's Office, Operations, India, FullTime, published 2026-08-03T16:00:15.382+00:00. | The only currently confirmed full-time lead in this retained batch. Full-time schedule and work eligibility remain candidate gates. |
| BJAK — Founder's Office | The public Ashby board response exceeds the unchanged 4 MiB safe-response limit. Ashby's documented public endpoint returns the whole board; no public per-posting endpoint was found. | Do not lower the limit or infer that the job is current. Recheck through the employer page or an employer-supplied source before applying. |
| Panoptyc — Founder's Office: Growth/Ops | Official board returned six current rows, but none matched retained ID 19b84cef-1754-45c8-8306-7f17105b9bce. | Not a current confirmed opening from this source. |
| Vetcove — Product Operations Associate | Official board returned 25 current rows, but none matched retained ID b1e05b7b-1911-488e-b6da-c2d171f3841f. | Not a current confirmed opening from this source. |
| EvenUp — Product Operations Associate | Official public board endpoint returned HTTP 404 for evenup. | Not a current confirmed opening from this source. |

The standard Ashby hosted-page capture for BJAK again failed cleanly as empty
or insufficient. That outcome preserves the no-browser public-capture policy;
it does not justify upgrading old aggregator fallback text to official
provenance. The official API recheck used existing ats-agent board helpers and
made no application or tracker write.

The updated shortlist boundary is therefore precise: Human Archive is a
current, employer-confirmed full-time India lead; the other four retained leads
are not currently confirmed. Before any proposal or application, the candidate
must still confirm full-time availability, location/work authorisation, and
choose an explicit digest-bound approval after a fresh prepare run.

### Live full-time discovery refresh — 2026-09-06

The requested scope is jobs, not internships. This additional discovery pass
was read-only: it made no tracker, portal, CV, proposal, approval, or
application change, and it did not treat search-result text as candidate
evidence.

| Lead | Evidence status | Recommendation boundary |
|---|---|---|
| [BJAK — Founder's Office, Finance Super App (India)](https://jobs.ashbyhq.com/bjakcareer/f9d67c97-2a70-4d28-bc1e-daca703ef7eb) | The direct employer posting was publicly indexed in the current discovery pass as full-time, remote, and India-based. Its role scope covers market research, partnerships, licensing, finance, operations, and founder-level execution. The existing safe Ashby board adapter still cannot consume BJAK's over-4 MiB board response, and direct public capture remains intentionally insufficient without a browser fallback. | Best current role-alignment lead, but only if the candidate confirms India-based work status and standard full-time availability. Reopen the employer page and run fresh prepare before any CV proposal; do not promote this indexed evidence to captured provenance. |
| [Human Archive — Founder's Office](https://jobs.ashbyhq.com/humanarchive/a670da53-a205-4d8f-ab0c-e9316366335d) | The live, hardened official Ashby API check returned this exact listed FullTime India role. Its `isRemote` and `workplaceType` fields were null, so its actual work mode is unknown. | Current employer-confirmed lead, conditional on location/work-mode and full-time facts. It is not safe to describe as a remote role. |
| [TD SYNNEX — Strategy & Operations Analyst](https://synnex.wd5.myworkdayjobs.com/en-US/tdsynnexcareers/job/Strategy---Operations-Analyst_R51487) | The direct employer posting was publicly indexed four days ago as Remote India/Delhi, full-time. It explicitly asks for 2–4 years of strategy, consulting, or analytical-business experience. The no-browser capture intentionally returned insufficient content. | A stretch, not a primary application target unless the candidate can substantiate the experience requirement from existing evidence. |
| Editorialist — Operations Associate | Its previous direct Lever URL returned HTTP 404 both through the hardened capture path and an independent web fetch. | Excluded as expired; do not present it as an opening. |

This evidence separates discovery from verification: source-backed direct pages
are useful for prioritisation, but `ats-agent prepare` remains the only route
to a candidate-specific, provenance-preserving proposal. The previous blockers
for factual eligibility, digest-bound approval, rendered-document inspection,
provider measurement, external evaluation, and explicit managed-CLI install
approval remain unchanged.

### URI canonicalisation and final verification refresh — 2026-09-06

This entry supersedes the prior *current* source identity, performance figures,
and wheel paths after one further shared-boundary hardening change. Historical
entries remain execution history, not release evidence for source SHA-256
`4e598bd099d2ac94f21aad31174a3c5388f7201f28b675d601e5b7b93d0dd0bc`.

#### Additional direct-capture hardening

`src/ats_agent/capture.py` now canonicalises an IDNA-valid DNS hostname before
both DNS resolution and the curl_cffi `CurlOpt.RESOLVE` pin are constructed.
It rejects raw whitespace/control characters, a trailing DNS-root dot,
percent-encoded host text, and literal IP hostnames. This keeps the hostname
whose public addresses were verified identical to the hostname that curl uses
for its pin, rather than relying on implicit URL-library normalisation. It
does not add redirects, proxies, browser automation, credentials, or a weaker
IP policy.

The new regression proves a Unicode hostname is converted to its ASCII IDNA
form before both the resolver and pinning record. The unsafe-URL regression
also covers `example.com.`, a literal public IP, and a newline-bearing URL.
The focused network suite (37 tests) and job-research suite (21 tests) passed
after this change. A current generic public transport probe of IANA's reserved
domains page completed through the hardened path as
`scrapling_public_https`, with 2,660 bytes and SHA-256
`532550a9c1d637396e5b6164d9593f6ee5cdb50dfffcaad0fe400178f57403ae` at
`/tmp/ats-hardening-live-capture.FQUeJs/iana-reserved-domains.txt`. This is
transport evidence only, not job or candidate data.

#### Reproduced local gates

- Ruff and Mypy (35 source files) passed. The exact CI branch-coverage
  journey, including benchmark and explicit propose -> review ->
  digest-bound approve -> apply -> validate -> tailor paths, passed with
  **335 tests**: 5,455 statements, 433 missed, 1,930 branches, 285 partial,
  and **90%** total coverage. The threshold was retained exactly.
- The 270-case frozen benchmark, benchmark-diversity validator, skill and
  release-tree checks, adapter validation, reproducible bundle verification,
  compileall, Bandit at `-ll`, and local pip-audit all passed. Pip-audit found
  no known vulnerabilities. The public prerelease check passed; the
  `--require-holdout` variant exited 1 because no private holdout was supplied,
  the required fail-closed result.
- Source and managed `doctor --strict` both passed. The source engine is the
  SHA above; the managed user executable remains deliberately unchanged at
  engine SHA-256
  `fb4fc67af048e55eb11049bb7e623a59b8358276eaccfdf615eb050b3233d52e`.

#### Reproduced performance evidence

This 20-repetition, 20-role run remains explicitly synthetic and offline: the
frozen two-page DOCX, five local evidence files, 20 local descriptions, a
50 ms mocked capture, and the deterministic provider. It is a regression
budget, not a claim about live job sites or paid providers.

| Stage | p50 seconds | p95 seconds |
|---|---:|---:|
| Warm prepare plus review | 0.1890 | 0.2423 |
| Time to first proposal | 0.1784 | 0.2297 |
| Ten roles plus review | 1.3757 | 1.5256 |
| Twenty roles plus review | 2.6880 | 3.3182 |
| Analysis | 2.4783 | 3.0453 |
| Review writing | 0.2207 | 0.2727 |
| Cold prepare | 0.4165 | 0.6026 |
| Fresh mocked capture | 0.0581 | 0.0603 |
| Capture-cache hit | 0.0012 | 0.0015 |
| Explicit synthetic apply | 0.0223 | 0.0234 |
| Parse/audit validation | 0.0015 | 0.0016 |
| Resume twenty unchanged roles | 0.1490 | 0.1709 |
| Sequential distinct-host capture | 0.2187 | 0.2230 |
| Four-worker distinct-host capture | 0.0565 | 0.0576 |

The run observed 20 fresh mocked captures, 20 capture-cache hits, 160
distinct-host mock captures, 20 initial tailor captures, zero resume captures,
and zero resume proposal calls. Provider counters were 14 observed/invoked
contexts, 266 cache hits, zero coalesced waits, and 14 unique contexts. Its
parallel-to-sequential ratio was 0.2582 p50 and 0.2689 p95, below the 0.50
target. All initial and resumed outcomes remained `awaiting_approval`, with
zero blocked outcomes. Live-site latency and paid-provider latency/cost remain
intentionally unmeasured.

Reproduce the measurement with:

    uv run --isolated --extra dev --extra documents -- python scripts/perf_batch_benchmark.py

#### Reproduce the current local verification

    uv run --isolated --extra dev --extra documents -- ruff check src tests scripts
    uv run --isolated --extra dev --extra documents -- mypy src/ats_agent
    uv run --isolated --extra dev --extra documents -- python scripts/check_benchmark.py
    uv run --isolated --extra dev --extra documents -- python scripts/validate_agent_adapters.py
    uv run --isolated --extra dev --extra documents -- python scripts/validate_benchmark_diversity.py
    uv run --isolated --extra dev --extra documents -- python scripts/validate_skill.py
    uv run --isolated --extra dev --extra documents -- python scripts/check_release_tree.py
    uv run --isolated --extra dev --extra documents -- bandit -r src/ats_agent -q -ll
    uv run --isolated --extra dev --extra documents -- pip-audit --local
    uv run --isolated --extra dev --extra documents -- python -m compileall -q src scripts tests
    uv run --isolated --extra dev --extra documents -- python scripts/release_check.py
    uv run --isolated --extra dev --extra documents -- python scripts/release_check.py --require-holdout

For the mandatory branch gate, run the whole `Test, benchmark, and CLI workflow
with branch coverage` block in `.github/workflows/ci.yml` under one isolated
environment and `COVERAGE_FILE`; do not replace it with the lower-coverage
unit-only command. Build a candidate wheel without touching the managed CLI:

    uv run --isolated --extra dev --extra documents -- python -m build --outdir "$(mktemp -d /tmp/ats-wheel.XXXXXX)"

#### Tested artifact; deliberately not installed

| Artifact | SHA-256 |
|---|---|
| `/tmp/ats-hardening-wheel.mrniLQ/tailoring_ats_cvs-1.0.0b4-py3-none-any.whl` | `afd9734ed46bc2a4e16c2666aa93422b1ba92563f553b0c84a88bb7d7bbeeda7` |
| `/tmp/ats-hardening-wheel.mrniLQ/tailoring_ats_cvs-1.0.0b4.tar.gz` | `921f856a0dc98319dc79d4f79f78e7c3d6a6fcc3d6fbe5761173ae1be18e6d74` |

`python -m build --outdir` created these in a fresh temporary directory; the
only build output beyond normal packaging was the existing forward-looking
setuptools license-metadata warning. The wheel was installed only into
`/tmp/ats-hardening-wheel-env.NcFkA6/venv`. From `/tmp`, its site-packages
entry point passed help, strict doctor, the schema-3 eight-case smoke benchmark,
the new IDNA assertion, and the supplied source-PDF read-only format audit
(873 words, low risk). Both thin adapters passed strict doctor against that
wheel using temporary `ATS_AGENT_EXECUTABLE_OVERRIDE`; this did not alter the
managed install manifest or executable.

#### Exact remaining blockers; overall goal remains open

1. The fresh wheel above must be re-hashed and receive fresh explicit user
   approval before it can replace the managed `ats-agent`. Matching version
   text is not artifact identity.
2. A selected full-time role still needs candidate-confirmed standard
   availability, work location, and work authorisation plus a user-selected
   candidate run directory. A job description cannot supply those facts.
3. Only after fresh `ats-agent prepare` may the candidate explicitly choose
   supported `change-id:variant` values bound to that exact proposal digest;
   then and only then can apply and validation occur. A real output also needs
   human rendered-layout inspection.
4. No configured and authorised paid/external rewrite provider is available,
   so live provider latency and cost remain unmeasured.
5. Hosted compatibility/security CI for this dirty, unpushed checkout, the
   protected private holdout, blinded human evaluation, and protected
   publication/release remain external gates. The protected-holdout failure is
   preserved rather than bypassed.

No unavailable or manual gate has been marked complete. The local source and
tested-artifact boundary are complete; the overall goal remains open until the
requirements above obtain their own evidence.

### Canonical capture deduplication and final artifact refresh — 2026-09-06

This is the final current local record. It supersedes the prior source identity,
artifact paths, and performance figures after the URL canonicalisation boundary
was extended to its cache and batch-dedup consumers. The current source
SHA-256 is `11fb842ccbedef2683571cd1ad0400bd11eb07547ff6fe4cbc06f2c4df32b0c3`.

#### Shared capture-key correction

`capture_cached` now derives its lock stripe, cache filenames, cached provenance
comparison, and downstream capture call from the same canonical IDNA URL used
by the network boundary. `fetch_many` uses that canonical URL as its batch
dedup key while preserving unsafe URLs as visible `CaptureError` outcomes.
Thus `https://täst.example/role` and
`https://xn--tst-qla.example/role` make one capture/cache entry rather than
two. The new regression proves one cache miss, one cache hit, one batch
capture, and both requested output destinations. This changes neither candidate
evidence, approval binding, source-CV protection, provenance fields, nor the
no-proxy/no-browser/no-redirect policy.

The focused network suite now has 38 passing tests; the complete branch
workflow has **336 passing tests** and retains **90%** coverage (5,465
statements, 437 missed, 1,930 branches, 285 partial). Ruff, Mypy, the frozen
270-case benchmark, benchmark diversity, skill and release-tree checks,
adapter validation and bundles, compileall, Bandit `-ll`, local pip-audit, and
the public prerelease check all passed again. The protected-holdout command
again exited 1 with its required no-private-holdout failure.

#### Reproducible performance measurement

The final successful report is
`/tmp/ats-final-canonical-perf-retry.ENQavL/report.json`. It is a 20-run,
20-role synthetic/offline measurement using the frozen inputs, a 50 ms mock
capture, and the deterministic provider. Its host load was recorded as 12.25
one-minute average before and 8.85 after the run on an eight-CPU machine; the
acceptance thresholds are unchanged.

| Stage | p50 seconds | p95 seconds |
|---|---:|---:|
| Warm prepare plus review | 0.3104 | 0.4057 |
| Time to first proposal | 0.2935 | 0.3828 |
| Ten roles plus review | 2.1987 | 2.4910 |
| Twenty roles plus review | 4.3191 | 5.0223 |
| Analysis | 3.9752 | 4.6330 |
| Review writing | 0.3437 | 0.3891 |
| Cold prepare | 0.6532 | 0.9204 |
| Fresh mocked capture | 0.0573 | 0.0589 |
| Capture-cache hit | 0.0011 | 0.0013 |
| Explicit synthetic apply | 0.0366 | 0.0370 |
| Parse/audit validation | 0.0024 | 0.0025 |
| Resume twenty unchanged roles | 0.2466 | 0.2641 |
| Sequential distinct-host capture | 0.2205 | 0.2238 |
| Four-worker distinct-host capture | 0.0570 | 0.0594 |

Call counts were 20 fresh mock captures, 20 cache hits, 160 distinct-host mock
captures, 20 initial tailor captures, zero resume captures, and zero resume
proposal calls. Provider counters were 14 observed/invoked contexts, 266 cache
hits, zero coalesced waits, and 14 unique contexts; provider p50/p95 was
0.000104 s / 0.000245 s. The paired parallel-to-sequential ratio was 0.2576
p50 and 0.2739 p95, under the 0.50 target. All initial/resumed outcomes were
`awaiting_approval`, with zero blocked outcomes.

One earlier report at
`/tmp/ats-final-canonical-perf.UMoxWE/report.json` failed honestly during
exceptional host contention: cold p95 was 3.5353 s and concurrent-capture
ratio p95 was 0.5013. It was retained as observed evidence, not converted into
a pass or used to relax a target. The lower-load rerun above is the passing
current measurement. Neither report measures live job sites or a paid provider.

#### Final tested artifact; not installed

| Artifact | SHA-256 |
|---|---|
| `/tmp/ats-final-canonical-wheel.bEXcv5/tailoring_ats_cvs-1.0.0b4-py3-none-any.whl` | `8d57ecd4cf2ed29eb9b28585f9c7647120639cdb4567157a1fe4ffe88b56f495` |
| `/tmp/ats-final-canonical-wheel.bEXcv5/tailoring_ats_cvs-1.0.0b4.tar.gz` | `7e6ee88b13d6da018edfe3cb5ce557b454e2dcb5e36682a97354077ab9f45454` |

The wheel installed only into
`/tmp/ats-final-canonical-wheel-env.Jx4OLk/venv`. From `/tmp`, its
site-packages CLI passed help, strict doctor, the schema-3 smoke benchmark,
the IDNA URL assertion, and the supplied-PDF format audit (873 words, low
risk). Both thin adapters passed strict doctor against that wheel via temporary
`ATS_AGENT_EXECUTABLE_OVERRIDE`. A fresh live generic IANA capture through the
current source completed as `scrapling_public_https`, 2,660 bytes, SHA-256
`532550a9c1d637396e5b6164d9593f6ee5cdb50dfffcaad0fe400178f57403ae`, at
`/tmp/ats-final-canonical-live.jK31eR/iana-reserved-domains.txt`.

The managed CLI remains version `1.0.0b4` on older source SHA-256
`fb4fc67af048e55eb11049bb7e623a59b8358276eaccfdf615eb050b3233d52e`;
both it and the current source passed `doctor --strict`. It was not modified.

#### Exact remaining blockers; overall goal remains open

1. Explicit user approval is required to install the exact wheel above after
   re-hashing it. Same-version text is not sufficient identity evidence.
2. A selected full-time job, confirmed standard full-time availability,
   location/work authorisation, and a user-selected candidate run directory
   are required for a real proposal. Job text remains non-candidate evidence.
3. The candidate must explicitly approve selected `change-id:variant` values
   bound to a fresh proposal digest before apply. A resulting real document
   still needs a human rendered-layout inspection.
4. Live paid/external-provider latency and cost require a configured provider
   and explicit authorisation.
5. Hosted CI for the dirty unpushed checkout, protected private holdout,
   blinded human evaluation, and protected publication remain external gates.

No local, manual, or external gate has been silently waived or marked complete
without its own evidence.

## Final local refresh and remaining external gates — 2026-09-08

This section supersedes older "current" source hashes, wheels, timings, and
local-test totals in all historical execution records in this document. It records the
current checkout evidence only; it does not convert a fixture, a generic
network capture, or a source-document audit into an application or release.

### Completed local remediation

- `ats-agent` remains the sole CV engine. The thin adapters invoke the
  executable and do not recreate extraction, requirement mapping, rewrite,
  approval, application, or validation behaviour.
- Shared artifact helpers now atomically replace text and copied artifacts,
  while refusing outputs, receipt/recovery sidecars, review bundles, capture
  cache materialisations, and run directories that alias a protected CV,
  evidence, proposal, or job input. This closes the same source-protection
  root cause across the CLI, workflow, capture, review, research, deep-dive,
  and orchestrator paths.
- `research-jobs` persists its schema-2 journal and recovery artifacts
  atomically. Interrupted/corrupt artifacts recover to a visible
  `blocked_recovery` state rather than being silently reused or overwritten.
  The scheduler still sends only capture-needed roles through the existing
  four-worker bound.
- Capture reuse still validates cache metadata and body hashes, materialises a
  cache hit at its requested destination, canonicalises eligible URLs, and
  keeps the existing public-HTTPS/DNS, redirect, proxy, timeout, response-size,
  host-pacing, cleanup, and provenance safeguards. No network policy was
  weakened for performance.
- Per-batch candidate analysis is keyed to candidate content identity. Provider
  calls are keyed to provider configuration and context identity, coalesced
  where applicable, and resume reuses unchanged persisted proposals. Applying
  still verifies the exact proposal digest, candidate/source identities, hard
  gates, explicit change IDs and variants, and output/document mode.
- The default research workflow is now explicitly **full-time jobs only**.
  `research-jobs` visibly retains an explicit internship or part-time,
  contract, temporary, or freelance row as `excluded_scope` and neither
  captures nor proposes it by default. `--include-internships` is an explicit
  opt-in for internships only; non-full-time employment remains excluded.
  `deep-dive` likewise excludes internships from its default career matches,
  while retaining an explicit opt-in for exploratory use. Unknown employment
  scope remains visible rather than being invented as full-time.

### Read-only document check

The supplied `/Users/raghav/Downloads/Raghav_Badhwar_.pdf` was inspected only
through the source CLI's read-only `format` and `validate` paths. Both reported
an audited/valid input with 873 words, 99 lines, low formatting risk, and an
informational missing-conventional-`experience` finding. No output document,
application, approval, source-CV modification, or rendered-layout claim was
created. A real output remains `delivery_ready: false` until its content is
validated and a human reviews its rendered layout.

### Current-source verification

| Check | Observed result |
|---|---|
| Lint and typing | `ruff check src tests scripts` passed; `mypy src/ats_agent` passed for 35 source files. |
| Branch suite | 346 tests passed in 12.859 s. The unchanged `coverage report --fail-under=90` gate passed: 5,592 statements, 456 missing, 1,968 branches, 297 partial branches; report display was 90%, raw total 89.61640211640211%. |
| Benchmark and adapters | Frozen public/adversarial/documents benchmark: 270 passing cases. `scripts/validate_agent_adapters.py` passed with no errors. |
| Security and package hygiene | `compileall`, Bandit at `-ll`, local `pip-audit`, release-tree, skill, benchmark-diversity, bundle-build, and bundle-verify checks passed. |
| Stable-release holdout gate | `scripts/release_check.py --require-holdout` correctly failed closed because no private holdout was supplied; this is an unresolved release gate, not a passing check. |

### Reproducible synthetic performance evidence

`/tmp/ats-final-perf.Ub0MeK/report.json` passed with 20 repetitions on CPython
3.14.6/macOS 26.6.2. It uses fixed local fixtures, deterministic provider
behaviour, and mocked capture. These are **synthetic/offline** timings, not
live job-site, real-document, or paid-provider results.

| Stage | p50 seconds | p95 seconds |
|---|---:|---:|
| Warm prepare plus review | 0.2894 | 0.3289 |
| Time to first proposal | 0.2724 | 0.3112 |
| Ten roles | 2.0034 | 2.2636 |
| Twenty roles | 3.8556 | 4.5357 |
| Analysis | 3.5145 | 4.1692 |
| Review writing | 0.3242 | 0.3692 |
| Cold prepare | 0.5596 | 0.7164 |
| Fresh mocked capture | 0.0588 | 0.0595 |
| Capture-cache hit | 0.0011 | 0.0015 |
| Sequential distinct-host capture | 0.2201 | 0.2237 |
| Four-worker distinct-host capture | 0.0564 | 0.0588 |
| Explicit synthetic apply | 0.0288 | 0.0304 |
| Validation | 0.0018 | 0.0020 |
| Resume twenty unchanged roles | 0.1493 | 0.1543 |

The run recorded 20 initial-tailor captures, 20 fresh mocked captures, 20
cache hits, and 160 distinct-host mocked captures. Resume recorded zero
captures and zero proposal calls. Provider counters were 14 observed/invoked
contexts, 14 unique contexts, 266 cache hits, and zero coalesced waits. All 20
initial and all 20 resumed roles were `awaiting_approval`, with zero blocked
outcomes. The parallel/sequential ratio was 0.2566 p50 and 0.2736 p95, below
the unchanged 0.50 target.

### Tested package artifact; not installed

| Artifact | SHA-256 |
|---|---|
| `/tmp/ats-final-wheel.cLDbV2/tailoring_ats_cvs-1.0.0b4-py3-none-any.whl` | `9538d3dd25428ea791f095dba008343d91d91dae1b3cdcc079841baa6b7774df` |
| `/tmp/ats-final-wheel.cLDbV2/tailoring_ats_cvs-1.0.0b4.tar.gz` | `0f6162152ec0f3454e51478d345fcd92fe30e1e9162c0dcc4f627cc2a07d8ec7` |

The wheel was built from the current source, installed only into
`/tmp/ats-final-wheel-env.HWzyul/venv`, and invoked from outside the checkout.
Its `ats-agent --version`, strict doctor, smoke benchmark, full-time scope
help, source-PDF read-only audit, and both adapter routes passed from
site-packages. Its engine SHA was
`e7ebd4808d4b4b36a0cb67905010f7d3ad72556fea236472ef2e3e8be80d738d`.
The build emitted only the existing setuptools license-table/classifier
deprecation warning. The managed executable was separately checked and remains
on SHA `fb4fc67af048e55eb11049bb7e623a59b8358276eaccfdf615eb050b3233d52e`.
It was not modified; equal `1.0.0b4` version text is not evidence of equal
engine content.

### Security review: completed snapshot audit, current remediation verified

The completed Codex Security scan `a8ca0787-95d5-46ec-b858-678eab083b09`
reviewed the CV-workflow security surfaces at snapshot
`d62d01c63c9651f38727d993ea231cac620690bc`. Its report is a **partial**
source-surface audit, not a security certification or a line-by-line review of
the current dirty tree. It reported one high-confidence medium finding
(`filesystem.symlink-sidecar-overwrite`, CWE-59): the snapshot's predictable
`<output>.applied.json` receipt could follow a pre-existing run-directory
symlink to a candidate source document.

The current working tree implements the report's shared remediation before the
final verification: atomic sibling-temp-and-replace writes, resolved-path
checks covering primary and derived artifacts, and input/run-directory
separation. Focused tests construct the malicious receipt sidecar and cache
alias arrangements and confirm rejection without changing the source bytes;
the 346-test branch suite passed afterward with the unchanged coverage gate.
The scan itself predates the uncommitted remediation, so its finding remains
open in the historical scan record rather than being falsely relabelled as a
clean current-tree finding. See its local report at
`/private/var/folders/wy/yf6sv559135frnvj_b5gzgtm0000gn/T/codex-security-scans-2ECWgt/tailoring-ats-cvs/d62d01c63c9651f38727d993ea231cac620690bc_20260907T184209Z_5yyz4xoe/report.md`.

### Fresh official-board full-time job research

The following leads were checked on official employer boards after the local
security review. They are **jobs, not internships**; their listing pages
showed an application action when checked. They are a ranked research
shortlist, not an assertion that the candidate is eligible, available, or
approved to apply. No application, external capture through `ats-agent`, or
CV proposal was made.

| Priority | Official full-time job | Why it is a plausible match | Explicit gate or gap to resolve first |
|---|---|---|---|
| 1 | [Paytm — Associate Product Manager, Lending](https://jobs.lever.co/paytm/255aa024-39ae-4f74-a62b-b062ec12db97), Noida, on-site | Closest overlap of the supplied CV's corporate-finance, lending/fintech interest, product-system work, cross-functional execution, and analytical background. The listing asks for end-to-end lending journeys, product requirements, roadmaps, and customer experience. | Confirm whether standard full-time work is possible before the stated May 2027 degree completion; substantiate any lending-product experience instead of inventing it. |
| 2 | [Better — Marketing Operations & AI Automation Coordinator](https://jobs.ashbyhq.com/better-mortgage/8b7bdc9a-e05d-4783-8d9f-1f5d3c26b4e3), Gurugram, remote | Strong tool overlap: automation, GitHub, Supabase, Vercel, AI tools, Canva, campaign operations, reporting, and quality controls; the commercial/campus work supports the operational side. | The official posting explicitly asks for 2+ years of marketing operations/technology experience plus hands-on automation. Treat as a stretch unless that experience is factual and supportable. |
| 3 | [Numerix — Market Data Operations Analyst](https://job-boards.greenhouse.io/numerix/jobs/5406676008), remote India | Finance, Python, SQL, Excel, data-quality/operations, and approval-oriented systems align with the source CV's finance and technical work. | The listing requires India work authorisation, a bachelor’s degree or equivalent experience, derivatives knowledge, and potential US-shift availability. Each needs a truthful candidate confirmation. |
| 4 | [Teikametrics — Product Operations Analyst](https://jobs.lever.co/teikametrics/b144b9bc-9d02-4b13-88f0-44b431476c7c), India remote | Product/engineering/customer operations and SQL troubleshooting are directionally relevant. | The listing explicitly calls for 2–3 years of technical-SaaS experience and support/troubleshooting evidence, making it lower priority for the supplied early-career profile. |

The Paytm official board also showed full-time APM travel and telco listings,
but their job-specific requirements should be re-opened from the official
application page before ranking them above the four documented leads. The tool
now keeps any internship rows visibly excluded by default rather than mixing
them into this full-time shortlist.

### Exact remaining blockers; overall goal remains open

1. **Managed CLI:** explicitly approve installation of the exact wheel hash
   above. Until then, the older managed executable remains in place.
2. **Real full-time pilot:** select one currently open, official-board job;
   confirm standard full-time availability and India location/work
   authorisation; and choose an empty, separate candidate run directory. Only
   then may `ats-agent prepare` create a proposal. Job text remains
   non-candidate evidence.
3. **Approval and delivery:** after that fresh proposal, explicitly select each
   `change-id:variant` against its persisted digest. Apply only to a distinct
   output, run `validate`, and obtain a human rendered-layout review before
   delivery or application.
4. **Live measurements:** a configured paid/external provider plus explicit
   cost authority are required for live provider latency, call-count, and cost
   evidence. Synthetic results do not substitute.
5. **Release evidence:** hosted CI for the dirty/unpushed checkout, a protected
   private holdout, blinded human evaluation, and release/publication authority
   remain unavailable. The stable-release gate must stay fail-closed.

Reproduce the local gates without replacing the managed CLI:

```bash
PYTHONPATH=src .venv/bin/ruff check src tests scripts
PYTHONPATH=src .venv/bin/mypy src/ats_agent
PYTHONPATH=src .venv/bin/python -m coverage erase
PYTHONPATH=src .venv/bin/python -m coverage run --branch --source=ats_agent -m unittest discover -s tests -v
PYTHONPATH=src .venv/bin/python -m coverage report --fail-under=90
PYTHONPATH=src .venv/bin/python scripts/check_benchmark.py
PYTHONPATH=src .venv/bin/python scripts/validate_agent_adapters.py
PYTHONPATH=src .venv/bin/python scripts/perf_batch_benchmark.py
PYTHONPATH=src .venv/bin/python -m build --outdir /tmp/ats-final-wheel.cLDbV2
```

### Streamed direct-capture boundary and final artifact refresh — 2026-09-06

This is the current local evidence record. It supersedes all earlier source
identities, artifact paths, timing figures, and generic transport probes. The
current source engine SHA-256 is
`944dae2d82bdde06f1e359094cda88688c6ed1bb501a3d917adbc264fc0e2b26`.
The managed CLI was deliberately not changed.

#### Final local network hardening repair

The direct public-page path previously checked the temporary artifact size
only after the isolated Scrapling/cURL child had completed. That protected the
published file but left a large response able to accumulate in the child
before conversion. The pinned child now applies two existing `curl_cffi`
mechanisms before it hands content to Scrapling's converter:

- `CurlOpt.MAXFILESIZE_LARGE` rejects a declared oversized body in cURL.
- `content_callback` accumulates only bounded chunks and aborts an
  undeclared/chunked body before the child can buffer beyond 4 MiB.

The child maps either path to `response exceeds the maximum capture size`,
never writes a destination, and the caller treats both child-time and
post-write size errors as permanent (no retry-budget waste). It retains public
HTTPS-only DNS validation, direct validated-peer pinning, TLS verification, no
redirects, no proxies, scrubbed child environment, bounded deadline, atomic
materialisation, provenance, and the existing board-feed streaming cap. No
browser, credential, proxy, redirect, or new dependency was added.

The OS resolver itself still cannot be cancelled portably by Python once its
daemonized lookup has begun; the caller's deadline returns control and blocks
publication, but does not pretend to kill that platform thread. The parent
also cannot inspect the child socket directly. Both limits are contained by
the caller deadline plus cURL's `RESOLVE` peer pin and TLS hostname validation;
neither is represented as a stronger guarantee than the runtime can provide.

`CaptureCacheTests.test_pinned_scrapling_child_stops_oversized_body_during_streaming`
executes the exact injected child source against mocked cURL/Scrapling modules:
both callback and header-size paths abort before conversion or output, while
asserting the peer pin and byte-limit cURL options. The expanded oversized
output regression also proves only one attempt occurs even when three are
requested. The complete 39-test network suite passed. A controlled real
runtime probe used the same packaged child source with an in-memory 64-byte
limit against IANA: cURL exited 1 with that exact error and created no output.
This validates the boundary mechanism, not a claim about a real 4 MiB job page.

The prior provider configuration identity repair, default-port URL
canonicalisation, interrupted `research-jobs` journal recovery, candidate
input reuse, and exact approval-resume protections remain covered by the full
suite. `ats-agent` remains the sole engine: neither adapters nor job discovery
gain authority to create candidate evidence, approvals, or document changes.

#### Full verification and synthetic performance evidence

The unchanged branch-coverage/CLI journey from `.github/workflows/ci.yml` was
rerun at `/tmp/ats-stream-bound-fullcoverage.UJxXnx` after the streamed-limit
repair. It covered proposal-only exit, review, explicit variant selection,
approve, apply, validate, initial `tailor`, persisted-approval `tailor`, and
the smoke benchmark.

- **339 tests** passed in **7.514 s**.
- Branch coverage remained exactly **90%**: 5,491 statements, 440 missed,
  1,936 branches, and 286 partial branches. The configured gate was unchanged.
- Ruff, Mypy for 35 source files, the 270 frozen benchmark cases, adapters,
  skill/release-tree/diversity checks, reproducible adapter bundles, Bandit
  source scan, local `pip-audit`, compileall, and public prerelease check all
  passed at `/tmp/ats-stream-bound-quality.ZEolQy`.
- `release_check.py --require-holdout` exited **1** with
  `stable releases must pass the protected holdout` at
  `/tmp/ats-stream-bound-holdout.nzJI0F`, because no private holdout was
  supplied. This expected fail-closed result is not a stable-release pass.

`/tmp/ats-stream-bound-perf-json.1F9rV8/report.json` (SHA-256
`6df4149d65bab02001caec20fe449a5ce31428b8ed5f1c69172694018433d16c`) is a
fresh valid-JSON, 20-repetition/20-role **synthetic/offline** measurement for
this exact source. It uses frozen local DOCX/evidence/JD fixtures, a 50 ms
mocked capture, and the deterministic provider. It makes no live job-site,
paid-provider, or candidate-document performance claim.

| Stage | p50 seconds | p95 seconds |
|---|---:|---:|
| Warm prepare plus review | 0.1779 | 0.1911 |
| Time to first proposal | 0.1677 | 0.1808 |
| Ten roles plus review | 1.2600 | 1.2752 |
| Twenty roles plus review | 2.4775 | 2.5030 |
| Analysis | 2.2858 | 2.3106 |
| Review writing | 0.1909 | 0.2042 |
| Cold prepare | 0.3728 | 0.4339 |
| Fresh mocked capture | 0.0567 | 0.0587 |
| Capture-cache hit | 0.0004 | 0.0004 |
| Explicit synthetic apply | 0.0226 | 0.0257 |
| Parse/audit validation | 0.0015 | 0.0020 |
| Resume twenty unchanged roles | 0.1438 | 0.1580 |
| Sequential distinct-host capture | 0.2172 | 0.2208 |
| Four-worker distinct-host capture | 0.0556 | 0.0610 |

Calls were 20 fresh mock captures, 20 cache hits, 160 distinct-host mock
captures, 20 initial-tailor captures, zero resume captures, and zero resume
proposal calls. Provider counters were 14 observed/invoked/unique contexts,
266 cache hits, and zero coalesced waits; deterministic provider p50/p95 was
0.000048 s / 0.000058 s. Parallel-to-sequential p50/p95 was 0.2564 / 0.2754,
below the unchanged 0.50 target. All 20 initial and 20 resumed outcomes were
`awaiting_approval`; none were blocked.

#### Clean artifact and installed-runtime boundary

| Artifact | SHA-256 |
|---|---|
| `/tmp/ats-stream-bound-wheel.nzDoQe/tailoring_ats_cvs-1.0.0b4-py3-none-any.whl` | `49317e6cdf099cbac6c25c9f614c9ccfeca1ab68500deae323365eece1e23cc5` |
| `/tmp/ats-stream-bound-wheel.nzDoQe/tailoring_ats_cvs-1.0.0b4.tar.gz` | `ada4dff7674dd40eca7ac4254cbcb48a8072fabe719e4bc09045a86e0c9281f6` |

The wheel was installed only into
`/tmp/ats-stream-bound-wheel-env.JPPzKa/venv` and invoked from `/tmp`. Its
site-packages executable passed help, strict doctor, the schema-3/eight-case
smoke benchmark (hard-gate accuracy 1.0, zero unsafe rewrites), default and
non-default port assertions, and the supplied source PDF's read-only format
audit (873 words, 99 lines, low risk). Both thin adapters passed strict doctor
through temporary `ATS_AGENT_EXECUTABLE_OVERRIDE`.

The packaged CLI completed the exact cross-process fixture sequence `tailor`
→ explicit digest-bound `approve` → `tailor --approve-from` at
`/tmp/ats-stream-bound-wheel-tailor.K6MnYL/`. It produced a distinct output
and receipt with `content_validation: verified`, `rendered_layout: unverified`,
`delivery_ready: false`, and `source_overwrite: false`; therefore it makes no
unsupported layout/delivery claim. The repository fixture source was not
overwritten.

The same clean wheel captured IANA reserved domains as
`scrapling_public_https` to
`/tmp/ats-stream-bound-wheel-live.DVZoai/iana-reserved-domains.txt`: 2,660
bytes, SHA-256
`532550a9c1d637396e5b6164d9593f6ee5cdb50dfffcaad0fe400178f57403ae`.
This is generic transport evidence only, not job research, candidate evidence,
or a live provider measurement. Its in-memory 64-byte boundary probe returned
the precise oversized-response error and left no output file.

The current checkout's `ats-agent doctor --strict` passes on source SHA
`944dae2d82bdde06f1e359094cda88688c6ed1bb501a3d917adbc264fc0e2b26`.
The separately managed `/Users/raghav/.local/bin/ats-agent` remains version
`1.0.0b4`, passes strict doctor, and reports its older source SHA
`fb4fc67af048e55eb11049bb7e623a59b8358276eaccfdf615eb050b3233d52e`.
It has not been upgraded. A module-level comparison with the clean wheel found
six changed modules (`boards.py`, `capture.py`, `job_research.py`,
`orchestrator.py`, `providers.py`, and `workflow.py`) and 29 unchanged Python
modules; version text alone therefore cannot identify the tested behavior.
The wheel and sdist were re-hashed again at the final upgrade boundary and
matched the two SHA-256 values above. A fresh managed-CLI strict doctor still
reported the older source SHA and passed; no managed installation was changed.

Reproduce local verification without installing the managed CLI:

```bash
uv -q run --isolated --extra dev --extra documents -- ruff check src tests scripts
uv -q run --isolated --extra dev --extra documents -- mypy src/ats_agent
# Run the unchanged Test, benchmark, and CLI workflow with branch coverage block
# from .github/workflows/ci.yml; branch=True is configured in pyproject.toml.
uv -q run --isolated --extra dev --extra documents -- python scripts/check_benchmark.py
uv -q run --isolated --extra dev --extra documents -- python scripts/validate_agent_adapters.py
uv -q run --isolated --extra dev --extra documents -- python scripts/perf_batch_benchmark.py > /tmp/ats-performance-report.json
uv -q run --isolated --extra dev --extra documents -- bandit -r src/ats_agent -q -ll
uv -q run --isolated --extra dev --extra documents -- pip-audit --local
uv -q run --isolated --extra dev --extra documents -- python -m build --outdir "$(mktemp -d /tmp/ats-wheel.XXXXXX)"
```

#### Fresh full-time job discovery and official-board check — 2026-09-06

The user corrected scope to **jobs, not internships**. A bounded, live
discovery pass used the two enabled public search CLIs in
`/Users/raghav/Documents/Dev_Projects/ai-job-search` (LinkedIn public search
and Freehire), then opened only promising employer ATS pages. No job-search
state, application tracker, candidate artifact, `ats-agent prepare`, approval,
apply, or portal submission was written. Search results and posting text were
treated as untrusted role requirements, never as candidate evidence.

The current short list below is a lead ranking, not an authorization to apply
or a claim that the CV proves every requirement. It weights the supplied CV's
finance, Python/SQL, automation, AI-systems, stakeholder, and operations
evidence against the live posting. Behavioural fit is not scored as established
because no behavioural self-report is available.

| Rank | Current full-time lead | Evidence and honest fit read | Decision boundary |
|---:|---|---|---|
| 1 | [Marketing Operations & AI Automation Coordinator — Better](https://jobs.ashbyhq.com/better-mortgage/8b7bdc9a-e05d-4783-8d9f-1f5d3c26b4e3) | The current employer-owned Ashby result reports Gurugram, **Full time**, and **Remote**. The role directly overlaps with AI workflow automation, GitHub/Supabase/Vercel, Canva, finance/regulated-industry context, reporting, and QA. Gaps: it asks for 2+ years of relevant marketing/technology experience plus hands-on Airtable, Zapier/n8n, Smartsheet, Google Analytics, CRM, and campaign-tool evidence not established by the supplied CV. | Best role-alignment lead; reopen the employer page immediately before any proposal and only proceed after the shared full-time/work-authorisation gates. |
| 2 | [Product Operations Analyst — Teikametrics](https://jobs.lever.co/teikametrics/b144b9bc-9d02-4b13-88f0-44b431476c7c) | The employer's active Lever board currently labels it **India / Remote**, **Full-time**, and remote. Product/engineering/customer workflow, SQL, analysis, incident discipline, and AI-product context align. Gaps: the posting explicitly asks for 2–3 years in technical SaaS plus hands-on technical support/troubleshooting; e-commerce marketplace experience is a plus, and Bangalore is preferred. Those experience claims are not established by the source CV. | Viable stretch only; do not imply the required SaaS/support history or claim Bangalore availability. |
| 3 | [Market Data Operations Analyst — Numerix](https://job-boards.greenhouse.io/numerix/jobs/5406676008) | The employer's active Greenhouse page says **Remote - India**, fully remote for people authorized to work in India. It matches finance, Excel, Python/SQL, data-quality/process automation, and operations evidence. Gaps: it asks for a leading engineering degree or equivalent professional experience, derivatives/market-data knowledge, troubleshooting, and possible 3:00 PM–11:30 PM MST shifts. The supplied CV does not establish the degree alternative, professional-equivalence, derivatives depth, India work authorization, or that schedule. | Strong subject-matter match but a qualification/schedule stretch; clarify those hard gates before any `prepare`. |

The discovery pass also **excluded** the following rather than padding the
shortlist:

- Highstreet's seemingly entry-level Business Financial Analyst was returned
  with `employment_type: internship`; it is outside the user's full-time-only
  scope.
- YipitData's current-looking Data QA page had an explicit start deadline no
  later than June 2025; an open form alone is not evidence that the job remains
  live.
- Wadhwani AI Global's Associate Product Manager and Human Archive's Founder's
  Office are full-time leads but the observed descriptions require Delhi/field
  travel or India-wide field operations and do not establish remote-only
  eligibility. They remain out of the current remote-only shortlist.
- Fresh Prints/Frontier remote operations leads currently require 2–4+ years
  of executive or sales-operations history and US-hours full-time work; they
  are lower-fit backups, not recommended ahead of the three above.

Reproduce the bounded discovery without submitting anything:

```bash
cd /Users/raghav/Documents/Dev_Projects/ai-job-search
bun run .agents/skills/linkedin-search/cli/src/cli.ts search --query "AI product associate" --location Remote --remote remote --jobage 14 --limit 10 --format json
bun run .agents/skills/linkedin-search/cli/src/cli.ts search --query "product operations associate" --location Remote --remote remote --jobage 14 --limit 10 --format json
bun run .agents/skills/freehire-search/cli/src/cli.ts search --query "AI operations" --remote remote --country IN --jobage 14 --limit 10 --format table
bun run .agents/skills/freehire-search/cli/src/cli.ts search --query "business operations" --remote remote --country IN --jobage 14 --limit 10 --format table
```

Each employer board must be reopened and rechecked for open status, work mode,
location, and eligibility immediately before a candidate-specific workflow.
The descriptions above are discovery evidence only; `ats-agent` remains the
sole engine for a provenance-preserving capture, evidence map, proposal,
digest-bound approval, application document, and validation.

#### Employer-board status refresh — 2026-09-08

The three ranked leads were re-opened against their employer-owned boards on
2026-09-08, with no login, application-form entry, tracker mutation, or
candidate artifact:

| Lead | Current official-board result | Ranking consequence |
|---|---|---|
| Better — Marketing Operations & AI Automation Coordinator | The current employer Ashby result explicitly reports **Gurugram, Haryana**, **Full time**, and **Remote**. The page itself continues to ask for 2+ years and the specific marketing-automation stack recorded above. | Remains rank 1. It is current and genuinely within the remote/full-time search; its experience/tool gaps remain real. |
| Teikametrics — Product Operations Analyst | The active Lever board still reports **India / Remote**, **Full-time**, and remote; the application page is live. It still names 2–3 years technical SaaS support/troubleshooting, SQL, and a Bangalore preference. | Remains a genuine but honest stretch rather than a substitute for Better. |
| Numerix — Market Data Operations Analyst | The active Greenhouse opening is still listed on Numerix's current openings page as **Remote - India**. Its posting still requires Indian work authorization, the degree-or-equivalent route, market-data/derivatives knowledge, and potential US-shift work. | Remains a finance/technical stretch; its live status does not waive the stated hard gates. |

This refresh removed the previous caveat that Better's current work-mode fields
were only independently indexed. It does **not** convert job text into
candidate evidence or authorize an application. The user must still choose a
role and satisfy the candidate-specific gates below before `ats-agent` may
prepare anything.

#### Exact remaining blockers; overall goal remains open

1. Receive fresh explicit user approval before replacing the managed
   `ats-agent` with the re-hashed wheel above; equal version text is not a
   sufficient artifact identity.
2. Before a real full-time application workflow, provide a selected job,
   candidate-confirmed standard full-time availability, location/work
   authorisation, and a user-selected run directory. Job text remains
   non-candidate evidence.
3. Run a fresh `ats-agent prepare`, then explicitly approve each exact
   `change-id:variant` against its persisted digest before apply. Inspect the
   resulting real document's rendered layout before delivery.
4. Provide a configured live/paid provider and explicit cost authorization for
   live provider latency and cost measurement.
5. Hosted CI for this dirty, unpushed checkout, a protected private holdout,
   blinded human evaluation, and protected release/publication authority are
   still external gates.

No benchmark, coverage, security, approval, provenance, source-protection, or
document-validation gate was lowered or silently marked complete.

### Provider-configuration cache binding and artifact refresh — 2026-09-06 (historical; superseded)

This historical record is retained for auditability. The preceding streamed-body
boundary record supersedes its source identity, wheel paths, timing
figures, and transport probe after closing the remaining direct-capture input
limit. At the time of this earlier audit, the checkout engine SHA-256 was
`6f30ab405587a24189ce428f5929ec1fbe0a423356fe604e1557c1ec0ab8a41c`.
The managed CLI was not changed.

#### Shared-root-cause repair

`RewriteCache._key` previously used only the provider type, ID, and version,
although resumability already bound work to a provider-configuration digest.
Two different configurations of a same-named provider could therefore share a
rewrite result within one run. The cache now uses `rewrite_provider_identity`,
including a SHA-256 of configuration representation rather than persisting the
configuration itself. It snapshots that identity before the first invocation:
some deterministic test providers increment a `calls` member in `__dict__`,
which otherwise would make their own later identical requests look different.
The per-batch cache retains the provider object with that snapshot to prevent
an `id()` reuse from joining a different provider. The ordinary same-provider,
same-context coalescing behavior, defensive copies, error wake-up, evidence
validation, output limits, and timeout contract remain unchanged.

`tests/test_provider_benchmark_edges.py::ProviderBenchmarkEdgeTests.test_rewrite_cache_does_not_share_same_named_different_provider_configurations`
proves that distinct configurations each invoke their own provider; the
existing concurrent duplicate-context test still proves one invocation and a
coalesced waiter for an equal provider/context. The full suite also retained
the interrupted `research-jobs` recovery, source/input digest binding, public
capture, journal, document, and adapter regressions.

#### Requirement and verification evidence

| Requirement | Current evidence | Accurate limit |
|---|---|---|
| Public-network hardening and capture deduplication | Existing bounded, public-HTTPS/no-proxy/no-redirect capture paths remain covered; this refresh adds default-port (`:443`) canonicalisation to the IDNA cache/batch regression. A fresh IANA transport probe completed through `scrapling_public_https`. | The probe is a generic public page, not job research, candidate evidence, or a live-provider measurement. OS DNS cancellation and pre-write streaming-byte observation remain explicitly unclaimed. |
| Interrupted research-job recovery | The atomic schema journal, digest-bound recovery, visible corrupt-record block, and zero-work resume checks remained in the full suite. | A real job run still requires the user's selected role/run directory and applicable authorization. |
| Provider-call deduplication | The cache now differentiates configured provider instances as well as coalescing equal contexts. The measured deterministic run reports 14 invocations for 14 unique contexts, 266 cache hits, and zero waits. | No paid or external provider was configured or called. |
| Approval and source-CV protection | A transient `uv run --isolated` interpreter pathname no longer invalidates a persisted approval, while an engine source-SHA change still does. The clean wheel completed a separate-process prepare → explicit approval → persisted-approval replay. | This used only repository fixtures; no real candidate proposal, approval, or document output was created. |
| Truthful document validation | The packaged fixture receipt records content validation `verified`, rendered layout `unverified`, `delivery_ready: false`, and `source_overwrite: false`. | A real candidate output still requires human rendered-layout inspection before delivery. |

The full unchanged branch-coverage/CLI sequence from `.github/workflows/ci.yml`
was rerun after this fix at `/tmp/ats-provider-id-fullcoverage.AZLM7r`:

- **338 tests** passed in **11.177 s**.
- Coverage remained exactly **90%** with the existing gate: 5,491 statements,
  440 missed, 1,936 branches, and 286 partial branches.
- Ruff, Mypy for 35 source files, the 270 frozen benchmark cases, benchmark
  diversity, skill/release-tree checks, adapter validation, reproducible
  adapter-bundle verification, compileall, Bandit `-ll`, local `pip-audit`,
  and the public prerelease check passed at
  `/tmp/ats-provider-id-quality.o8OF5E`.
- The protected command `python scripts/release_check.py --require-holdout`
  exited **1** with `stable releases must pass the protected holdout` because
  no private holdout was supplied. That is the intended fail-closed result,
  not a passing release gate.

Adapter bundle hashes remain
`361d3f0680bdcf9f7fa7d292e361eca4d6429eef8d52d2bb412e6ffdc4c6edb7`
(skill) and
`a1ce9618dda48a6853a129a9e914fb8936570a64da63fbd517bb7b710228b03b`
(plugin).

#### Reproducible timing and call-count record

`/tmp/ats-provider-id-perf.G8LQga/report.json` is a fresh, passing
20-repetition, 20-role **synthetic/offline** measurement for this exact source
SHA. It uses frozen local inputs, a 50 ms mocked capture, and the deterministic
provider; it is not a live job-site, external-provider, or candidate-document
claim. Recorded one-minute host load averaged 3.86 before and 6.15 after the
run; thresholds were unchanged.

| Stage | p50 seconds | p95 seconds |
|---|---:|---:|
| Warm prepare plus review | 0.3070 | 0.5125 |
| Time to first proposal | 0.2899 | 0.4827 |
| Ten roles plus review | 2.1681 | 3.5834 |
| Twenty roles plus review | 4.2293 | 6.9505 |
| Analysis | 3.9085 | 6.4233 |
| Review writing | 0.3188 | 0.5270 |
| Cold prepare | 0.6208 | 0.9286 |
| Fresh mocked capture | 0.0570 | 0.0622 |
| Capture-cache hit | 0.0005 | 0.0006 |
| Explicit synthetic apply | 0.0363 | 0.0378 |
| Parse/audit validation | 0.0025 | 0.0027 |
| Resume twenty unchanged roles | 0.2382 | 0.2450 |
| Sequential distinct-host capture | 0.2324 | 0.2422 |
| Four-worker distinct-host capture | 0.0609 | 0.0619 |

Measured calls: 20 fresh mock captures, 20 cache hits, 160 distinct-host mock
captures, 20 initial-tailor captures, zero resume captures, and zero resume
proposal calls. Provider counters: 14 observed/invoked contexts, 266 cache
hits, zero coalesced waits, 14 unique contexts, and 0.000085 s / 0.000107 s
provider p50/p95. The parallel-to-sequential ratio was 0.2632 p50 and 0.2747
p95, under the unchanged 0.50 target. All 20 initial and all 20 resumed roles
were `awaiting_approval`, with zero blocked outcomes.

#### Clean artifact and installed-runtime boundary

| Artifact | SHA-256 |
|---|---|
| `/tmp/ats-provider-id-wheel.AlaNmy/tailoring_ats_cvs-1.0.0b4-py3-none-any.whl` | `5dfa8ba460265dee9b162c942b593da5b9bdd7aa0379275cfeaff6bccb2a8217` |
| `/tmp/ats-provider-id-wheel.AlaNmy/tailoring_ats_cvs-1.0.0b4.tar.gz` | `449cdd64b3aaec6a963b11266fb93d06ac2fe54f1889c22e2c3f2dd2a876868d` |

The wheel was built into that temporary directory, installed only into
`/tmp/ats-provider-id-wheel-env.9zwDYe/venv`, and invoked from `/tmp`. Its
site-packages executable passed help, strict doctor, the schema-3/eight-case
smoke benchmark, default/non-default port assertions, and the supplied
source-PDF's read-only format audit. Both thin adapters passed strict doctor
through temporary `ATS_AGENT_EXECUTABLE_OVERRIDE`. The clean wheel also passed
the exact separate-process fixture sequence `tailor` → explicit digest-bound
`approve` → `tailor --approve-from` at
`/tmp/ats-provider-id-wheel-tailor.jMMGvC/`: it wrote a distinct output and
receipt with verified content, but correctly retained rendered layout as
unverified and not delivery-ready. The source fixture was not overwritten.

On 2026-09-06, the current source captured
`https://www.iana.org/domains/reserved` to
`/tmp/ats-provider-id-live.jo7dUV/iana-reserved-domains.txt` as
`scrapling_public_https`, 2,660 bytes, SHA-256
`532550a9c1d637396e5b6164d9593f6ee5cdb50dfffcaad0fe400178f57403ae`.
This is generic transport evidence only.

Current-source `ats-agent doctor --strict` passes with source SHA
`6f30ab405587a24189ce428f5929ec1fbe0a423356fe604e1557c1ec0ab8a41c`.
The separately managed `/Users/raghav/.local/bin/ats-agent` remains version
`1.0.0b4`, passes strict doctor, and reports its older source SHA
`fb4fc67af048e55eb11049bb7e623a59b8358276eaccfdf615eb050b3233d52e`.
It has not been upgraded.

Reproduce the local gates without installing the managed CLI:

```bash
uv run --isolated --extra dev --extra documents -- ruff check src tests scripts
uv run --isolated --extra dev --extra documents -- mypy src/ats_agent
# Run the unchanged Test, benchmark, and CLI workflow with branch coverage block
# in .github/workflows/ci.yml; branch=True is configured in pyproject.toml.
uv run --isolated --extra dev --extra documents -- python scripts/check_benchmark.py
uv run --isolated --extra dev --extra documents -- python scripts/validate_agent_adapters.py
uv run --isolated --extra dev --extra documents -- python scripts/perf_batch_benchmark.py
uv run --isolated --extra dev --extra documents -- python -m build --outdir "$(mktemp -d /tmp/ats-wheel.XXXXXX)"
```

#### Exact remaining blockers; overall goal remains open

1. Re-hash the exact wheel above and receive fresh explicit user approval
   before replacing the managed `ats-agent`; equal version text is not a
   sufficient artifact identity.
2. Before a real full-time application workflow, provide a selected job,
   candidate-confirmed standard full-time availability, location/work
   authorisation, and a user-selected run directory. Job text remains
   non-candidate evidence.
3. Run a fresh `ats-agent prepare`, then explicitly approve each exact
   `change-id:variant` against its persisted digest before apply. Inspect the
   resulting real document's rendered layout before delivery.
4. Provide a configured live/paid provider and explicit cost authorization for
   live provider latency and cost measurement.
5. Hosted CI for this dirty, unpushed checkout, a protected private holdout,
   blinded human evaluation, and protected release/publication authority are
   still external gates.

No benchmark, coverage, security, approval, provenance, source-protection, or
document-validation gate was lowered or silently marked complete.

### Stable engine-identity resume and default-port canonicalisation — 2026-09-06 (historical; superseded)

This historical record is retained for auditability. The preceding
provider-configuration cache-binding record supersedes its source identity,
artifact paths, timing figures, and transport evidence after a final shared
cache fix. At the time of this earlier audit, the current source SHA-256 was
`6be97de137d8ff13da27284a4469e4aa5709cee5e97a09badc10e7fc8be16839`.

#### Approval-resume root-cause repair

The exact branch workflow exposed a real failure in the required two-process
`tailor` path: a persisted digest-bound approval was rejected immediately with
`inputs or engine changed; prepare a fresh review before approving`. Each
`uv run --isolated` invocation reports a new temporary virtual-environment
pathname in `doctor.runtime.interpreter`; that volatile pathname had been
included in both the run `source_digest` and per-role `intake_digest`.

`orchestrator._engine_identity` now binds the approval path to the package
name/version, full Python version, resolved engine path, source SHA-256, and
optional-document dependency availability. It intentionally excludes only the
ephemeral isolated-venv pathname. Missing or malformed identity fields fail
closed rather than falling back to a version string. The new regression proves
that two different temporary interpreter paths with the same engine identity
can apply a persisted approval, while changing the source SHA still blocks it.
This preserves exact proposal-digest binding, candidate-input hashes, provider
configuration binding, approval selections, source-CV protection, and
apply-time validation.

The same audit also found that the shared canonical URL helper treated
`https://host/path` and the standards-equivalent
`https://host:443/path` as separate cache and batch keys. It now elides only
the default HTTPS port; non-default ports remain distinct. The regression
exercises IDNA, explicit/implicit port cache reuse, one batched capture, and
materialisation to all requested destinations.

#### Current local verification

The unmodified `Test, benchmark, and CLI workflow with branch coverage` block
from `.github/workflows/ci.yml` was rerun in one isolated environment at
`/tmp/ats-stable-id-fullcoverage.ycdpWi`. It completed the exact CLI sequence
including propose, review, explicit variant selection, approve, apply,
validate, initial `tailor`, persisted-approval `tailor`, and smoke benchmark.
It produced all required review, approval, output, receipt, and smoke artifacts.

- **337 tests** passed in **11.541 s**.
- Branch coverage remained **90%**: 5,482 statements, 440 missed, 1,934
  branches, and 286 partial branches. The threshold was not changed.
- Ruff, Mypy (35 source files), the frozen 270-case benchmark, benchmark
  diversity, skill and release-tree checks, adapter validation, reproducible
  bundle verification, compileall, Bandit `-ll`, local pip-audit, and the
  public prerelease check all passed again. Adapter bundle hashes remain
  `361d3f0680bdcf9f7fa7d292e361eca4d6429eef8d52d2bb412e6ffdc4c6edb7`
  (skill) and
  `a1ce9618dda48a6853a129a9e914fb8936570a64da63fbd517bb7b710228b03b`
  (plugin).
- `uv run --isolated --extra dev --extra documents -- python
  scripts/release_check.py --require-holdout` exited **1** with the required
  `stable releases must pass the protected holdout` message because no private
  holdout was supplied. This remains a fail-closed external gate, not a pass.

Reproduce the current local gates with:

```bash
uv run --isolated --extra dev --extra documents -- ruff check src tests scripts
uv run --isolated --extra dev --extra documents -- mypy src/ats_agent
# Run the complete branch-coverage/CLI block in .github/workflows/ci.yml unchanged.
uv run --isolated --extra dev --extra documents -- python scripts/check_benchmark.py
uv run --isolated --extra dev --extra documents -- python scripts/validate_agent_adapters.py
uv run --isolated --extra dev --extra documents -- python scripts/perf_batch_benchmark.py
uv run --isolated --extra dev --extra documents -- python -m build --outdir "$(mktemp -d /tmp/ats-wheel.XXXXXX)"
```

#### Reproducible performance measurement

`/tmp/ats-stable-id-perf.MQHrVz/report.json` is a fresh, passing 20-run,
20-role **synthetic/offline** report for this source SHA. It uses the frozen
two-page DOCX, five local evidence files, 20 local role descriptions, 50 ms
mocked capture, and the deterministic provider; it makes no live job-site or
paid-provider claim. The host's recorded one-minute load averages were 7.50
before and 27.65 after the run. Thresholds were unchanged.

| Stage | p50 seconds | p95 seconds |
|---|---:|---:|
| Warm prepare plus review | 0.4482 | 0.7536 |
| Time to first proposal | 0.3685 | 0.6631 |
| Ten roles plus review | 2.9296 | 5.7674 |
| Twenty roles plus review | 6.4683 | 14.9444 |
| Analysis | 5.9463 | 13.1329 |
| Review writing | 0.5068 | 1.3626 |
| Cold prepare | 0.7542 | 1.5017 |
| Fresh mocked capture | 0.0625 | 0.0674 |
| Capture-cache hit | 0.0012 | 0.0016 |
| Explicit synthetic apply | 0.0632 | 0.0720 |
| Parse/audit validation | 0.0042 | 0.0053 |
| Resume twenty unchanged roles | 0.2542 | 0.4024 |
| Sequential distinct-host capture | 0.2308 | 0.2428 |
| Four-worker distinct-host capture | 0.0590 | 0.0622 |

Call counts were 20 fresh mock captures, 20 cache hits, 160 distinct-host mock
captures, 20 initial-tailor captures, zero resume captures, and zero resume
proposal calls. Provider counters were 14 observed/invoked contexts, 266 cache
hits, zero coalesced waits, and 14 unique contexts; provider p50/p95 was
0.000130 s / 0.000537 s. The parallel-to-sequential ratio was 0.2580 p50 and
0.2692 p95, below the unchanged 0.50 target. All 20 initial and all 20 resumed
roles were `awaiting_approval`, with zero blocked outcomes.

#### Current wheel and live transport check; not installed

| Artifact | SHA-256 |
|---|---|
| `/tmp/ats-stable-id-wheel.9FTXho/tailoring_ats_cvs-1.0.0b4-py3-none-any.whl` | `9dab43d758290fdcc6b05540bd85e025dd8ff5b455ee79dd6323a507416b9cef` |
| `/tmp/ats-stable-id-wheel.9FTXho/tailoring_ats_cvs-1.0.0b4.tar.gz` | `235da942e045c922f3121e224d52a2a9718d9ff20f58b113fd9ad3d9a3b0d6db` |

The wheel was installed only into
`/tmp/ats-stable-id-wheel-env.kmjGRE/venv`. From `/tmp`, its site-packages
entry point passed help, strict doctor, schema-3/eight-case smoke benchmark,
default-port canonicalisation assertions, and the supplied PDF's read-only
format audit (873 words, 99 lines, low risk, informational F5). Both thin
adapters passed strict doctor through temporary
`ATS_AGENT_EXECUTABLE_OVERRIDE`. The packaged CLI also passed the exact
two-process `tailor` → explicit digest-bound `approve` → `tailor
--approve-from` replay, producing a distinct validated output and receipt at
`/tmp/ats-stable-id-wheel-tailor.G6Mci7/`; no source CV was changed. The only
build warning was the pre-existing forward-looking setuptools license-classifier
deprecation.

A fresh generic IANA reserved-domains capture through the current source
completed as `scrapling_public_https`, 2,660 bytes, SHA-256
`532550a9c1d637396e5b6164d9593f6ee5cdb50dfffcaad0fe400178f57403ae`, at
`/tmp/ats-stable-id-live.qIZfzF/iana-reserved-domains.txt`. It is public
transport evidence only, not a job draft, candidate artifact, or live-provider
measurement.

The managed CLI remains version `1.0.0b4` on the older source SHA-256
`fb4fc67af048e55eb11049bb7e623a59b8358276eaccfdf615eb050b3233d52e`; its
strict doctor still passes and it was not modified.

#### Exact remaining blockers; overall goal remains open

1. Re-hash the exact wheel above and obtain fresh explicit user approval before
   installing it into the managed `ats-agent` environment.
2. A selected full-time job, candidate-confirmed standard full-time
   availability, location/work authorisation, and a user-selected candidate
   run directory are required before creating a real proposal. Job text is not
   candidate evidence.
3. After fresh `ats-agent prepare`, the candidate must explicitly select each
   `change-id:variant` against that exact persisted digest before apply. A
   resulting real document still requires human rendered-layout inspection.
4. Live paid/external-provider latency and cost require a configured provider
   and explicit authorisation.
5. Hosted CI for the dirty unpushed checkout, protected private holdout,
   blinded human evaluation, and protected publication remain external gates.

No local, manual, or external gate has been silently waived or marked complete
without its own evidence.

## Final current status — 2026-09-08

This final status supersedes every earlier historical "current" record in this
document. The detailed evidence is in “Final local refresh and remaining
external gates” above; it remains authoritative even though older execution
records follow it for audit history.

- Current source engine SHA-256:
  `e7ebd4808d4b4b36a0cb67905010f7d3ad72556fea236472ef2e3e8be80d738d`.
  Local lint, typing, 346-test branch suite, unchanged `--fail-under=90`
  coverage gate, frozen 270-case benchmark, adapters, static security checks,
  package build, and clean-wheel execution passed.
- The 20-run synthetic/offline performance report is
  `/tmp/ats-final-perf.Ub0MeK/report.json`; it records cold/warm preparation,
  capture/cache, review, apply, validation, resume, provider-call, and
  bounded-parallelism measurements. It is not a paid-provider or real-job-site
  measurement.
- The tested but uninstalled wheel is
  `/tmp/ats-final-wheel.cLDbV2/tailoring_ats_cvs-1.0.0b4-py3-none-any.whl`,
  SHA-256 `9538d3dd25428ea791f095dba008343d91d91dae1b3cdcc079841baa6b7774df`.
  The managed CLI remains on the older engine SHA above; it must not be
  replaced without explicit approval of this exact digest.
- The completed partial security scan found one medium snapshot-era derived
  receipt-symlink source-overwrite path. The current shared atomic-write,
  path-alias, and run-directory-separation remediation passed focused and full
  regression checks; the historical scan correctly remains a partial snapshot
  report rather than a claim of exhaustive current-tree security coverage.
- Fresh official-board research identified full-time roles only: Paytm APM
  Lending is the strongest role-fit lead, followed conditionally by Better
  Marketing Operations & AI Automation, Numerix Market Data Operations, and
  Teikametrics Product Operations. No internship was selected, no application
  was submitted, and no real CV proposal was generated.

The overall goal is **not complete**: explicit managed-install approval,
candidate-confirmed full-time availability and India work authorisation, one
selected official job, a separate empty run directory, explicit per-change
approval after `prepare`, real rendered-layout review, paid-provider authority
for live metrics, protected holdout/blinded evaluation, hosted CI, and release
authority are still required. None has been inferred or waived.
