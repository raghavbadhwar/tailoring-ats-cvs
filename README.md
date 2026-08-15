# Tailoring ATS CVs — Evidence-Grounded Career Intelligence Agent

An approval-first tool that reads a candidate CV, a job description, and optional supporting evidence; maps requirements to traceable candidate facts; proposes safe role-aligned rewrites; and applies only explicitly approved changes to a new output document.

It does **not** invent qualifications, autonomously submit applications, or claim a universal ATS acceptance score.

## What works

- TXT, Markdown, HTML, RTF, DOCX, and optional text-based PDF ingestion
- extraction-quality diagnostics and safe blocking
- candidate-scoped evidence ledger with source spans and ownership levels
- deterministic hard-gate extraction for degree, graduation year, experience, work authorization, sponsorship, grade, work mode, and travel
- requirement-to-evidence mapping with direct, transferable, and unsupported states
- conservative, balanced, and compact evidence-backed rewrite variants
- unsupported skill, metric, employer, status, and ownership-escalation blocking
- human approval manifest and self-contained local review HTML
- exact, stale, ambiguous, conflicting, and no-op validation
- structure-preserving DOCX patch mode and ATS-safe rebuild mode
- final re-parse, formatting audit, hashes, diff, and applied-change log
- 100-case offline safety benchmark with enforced CI thresholds
- Python 3.10, 3.12, and 3.13 compatibility checks

## Install

```bash
python -m pip install -e .
```

PDF input requires the optional document extra:

```bash
python -m pip install -e '.[documents]'
```

Development environment:

```bash
python -m pip install -e '.[dev,documents]'
```

Optional local commit hooks:

```bash
python -m pip install pre-commit
pre-commit install
```

## End-to-end workflow

### 1. Prepare a proposal and review bundle

```bash
ats-agent prepare resume.docx job-description.md \
  --candidate-id raghav-badhwar \
  --evidence master-project-bank.docx \
  --company-context official-company-context.md \
  --out run/
```

This writes:

```text
run/proposal.json
run/proposal.md
run/review.html
```

Open `review.html`, inspect evidence and variants, then download `approval-manifest.json`.

An existing proposal can also be rendered explicitly:

```bash
ats-agent review run/proposal.json \
  --markdown run/review.md \
  --html run/review.html \
  --output-document run/tailored-resume.docx
```

### 2. Apply approved changes

```bash
ats-agent apply run/approval-manifest.json
```

The source is never overwritten. The command creates a tailored document and an `.applied.json` audit log.

### 3. Validate the output

```bash
ats-agent validate run/tailored-resume.docx
```

## Other commands

```bash
ats-agent doctor
ats-agent audit resume.docx job.md --candidate-id candidate-1
ats-agent propose resume.docx job.md --output proposal.json
ats-agent format resume.docx
ats-agent benchmark
ats-agent benchmark --dataset benchmarks/datasets/cases_v2.jsonl
```

## Approval manifest

```json
{
  "proposal": "proposal.json",
  "selections": [
    {"change_id": "C1", "variant_id": "balanced"},
    {"change_id": "C3", "variant_id": "compact"}
  ],
  "approved_change_ids": ["C1", "C3"],
  "document_mode": "preserve",
  "output": "tailored-resume.docx"
}
```

`document_mode` can be:

- `preserve`: patch a DOCX while retaining its package, paragraph styles, headers, footers, hyperlinks, and unrelated content;
- `rebuild`: create a clean one-column ATS-safe DOCX from extracted text.

The legacy `mode` field remains accepted for backward compatibility. PDF is input-only unless a genuine PDF renderer is added. The tool never writes plain text to a fake `.pdf` file.

## Safety model

The job description is vocabulary, not evidence. A supported change must reference real evidence IDs from the same candidate ledger. The validator blocks:

- unknown or cross-candidate evidence;
- stronger ownership than the evidence supports;
- new numbers, employers, skills, certifications, users, customers, revenue, or production status;
- stale proposals;
- missing, ambiguous, conflicting, or no-op edits;
- source overwrites.

See [`docs/threat-model.md`](docs/threat-model.md) for assets, trust boundaries, threats, controls, and residual risks.

## Benchmark and quality gates

```bash
python scripts/generate_benchmark.py
python scripts/check_benchmark.py
```

The committed dataset contains 100 deterministic cases across supported skills, supporting evidence, unsupported qualifications, graduation and degree gates, experience gates, ownership escalation, and forbidden rewrite terms. Metrics are transparent engineering measures—not employer acceptance predictions.

CI enforces:

- portable skill and example validation;
- whitespace and Ruff checks;
- Mypy type checking;
- at least 80% branch-aware test coverage;
- 100-case benchmark safety thresholds;
- dependency auditing;
- source compilation;
- wheel build and installation outside the repository;
- the documented proposal → review → approval → apply workflow;
- Python 3.10, 3.12, and 3.13 compatibility.

## Repository map

```text
src/ats_agent/
  agents.py          explainable recruiter and hiring-manager reports
  benchmark.py       measured safety and coverage metrics
  cli.py             user-facing commands
  document_model.py  normalized resume structure
  documents.py       anchored text and DOCX editing
  evidence.py        candidate-scoped provenance ledger
  formatting.py      parser-risk diagnostics
  ingestion.py       safe document extraction
  reporting.py       primary Markdown and HTML review bundles
  reports.py         backward-compatible review renderers
  requirements.py    JD requirements, hard gates, and evidence mapping
  rewriting.py       protected rewrite variants
  validation.py      deterministic factual guardrails
  workflow.py        PROPOSE → APPROVE → APPLY orchestration
```

## Known limits

- Semantic matching is deterministic and taxonomy-based by default; it is intentionally conservative.
- Text-based PDF input requires `pypdf`; scanned PDFs are blocked rather than OCRed silently.
- Preserve mode retains the DOCX package and unrelated styling, but complex mixed-format paragraphs should be visually reviewed.
- Company-language alignment uses only user-supplied context in the current local-first release.
- Human preference and real hiring-outcome studies are not yet available, so the project makes no acceptance-rate claim.

See `docs/architecture.md`, `docs/evidence-model.md`, `docs/privacy.md`, `docs/threat-model.md`, `SECURITY.md`, and `ROADMAP.md`.
