# ATS Agent Capability Upgrade Plan

## Outcome

Turn the current approval-first CLI into a reliable workflow that:

1. Accepts a candidate CV, supporting evidence, and an unfiltered job list produced by AI Job Search.
2. Captures each public job page with ordinary Scrapling and records source quality and failures.
3. Builds a sourced role dossier for every job, including responsibilities, qualifications, eligibility terms, company context, and ATS-relevant terminology.
4. Maps every requirement to candidate evidence, proposes truthful role-specific wording, and recommends genuine gaps to close.
5. Applies only explicitly approved changes to a new DOCX while preserving the original document's structure and styling.
6. Validates factual integrity, keyword coverage, document readability, and format fidelity after application.

The product must improve honest keyword coverage. It must not promise passage through an employer's ATS, invent qualifications, hide keywords, filter inconvenient roles out of the report, or submit applications.

## Source of truth

Implement this plan in the clean worktree:

`/Users/raghav/dev/tailoring-ats-cvs-agent-native`

Baseline:

- Branch: `agent/public-job-research`
- Commit: `e5bcc71a46bb827726d29fc24d2b294e4463076d`
- Installed CLI provenance: local installation from this worktree
- Installed version: `1.0.0b3`

Do not implement this plan in `/Users/raghav/dev/tailoring-ats-cvs`; that worktree is on the older `codex/trustworthy-v1` branch and contains extensive staged and unstaged work.

Before implementation, create a new branch from the latest reviewed version of `agent/public-job-research`. Do not overwrite or clean either existing worktree.

## Live-pilot findings that this plan must fix

The 2026-08-17 pilot used the supplied SRCC CV and live TikTok, Zurich, and CheQ roles.

| Finding | Observed result | Required behaviour |
|---|---|---|
| Proposal digest | All three persisted proposals failed their own digest verification | Every proposal must verify before it is shown as approvable |
| Digest root cause | Digest was computed before typed serialization; review metadata was then written into the canonical JSON | Hash the final canonical proposal and keep review-only metadata outside it |
| Duplicate changes | TikTok and CheQ proposed skills/projects already present in the CV | Suppress exact and normalized duplicates before proposal creation |
| Conflicting evidence | Supporting profile said CGPA 8.82; source CV said 8.55 | Record a conflict and block any affected change until the candidate resolves it |
| Requirement depth | Zurich produced only one normalized requirement | Preserve and map all material responsibilities, qualifications, tools, and eligibility terms |
| Fragmented requirements | TikTok produced sentence fragments such as `SQL, A/B testing...` | Clean captured text and keep complete source-backed requirement clauses |
| Scrapling fallback | CheQ's employer-page capture produced no extractable text | Fail visibly or accept a labelled aggregator fallback; never present it as official capture |
| Change usefulness | Generated changes were technically supported but added no new value | Require measurable coverage or clarity improvement for every proposed change |
| Format fidelity | Preserve mode retained the package but did not prove layout constancy | Add a strict format lock and structural fingerprint before claiming format preservation |
| Synthetic tests | Smoke benchmark and strict doctor passed while the real path failed | Add persisted-DOCX and installed-wheel regression tests using real workflow shapes |

## Product contract

### Inputs

- One source CV: DOCX preferred; PDF is analysis-only unless an editable matching DOCX is supplied.
- One stable candidate ID.
- Zero or more candidate-evidence files.
- An unfiltered AI Job Search export using the existing public-jobs JSON shape.
- Optional role dossiers produced by AI Job Search, with every extracted fact bound to captured source text.
- Optional official company-context URLs.

### Outputs per job

- Capture manifest with URL, timestamp, method, SHA-256, source type, and extraction status.
- Role dossier with complete sourced requirements and eligibility warnings.
- Requirement-to-evidence matrix.
- Exact-keyword coverage before and after each proposed variant.
- Supported changes with evidence IDs, source anchors, variants, and expected coverage gain.
- Unsupported, conflicting, and eligibility gaps with next actions.
- Full local review bundle.
- After explicit approval only: a new tailored DOCX, validation report, diff, hashes, and applied-change receipt.

### Authority boundary

```text
DISCOVER -> CAPTURE -> ANALYSE -> PROPOSE -> EXPLICIT APPROVAL -> APPLY -> VALIDATE
```

- Discovery, capture, analysis, and proposal creation are read-only with respect to the CV and job tracker.
- No role is excluded because of location, seniority, work authorization, language, or graduation date. Those facts remain visible as warnings or hard gates.
- Approval must identify the proposal digest, change IDs, and variants.
- Application writes a new file and never overwrites the source.
- Submission, outreach, login, and tracker mutation remain outside this tool.

## Architecture

Reuse the existing single CLI pipeline. Do not add an agent framework, MCP server, database, or scheduler.

```text
AI Job Search
  -> unfiltered jobs.json + optional sourced role-dossier.json
  -> ats-agent research-jobs
       -> ordinary Scrapling capture
       -> capture/source manifest
       -> validated role dossier
       -> requirement extraction and evidence mapping
       -> evidence conflicts and hard gates
       -> deterministic or explicitly selected command rewrite provider
       -> duplicate/value/format-budget validation
       -> canonical digest-bound proposal
       -> Markdown + HTML review
  -> explicit change and variant approval
  -> transactional strict-preserve DOCX patch
  -> factual + keyword + structural + parser validation
  -> new DOCX + receipt
```

AI Job Search remains responsible for discovering and ranking jobs. Scrapling remains the public-page capture tool. `ats-agent` remains the only authority for candidate evidence, proposed wording, approval, document mutation, and validation.

## Milestone 0: Lock the baseline and pilot corpus

- [ ] Create a new implementation branch from the reviewed `agent/public-job-research` head.
- [ ] Record the installed CLI's version, direct URL, source commit, and `doctor --strict` result.
- [ ] Preserve the three local pilot bundles as private evaluation inputs; do not commit the candidate's PII.
- [ ] Create sanitized DOCX/JD/evidence fixtures that reproduce:
  - digest failure after prepare serialization;
  - source-versus-profile CGPA conflict;
  - existing-project and existing-skills duplicates;
  - sparse Zurich requirement extraction;
  - fragmented TikTok requirements;
  - empty CheQ direct capture plus labelled fallback.
- [ ] Capture the current full verification baseline before any implementation.

Acceptance:

- Current failures reproduce in focused tests.
- Sanitized fixtures contain no personal contact details or private candidate data.
- Existing tests are not weakened or deleted.

Suggested commit: `test: reproduce live CV workflow failures`

## Milestone 1: Make proposal integrity self-consistent

Primary files:

- `src/ats_agent/workflow.py`
- `src/ats_agent/models.py`
- `src/ats_agent/hashing.py`
- `src/ats_agent/review.py`
- `src/ats_agent/job_research.py`
- `tests/test_hash_binding.py`
- `tests/test_review_unified.py`
- `tests/test_job_research.py`

Tasks:

- [ ] Add one finalization path that validates/serializes the complete proposal first, computes the digest over that exact canonical JSON shape, adds the digest, and verifies it before returning.
- [ ] Ensure no production path computes a digest and then adds or defaults proposal fields.
- [ ] Write the canonical full proposal unchanged in `write_review_bundle`.
- [ ] Keep `review_mode` and `approval_disabled` in rendered review metadata, not in the approvable proposal JSON.
- [ ] Make redacted JSON a separate explicitly non-approvable artifact, or omit redacted proposal JSON; never reuse the canonical proposal filename for altered content.
- [ ] Route `research-jobs` additions such as capture provenance and coverage through the same proposal-finalization function.
- [ ] Verify the digest after writing and re-reading `proposal.json`; delete the incomplete run directory or mark it blocked if verification fails.
- [ ] Make `prepare` and `research-jobs` return a blocked status if their persisted proposal cannot verify.

Tests:

- [ ] `build_proposal -> JSON dump -> JSON load -> verify_proposal_digest` passes.
- [ ] Full `prepare` bundle verifies from disk.
- [ ] Redacted review cannot be approved.
- [ ] `research-jobs` proposal with research metadata verifies from disk.
- [ ] Any post-digest mutation still fails closed.
- [ ] Installed-wheel CLI repeats the same checks outside the source tree.

Acceptance: 100% of newly generated canonical proposals verify after persistence; tampering remains rejected.

Suggested commit: `fix: finalize proposals before digest binding`

## Milestone 2: Reject contradictions, duplicates, and no-value changes

Primary files:

- `src/ats_agent/evidence.py`
- `src/ats_agent/rewriting.py`
- `src/ats_agent/validation.py`
- `src/ats_agent/models.py`
- `tests/test_atomic_claims.py`
- `tests/test_claim_validation.py`
- `tests/test_section_placement.py`
- new focused conflict/deduplication tests

### Evidence conflict policy

- [ ] Introduce a small `evidence_conflicts` collection in the proposal.
- [ ] Treat the source CV as authoritative for facts already stated in that CV.
- [ ] Allow supporting evidence to add a fact only when the CV is silent and the source is candidate-scoped.
- [ ] Detect conflicting values for the same scoped fact, starting with CGPA/GPA, dates, graduation year, counts, money, percentages, work authorization, and employment status.
- [ ] Bind conflicts to evidence IDs and source spans.
- [ ] Mark affected changes unsupported or `blocked_conflict`; do not block unrelated changes.
- [ ] Require a newly supplied reconciled source before the fact can be changed. Do not resolve conflicts by source order or model choice.

### Duplicate and value checks

- [ ] Normalize whitespace, Markdown markers, punctuation, separators, and case before comparing supporting evidence with every CV fragment.
- [ ] Suppress exact duplicates and conservative normalized duplicates using the standard library.
- [ ] Reject a variant if its normalized text already exists elsewhere in the CV.
- [ ] Reject a change whose only effect is punctuation, Markdown-table syntax, or moving an existing keyword to a duplicate line.
- [ ] Require each proposed change to improve at least one supported requirement's visible coverage or materially improve clarity without changing meaning.
- [ ] Include the coverage delta and reason in each change record.
- [ ] Keep ambiguous near-duplicates as review-only warnings rather than inserting them automatically.

Acceptance against the pilot:

- CGPA remains 8.55 until explicitly reconciled.
- Existing RStack, Tender Export OS, Python/SQL, Excel, Figma, and Canva lines are not reinserted.
- No generated change uses Markdown-table text as a DOCX paragraph.
- Unsafe-change count is zero after proposal validation.

Suggested commit: `fix: block conflicting and duplicate CV evidence`

## Milestone 3: Build complete, sourced role dossiers

Primary files:

- `src/ats_agent/requirements.py`
- `src/ats_agent/job_research.py`
- `src/ats_agent/models.py`
- `tests/test_requirement_engine.py`
- `tests/test_job_research.py`
- Benchmark v3 role fixtures

Tasks:

- [ ] Clean captured page text before extraction: remove navigation noise, cookie text, repeated headings, and broken whitespace while retaining original offsets or source fragments.
- [ ] Represent material role requirements as complete clauses, not alias-triggered sentence fragments.
- [ ] Classify requirements as responsibility, skill/tool, education, experience, eligibility, availability, or preference.
- [ ] Preserve importance, source URL, capture SHA, source span, and exact supporting excerpt for every requirement.
- [ ] Extract all explicit eligibility facts even when the user requested no filtering; report them without excluding the role.
- [ ] Expand the deterministic ontology only for terms demonstrated by the pilot corpus, including:
  - AI agents, tool use, knowledge/SOP integration, conversation strategy, evaluation design, and A/B testing;
  - user research, usability, roadmap, backlog, proof of concept, prototyping, and scaling;
  - data annotation, golden datasets, AI-response quality, user feedback, RCA, issue tracking, dashboards, audits, and product analytics.
- [ ] Accept an optional AI Job Search role dossier containing additional requirements only when every item points to text present in a captured source.
- [ ] Validate dossier spans and reject invented, stale, or source-less requirements.
- [ ] Deduplicate overlapping deterministic and AI Job Search requirements while retaining the strongest source provenance.
- [ ] Keep company research separate from candidate evidence and separate from the job's mandatory requirements.

Pilot acceptance:

- TikTok requirements are complete clauses and distinguish undergraduate-or-master eligibility from a false master's-only gap.
- Zurich includes discovery, development, implementation, cross-functional work, user research, roadmap/backlog, data iteration, named AI tools, and 6-12 month availability.
- CheQ includes annotation, response evaluation, golden datasets, feedback/RCA, trackers/dashboards, spreadsheets, SQL, statistics, and fintech context.

Suggested commit: `feat: validate complete sourced role dossiers`

## Milestone 4: Make AI Job Search the discovery handoff

Primary files:

- `.agents/skills/tailor-cv/SKILL.md`
- `.claude-plugin/plugin.json` and `integrations/claude-code.md` (the Claude manifest reuses the same portable skill)
- `README.md`
- `docs/agent-adapters.md`
- `integrations/README.md`
- `src/ats_agent/job_research.py`
- adapter and job-research tests

Tasks:

- [ ] Document one canonical JSON interchange for AI Job Search with job ID, title, company, job URL, optional official context URLs, optional fallback description, and provenance.
- [ ] Update Codex and Claude instructions to call AI Job Search for discovery/ranking and export every selected role without eligibility filtering.
- [ ] Keep the current Career-Ops Markdown reader for backward compatibility, but remove it from the primary documented workflow.
- [ ] Do not copy AI Job Search ranking or portal logic into `ats-agent`.
- [ ] Include every job in the batch manifest, even when expired, inaccessible, ineligible, or blocked; distinguish `draft`, `blocked_capture`, `expired`, and `eligibility_warning` without silently dropping rows.
- [ ] Add candidate evidence paths and official context URLs to the batch command so each proposal uses the same verified candidate ledger.
- [ ] Make job-list and candidate files read-only; never mutate AI Job Search's `seen_jobs.json` or application tracker.

### Scrapling capture contract

- [ ] Keep ordinary public HTTPS capture, DNS/public-IP checks, no credentials, no stealth, no redirect following, no proxies, and bounded timeout.
- [ ] Reject empty or insufficient direct captures with a specific status.
- [ ] Permit an AI Job Search fallback description only when its source URL, provider, fetch date, and non-official status are recorded.
- [ ] Never label aggregator content as employer-confirmed.
- [ ] Capture official company context separately and retain per-source failures rather than collapsing the entire job.
- [ ] Record liveness evidence and research timestamp; require refresh before application when stale.

Acceptance:

- The nine-role unfiltered pilot list remains nine rows in the output manifest.
- CheQ uses a visible aggregator fallback and never claims a successful direct employer capture.
- One failed context URL does not erase a valid job description.
- No tracker or source-list mutation occurs.

Suggested commit: `feat: add AI Job Search research handoff`

## Milestone 5: Produce useful evidence-bounded rewrites

Primary files:

- `src/ats_agent/providers.py`
- `src/ats_agent/rewriting.py`
- `src/ats_agent/validation.py`
- `src/ats_agent/cli.py`
- provider and rewrite tests

Tasks:

- [ ] Keep the deterministic provider as the offline default.
- [ ] Expose the existing command rewrite provider through an explicit CLI option; do not add an SDK dependency or shell execution.
- [ ] Pass the provider only the original candidate fragment, allowed requirement terms, target section, evidence IDs, ownership ceiling, and strict character budget.
- [ ] Require structured variants and record provider identity, version, fallback, and input/output digests.
- [ ] Run every provider result through the same factual, metric, entity, ownership, conflict, duplicate, and format-budget validators.
- [ ] Reject keyword stuffing, hidden text, unsupported synonyms, employer-specific claims, and generic filler.
- [ ] Prefer replacement of an existing bullet over insertion of a new paragraph.
- [ ] Give each variant a compact explanation: supported terms surfaced, evidence used, terms still missing, character delta, and risk.
- [ ] Never auto-select or auto-approve the most aggressive variant.

Quality target:

- A proposed rewrite must read naturally to a recruiter and improve supported coverage.
- A change that merely repeats a skills list is not a useful rewrite.
- The tool reports exact coverage, not a universal ATS score or pass probability.

Suggested commit: `feat: expose validated role-specific rewrite providers`

## Milestone 6: Enforce strict DOCX format preservation

Primary files:

- `src/ats_agent/documents.py`
- `src/ats_agent/formatting.py`
- `src/ats_agent/workflow.py`
- `src/ats_agent/cli.py`
- DOCX fidelity and atomicity tests

Tasks:

- [ ] Add a `strict-preserve` document mode for existing DOCX files.
- [ ] In strict mode, allow anchored text replacement only; block paragraph insertion, deletion, table changes, section changes, and rebuilds.
- [ ] Preserve paragraph properties, run properties, styles, numbering, tables, headers, footers, margins, relationships, and all non-text package parts.
- [ ] Build a DOCX structural fingerprint before and after application that ignores only the approved text-node changes.
- [ ] Require identical structure/style fingerprints in strict mode.
- [ ] Enforce a configurable character-growth budget per paragraph to reduce pagination risk.
- [ ] Reparse the output, verify approved text, ensure no other candidate text disappeared, and compare section order and extractable-word counts.
- [ ] Keep transactional temporary-write, validation, and atomic rename behaviour.
- [ ] When LibreOffice or Word rendering is available, optionally compare PDF page count and rendered pages; otherwise report visual pagination as unverified.
- [ ] Do not claim pixel-identical or page-identical formatting without a successful renderer check.

Acceptance:

- Source DOCX hash remains unchanged.
- In strict mode, the OOXML package differs only in approved text nodes and expected archive metadata.
- Unaffected runs retain bold, italic, underline, fonts, sizes, and styles.
- No duplicate paragraphs or table rows are created.
- Output validation failure leaves no final DOCX behind.

Suggested commit: `feat: add strict DOCX format lock`

## Milestone 7: Report coverage and actionable gaps

Primary files:

- `src/ats_agent/agents.py`
- `src/ats_agent/review.py`
- `src/ats_agent/job_research.py`
- reporting tests and documentation

Tasks:

- [ ] Report keyword coverage as counts and sourced terms, not an opaque ATS score.
- [ ] Show baseline coverage, proposed-variant coverage, and validated-output coverage.
- [ ] Separate:
  - already covered terms;
  - truthfully surfaceable terms;
  - adjacent evidence requiring human confirmation;
  - unsupported skill/experience gaps;
  - factual conflicts;
  - eligibility and availability gaps.
- [ ] Rank gaps by mandatory/preferred status and likely screening impact.
- [ ] Give concrete evidence-building recommendations such as a project, analysis, course, portfolio artifact, or quantified work example.
- [ ] Never recommend adding a keyword without evidence.
- [ ] Make the review bundle say why each proposed change is useful and why each rejected change was blocked.
- [ ] Show source quality for job and company research next to every recommendation.

Acceptance: a student can tell what wording can change now, what evidence must be confirmed, what capability should be built, and what eligibility issue cannot be solved by CV wording.

Suggested commit: `feat: report sourced ATS coverage and genuine gaps`

## Milestone 8: Lock the workflow into real evaluations

Test layers:

### Focused regression tests

- [ ] Digest finalization and persistence.
- [ ] Conflict detection and scoped blocking.
- [ ] Exact/normalized duplicate suppression.
- [ ] Full-clause requirement extraction.
- [ ] AI Job Search interchange validation.
- [ ] Scrapling empty/failure/fallback provenance.
- [ ] Rewrite usefulness and keyword-stuffing rejection.
- [ ] Strict DOCX structural fingerprint.

### Public benchmark

- [ ] Add at least 30 licensed or synthetic role cases across product, AI, finance, strategy, operations, and analytics.
- [ ] Label complete requirements, importance, eligibility gates, supported evidence, prohibited claims, and acceptable coverage improvements.
- [ ] Measure requirement precision/recall, evidence precision/recall, unsupported detection, duplicate-change rate, conflict-escape rate, format-lock pass rate, and parser-risk delta.
- [ ] Keep human rewrite preference explicitly unmeasured until reviewed.

### Private holdout and real-document pilot

- [ ] Maintain a protected private holdout that is unavailable to implementation agents.
- [ ] Run the original TikTok, Zurich, and CheQ scenarios using the real DOCX locally without committing it.
- [ ] Add at least seven more real job/CV pairs with candidate consent.
- [ ] Blind human review of factual accuracy, usefulness, natural language, and layout preservation.
- [ ] Record corrections and failures rather than tuning the holdout into the public fixtures.

### Adapter and release verification

- [ ] Run the repository's required Ruff, Mypy, coverage, benchmark, adapter, build, and release-tree checks.
- [ ] Install the built wheel into a fresh environment.
- [ ] Verify standalone CLI, Codex skill, and Claude plugin against the same fixture.
- [ ] Run one fresh AI Job Search -> Scrapling -> proposal -> explicit approval -> strict-preserve apply -> validate flow.
- [ ] Verify the installed package provenance and version after replacement.
- [ ] Run CI on Linux, macOS, and Windows where the existing matrix supports them.

Suggested commit: `test: gate release on real CV workflow quality`

## Acceptance scorecard

The upgrade is complete only when all rows pass.

| Area | Release gate |
|---|---|
| Proposal integrity | 100% generated proposals verify after disk round-trip |
| Tamper safety | Any proposal, source, JD, evidence, or context mutation blocks approval/apply |
| Evidence conflicts | 0 conflicting scoped facts reach a supported variant |
| Duplicate changes | 0 exact or normalized duplicate insertions in the pilot and holdout |
| Unsupported claims | 0 unsupported terms, metrics, entities, ownership escalations, or eligibility claims inserted |
| Requirement coverage | All labelled material requirements represented with valid source spans; agreed precision/recall gate met |
| No-filter behaviour | Every discovered role remains visible with status and warnings |
| Capture provenance | Every source records method, URL, time, hash, source type, and failure/fallback status |
| Rewrite usefulness | Every proposed change has positive supported coverage or clarity delta |
| Strict format | Structural/style fingerprint unchanged; only approved text changes differ |
| Source safety | Source hash unchanged and output path distinct |
| Output validation | Reparse, coverage, factual, and format checks pass before atomic rename |
| Human approval | Exact digest, change IDs, and variants required; no approve-all shortcut |
| Real pilot | TikTok, Zurich, and CheQ regression expectations all pass |
| Installed runtime | Fresh installed wheel and both adapters complete the verified workflow |
| Claims | No universal ATS score, pass guarantee, interview probability, or salary promise |

## Full verification commands

Use the repository's locked environment and existing scripts. Do not lower gates.

```bash
ruff check src tests scripts
mypy src/ats_agent
coverage run --branch --source=ats_agent -m unittest discover -s tests -v
coverage report --fail-under=90
python scripts/check_benchmark.py
python scripts/validate_agent_adapters.py
python scripts/check_release_tree.py
python -m build
```

Then install the built wheel into a fresh temporary environment and run:

```bash
ats-agent --version
ats-agent doctor --strict
ats-agent benchmark --suite smoke
```

Finally rerun the private real-document pilot and record:

- roles discovered and retained;
- direct/fallback captures and failures;
- requirements extracted per role;
- existing, proposed, unsupported, conflicting, and eligibility terms;
- exact approved changes;
- source/output hashes;
- structural and optional rendered-layout results;
- all commands, exit codes, failures, and remaining manual gates.

## Explicit non-goals

- Beating or deceiving employer screening systems.
- Invisible keywords, white text, metadata stuffing, or fabricated experience.
- Guaranteed ATS passage, interview, offer, or salary.
- Automated applications, outreach, portal login, or tracker mutation.
- A new job-search crawler or replacement for AI Job Search.
- A web application, database, MCP server, autonomous multi-agent system, or background scheduler.
- Exact pagination claims without a real renderer.

## Implementation order

Do not begin research-depth or rewrite-quality work until Milestones 1 and 2 pass. A smarter system that cannot verify its proposal or reject conflicting facts is less useful than the current conservative tool.

Recommended PR sequence:

1. Proposal integrity.
2. Conflict and duplicate safety.
3. Sourced role dossiers and AI Job Search handoff.
4. Rewrite usefulness and coverage reporting.
5. Strict DOCX format lock.
6. Real evaluations, installed-runtime verification, and release documentation.

Each PR must include its focused tests and must leave the complete verification suite green before merge.
