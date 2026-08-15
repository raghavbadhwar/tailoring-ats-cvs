# ATS CV Agent

An approval-first, evidence-grounded Career Intelligence workflow for tailoring a CV to a job description without inventing qualifications.

> **Status:** alpha (`0.2.0`). The evidence ledger, requirement mapping, conservative rewriting, local approval review, safe apply engine, and ordinary DOCX preserve mode are implemented. Broader semantic extraction, model-backed prose generation, complex DOCX field editing, and large human-reviewed benchmarks remain roadmap items.

## What it does

- extracts candidate evidence from a CV and optional supporting files;
- isolates evidence by candidate identity and records file/line provenance;
- extracts traceable job requirements and common hard eligibility gates;
- maps each requirement to direct, transferable, or unsupported evidence;
- proposes conservative rewrites that preserve ownership level;
- blocks unsupported skills, metrics, ownership escalation, stale proposals, ambiguous edits, no-ops, and source overwrites;
- produces Markdown and self-contained HTML review reports;
- allows only supported changes to enter an approval manifest;
- applies only explicitly approved change IDs;
- preserves ordinary DOCX paragraph styles, run formatting, lists, tables, headers, and footers when using preserve mode;
- emits a new output, unified diff, hashes, validation findings, and an applied-change log;
- reports qualitative recruiter signals without presenting a fake universal ATS score.

## Install

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,documents]"
```

Python 3.10 or newer is required. Text-based PDF input uses the optional `pypdf` dependency included in the `documents` extra.

## End-to-end workflow

### 1. Propose changes

```bash
ats-agent propose resume.docx job.md \
  --evidence project-bank.md \
  --candidate-id raghav \
  --output run/proposal.json
```

`PROPOSE` is read-only. The job description supplies requirements and vocabulary; it is never candidate evidence.

### 2. Review and approve

```bash
ats-agent review run/proposal.json \
  --markdown run/review.md \
  --html run/review.html \
  --output-document tailored-resume.docx
```

Open `run/review.html` locally. It shows:

- recruiter-oriented signals;
- the requirement-to-evidence matrix;
- before/after wording;
- supporting evidence IDs;
- unsupported gaps as disabled controls.

Select supported changes and download `approval-manifest.json`. The HTML is self-contained and uses no network assets.

### 3. Apply approved changes

Place the downloaded manifest beside `proposal.json`, then run:

```bash
ats-agent apply run/approval-manifest.json
```

The source CV is never overwritten. The output is reopened and verified before success is reported.

## Other commands

```bash
ats-agent audit resume.docx job.md --evidence project-bank.md --candidate-id raghav
ats-agent format resume.docx --json
ats-agent benchmark
ats-agent benchmark --dataset benchmarks/datasets/cases.jsonl
```

The default benchmark fixtures are packaged with the installed CLI, so `ats-agent benchmark` works outside the repository directory.

## Reproducible repository example

```bash
run_dir="$(mktemp -d)"

ats-agent propose \
  examples/sample_resume.txt \
  examples/sample_job.md \
  --evidence examples/sample_project_bank.md \
  --candidate-id sample-candidate \
  --output "$run_dir/proposal.json"

ats-agent review "$run_dir/proposal.json" \
  --markdown "$run_dir/review.md" \
  --html "$run_dir/review.html" \
  --output-document tailored-resume.txt

cp examples/approved_changes.json "$run_dir/approval-manifest.json"
(cd "$run_dir" && ats-agent apply approval-manifest.json)
```

Expected artifacts:

- `proposal.json` — requirements, evidence, mappings, and proposed changes;
- `review.md` and `review.html` — human-readable approval reports;
- `tailored-resume.txt` — new output; the source remains unchanged;
- `tailored-resume.txt.applied.json` — exact edits, hashes, diff, and validation.

## Proposal contract

A proposal contains:

- source and job-description SHA-256 hashes;
- candidate ID;
- evidence ledger with source file and line provenance;
- extracted requirements with JD source spans;
- requirement-to-evidence mappings;
- supported and unsupported change proposals;
- parser, language, recruiter, hiring-manager, and interview-defense reports.

A supported rewrite resembles:

```json
{
  "id": "C1",
  "operation": "replace_span",
  "expected_text": "Helped build automated order workflows with 42 tests.",
  "replacement_text": "Contributed to workflow automation for orders with 42 tests.",
  "evidence_ids": ["E..."],
  "supported": true,
  "ownership_before": "contributor",
  "ownership_after": "contributor"
}
```

Missing qualifications remain unsupported and cannot be approved into the CV.

## Safety invariants

`APPLY` enforces all of the following:

- approved change IDs must exist;
- evidence IDs must exist in the same candidate ledger;
- ownership cannot be escalated beyond supporting evidence;
- unsupported known qualifications and numeric claims are blocked;
- the source SHA-256 must still match;
- expected text must occur exactly once;
- no-op and unsupported operations are rejected;
- the output cannot overwrite the source;
- `.pdf` output is blocked unless a genuine renderer is implemented;
- the generated output is reopened and verified before success is reported.

## Document support

| Format | Input | Output | Current behavior |
|---|---:|---:|---|
| TXT / Markdown | Yes | Yes | Full proposal/review/apply workflow |
| HTML / RTF | Basic | Text | Normalized text extraction |
| DOCX | Yes | Yes | Preserve mode patches ordinary paragraphs/runs and retains styles, tables, headers, and footers; rebuild mode creates a controlled text-first DOCX |
| Text-based PDF | Optional | No | Input requires `pypdf`; image-only/scanned files are blocked when no text is extractable |

DOCX preserve mode intentionally blocks complex field/hyperlink paragraphs that cannot be safely represented as ordinary runs. It does not silently flatten them. PDF output is not implemented.

## Benchmarking

Reported metrics are transparent engineering measures such as:

- supported-requirement recall;
- unsupported-requirement detection;
- evidence-provenance coverage.

Unimplemented metrics return `null` with an explicit status. The project does not turn these metrics into an employer acceptance prediction.

## Repository map

- `SKILL.md` — portable workflow and approval boundary;
- `src/ats_agent/evidence.py` — candidate-specific evidence ledger and ownership model;
- `src/ats_agent/requirements.py` — hard-gate extraction and requirement mapping;
- `src/ats_agent/rewriting.py` — conservative evidence-backed rewrites;
- `src/ats_agent/validation.py` — factual and ownership checks;
- `src/ats_agent/docx_patch.py` — structure-preserving DOCX patcher;
- `src/ats_agent/reports.py` — Markdown and offline HTML approval review;
- `src/ats_agent/workflow.py` — proposal and approval-gated apply orchestration;
- `benchmarks/` and `src/ats_agent/data/` — evaluation fixtures;
- `tests/` — workflow, safety, reporting, document, and CLI tests;
- `.github/workflows/ci.yml` — validation, lint, typing, coverage, package, compatibility, and end-to-end checks.

## Non-goals

The project does not:

- predict an employer's acceptance decision;
- produce a universal ATS score;
- submit job applications;
- invent candidate experience;
- autonomously approve edits;
- treat a number in a CV as proof of the underlying statement;
- claim that deterministic rewriting replaces a human-reviewed language model.

See `ROADMAP.md` for the remaining work toward a stable 9/10-usability release.
