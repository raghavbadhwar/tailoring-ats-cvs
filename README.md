# Tailoring ATS CVs — Evidence-Grounded Career Intelligence Agent

An approval-first tool that reads a candidate CV, a job description, and optional supporting evidence; maps requirements to traceable candidate facts; proposes safe role-aligned rewrites; and applies only explicitly approved changes to a new output document.

## Public job-list research

Use an unfiltered AI Job Search JSON export to produce one draft proposal per role. Scrapling captures the listed job page and optional official company-context pages without credentials, redirects, proxies, or browser automation. The batch output retains blocked and eligibility-warning roles, carries a capture manifest, and reports which job terms are directly supported, transferable, or unsupported by candidate evidence. Unsupported keywords are reported as gaps and are never inserted into the CV.

```json
{"jobs": [{"id": "analyst", "company": "Example", "role": "Analyst", "job_url": "https://careers.example.com/analyst", "official_context_urls": ["https://example.com/careers"], "fallback": {"description": "Only used when official capture fails.", "source_url": "https://listing.example.com/analyst", "provider": "Example Listings", "fetched_at": "2026-08-17T00:00:00Z"}}]}
```

```bash
ats-agent research-jobs resume.docx jobs.json --candidate-id student \
  --evidence candidate-projects.md \
  --context-url https://example.com/careers \
  --out runs/analyst-batch
```

Career-Ops Markdown remains a backward-compatible, read-only input; processed rows and tracker data are not changed:

```bash
ats-agent research-jobs /path/to/career-ops/cv.md /path/to/career-ops/data/pipeline.md \
  --candidate-id student --out runs/career-ops-batch
```

Pending rows use Career-Ops' existing `- [ ] URL | Company | Role` format. AI Job Search remains the system for job discovery and ranking; `ats-agent` remains the approval-gated CV engine. Aggregator fallback content is visibly labelled non-official and is never presented as employer-confirmed. Public-job proposals record a liveness timestamp and must be refreshed after seven days before apply.

Use the existing AI Job Search discovery workspace first, including its existing
low-volume public LinkedIn skill when relevant. Retain roles, keep its export
and tracker read-only, and pass its unfiltered export to `ats-agent`.

For a role-relevant unsupported gap, ask the candidate neutrally whether they
genuinely did the activity. A bare yes never becomes CV text. After yes,
require a confirmed activity plus setting or timeframe, write the truthful
response as a candidate-owned supplemental evidence artifact in the run
directory, and rebuild a draft with the existing `--evidence` option. The
source CV is not edited and the rebuilt draft still needs explicit approval
before apply.

It does **not** invent qualifications, autonomously submit applications, or claim a universal ATS score, interview probability, or employer-acceptance probability.

## Release status

The trustworthy v1 engineering line is prepared as `1.0.0b3`. Beta publication is fail-closed: the branch must pass CI, security, Benchmark v3, cross-platform compatibility, clean-wheel installation, and a protected 60-case private holdout before the `v1.0.0-beta.3` tag can publish a GitHub prerelease.

## Agent entry points

### Use it in 30 seconds

**Claude Code** (native plugin):

```text
/plugin marketplace add raghavbadhwar/tailoring-ats-cvs
/plugin install tailoring-ats-cvs@raghavbadhwar
```

Then run `/tailoring-ats-cvs:tailor-cv <cv-path> <job-description> [evidence...]`.
On first use the skill asks once — "May I install the ats-agent engine?" —
then installs and verifies the pinned engine automatically.

**Codex** (native skill):

```bash
python scripts/install_codex_skill.py
```

Then paste: `Use the tailor-cv skill. CV: ./my-cv.docx Job description: ./jd.md`
— same single-consent bootstrap applies inside Codex.

**Standalone CLI** (no agent host):

```bash
uv tool install "tailoring-ats-cvs[documents]==1.0.0b3"   # or, until PyPI:
uv tool install "git+https://github.com/raghavbadhwar/tailoring-ats-cvs.git@v1.0.0-beta.3"
ats-agent doctor --strict
```

All three paths require explicit approval of change IDs and variants before application. The engine installer itself is also consent-gated: one prompt covers the ordered attempt chain (PyPI → GitHub tag → isolated venv). See [agent adapter instructions](docs/agent-adapters.md) for bootstrap security, release assets, and known local-only limits.

The active upgrade is ordinary, reviewable source code. CI rejects encoded source payloads and workflows that reconstruct and push replacement source trees.

## What works

- TXT, Markdown, HTML, RTF, DOCX, and optional text-based PDF ingestion
- candidate-scoped artifact hashes and evidence provenance
- atomic claims with metric value/unit/scope and ownership binding
- clause-level requirement extraction and hard-gate evaluation
- requirement-to-evidence mapping with direct, equivalent/transferable, unsupported, and conservative unknown handling
- conservative, balanced, and compact evidence-backed rewrite variants
- deterministic blocking of unsupported skills, metrics, employers, protected status, and ownership escalation
- canonical proposal digest and explicit digest-bound approval manifests
- full and redacted Markdown/HTML review bundles
- transactional TXT/Markdown/DOCX apply with source-overwrite and existing-output protection
- DOCX preserve, strict-preserve, and rebuild modes, post-write reparse, diff, hashes, and applied-change receipts
- Benchmark v3 public, adversarial, document, smoke, and human-evaluation queue infrastructure
- Python 3.10–3.13 compatibility on Linux and Windows
- dependency audit, Bandit, CodeQL, dependency review, secret-pattern scan, and CycloneDX SBOM generation

## Install

```bash
python -m pip install -e '.[documents]'
```

Development environment:

```bash
python -m pip install -e '.[dev,documents]'
```

## Agent-native adapters

The CLI is the only CV engine. Codex and Claude Code adapters are thin instructions that call it and preserve the same approval boundary.

- **Codex:** the repository skill is [`.agents/skills/tailor-cv/`](.agents/skills/tailor-cv/). It first checks `ats-agent`, prints an immutable install command when missing, and waits for explicit permission before installation.
- **Claude Code:** load the repository root with `claude --plugin-dir .`. Its shared skill is available as `/tailoring-ats-cvs:tailor-cv`.
- **Restricted environments:** use the pinned manual virtual-environment command in `.agents/skills/tailor-cv/references/installation.md`; no adapter installs software silently.

Build deterministic release bundles with:

```bash
python scripts/build_agent_bundles.py --output dist/agent-adapters
```

The bootstrap reference is pinned to the `v1.0.0-beta.3` release tag, not a moving branch. After installation, verify `ats-agent doctor --strict`.

## End-to-end workflow

### 1. Prepare a proposal and review bundle

```bash
ats-agent prepare resume.docx job-description.md \
  --candidate-id candidate-1 \
  --evidence master-project-bank.docx \
  --company-context official-company-context.md \
  --out run/
```

This writes a proposal and review artifacts. The proposal contains source hashes, the evidence ledger, requirement mappings, hard-gate results, proposed changes, variants, and a canonical digest.

### 2. Create explicit approval

```bash
ats-agent approve run/proposal.json \
  --select C1:balanced \
  --select C3:compact \
  --output run/approval-manifest.json \
  --output-document run/tailored-resume.docx
```

Approval creates a manifest only. It does not edit the CV.

### 3. Apply approved changes

```bash
ats-agent apply run/approval-manifest.json
```

The source is never overwritten. Apply rechecks the proposal digest and all artifact hashes, writes a temporary output, reparses and verifies it, and atomically promotes it only after validation succeeds.

### 4. Validate the output

```bash
ats-agent validate run/tailored-resume.docx
```

## Review modes

Render an existing proposal:

```bash
ats-agent review run/proposal.json \
  --markdown run/review.md \
  --html run/review.html \
  --output-document run/tailored-resume.docx
```

Use `--redacted` for a shareable review that removes candidate content and paths and disables approval controls.

## Other commands

```bash
ats-agent doctor
ats-agent audit resume.docx job.md --candidate-id candidate-1
ats-agent propose resume.docx job.md --output proposal.json
ats-agent format resume.docx
ats-agent benchmark --suite smoke
ats-agent benchmark --suite public --report benchmarks/v3/reports/public.json
ats-agent benchmark --suite adversarial --report benchmarks/v3/reports/adversarial.json
ats-agent benchmark --suite documents --report benchmarks/v3/reports/documents.json
```

## Safety model

The job description and company context are vocabulary/context sources, not candidate evidence. Every factual rewrite must remain inside the candidate evidence boundary. The validator blocks unknown or cross-candidate evidence, ownership escalation, unsupported numbers/entities/status claims, stale proposals, tampered approvals, ambiguous/conflicting anchors, unsupported output formats, and source overwrites.

PDF is input-only unless a genuine renderer is added. Scanned/image-only PDFs are blocked rather than silently OCRed.

See `docs/threat-model.md` and `docs/evidence-model.md` for the detailed model.

## Benchmark v3

Benchmark v3 separates development/regression evidence from real-world outcome claims. Public reports contain exact code SHA, dataset SHA-256, environment metadata, denominators, confidence intervals, baselines, and explicit `not_measured` states for human preference or parser-risk metrics that have not been genuinely measured.

```bash
python scripts/validate_benchmark_diversity.py
python scripts/check_benchmark.py
```

The release path uses:

- a 180-case balanced public development suite;
- a 60-case adversarial safety suite;
- a 30-case document suite;
- a packaged smoke suite;
- a 50-pair blinded human-evaluation queue;
- a separate 60-case private holdout supplied only to the protected GitHub `release` environment.

The private cases are never committed to the public repository or uploaded as release assets.

## CI and release gates

Pull requests run:

- visible-source release-tree integrity;
- benchmark fixture and diversity validation;
- Ruff and Mypy;
- tests plus Benchmark v3 under at least 90% branch coverage;
- dependency auditing;
- package build and clean-wheel installation;
- approval-gated end-to-end smoke tests;
- Python 3.10–3.13 on Ubuntu and Windows;
- Bandit, CodeQL, dependency review, secret-pattern scanning, and SBOM generation.

The tag-triggered release workflow additionally requires the protected private holdout before publishing a prerelease. See `docs/release-process.md`.

## Repository map

```text
src/ats_agent/
  agents.py                 explainable recruiter/hiring-manager reports
  artifacts.py              candidate-scoped artifact registry
  benchmark.py              Benchmark v3 public API
  _benchmark_*.py           suite loading, metrics, validation, runners
  cli.py                    user-facing commands
  documents.py              transactional text and DOCX editing
  evidence.py               candidate-scoped evidence and atomic claims
  formatting.py             parser-risk diagnostics
  hashing.py                canonical digests and SHA-256 helpers
  ingestion.py              safe document extraction
  models.py                 typed proposal/approval schemas
  providers.py              deterministic/optional rewrite provider contracts
  requirements.py           JD requirements, hard gates, evidence mapping
  review.py                 canonical Markdown/HTML/approval renderer
  rewriting.py              protected section-aware rewrite variants
  validation.py             deterministic factual guardrails
  workflow.py               PROPOSE → APPROVE → APPLY orchestration
```

## Known limits

- Default semantic matching is deterministic and deliberately conservative.
- Complex unsupported DOCX structures fail explicitly or require visual review rather than being silently flattened.
- Human preference and real hiring outcomes are separate validation studies; automated benchmark scores are not substitutes for them.
- Stable `v1.0.0` requires the anonymized real-document pilot and blinded human evaluation described in `ROADMAP.md`.

See `docs/architecture.md`, `docs/evidence-model.md`, `docs/privacy.md`, `docs/threat-model.md`, `docs/benchmark-methodology.md`, `docs/release-process.md`, `SECURITY.md`, and `ROADMAP.md`.
