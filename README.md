# ATS CV Agent

An approval-first, evidence-grounded Career Intelligence workflow for tailoring a CV to a job description without inventing qualifications.

> **Status:** alpha. The evidence, requirement-mapping, approval, and safe text-editing core is implemented. Structure-preserving DOCX editing, larger human-reviewed benchmarks, and optional model-backed rewriting remain active roadmap items.

## What it does

- extracts candidate evidence from a CV and optional supporting files;
- isolates evidence by candidate identity and records source provenance;
- extracts traceable job requirements and common hard gates;
- maps requirements to direct, transferable, or unsupported evidence;
- proposes conservative rewrites that preserve ownership level;
- blocks unsupported skills, metrics, ownership escalation, stale proposals, ambiguous edits, no-ops, and source overwrites;
- applies only explicitly approved change IDs;
- emits a new output, unified diff, hashes, validation findings, and an applied-change log;
- reports qualitative recruiter signals without presenting a fake universal ATS score.

## Install

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,documents]"
```

Python 3.10 or newer is required. PDF extraction uses the optional `pypdf` dependency included in the `documents` extra.

## Quick start

```bash
ats-agent audit resume.docx job.md \
  --evidence project-bank.md \
  --candidate-id raghav

ats-agent propose resume.docx job.md \
  --evidence project-bank.md \
  --candidate-id raghav \
  --output proposal.json

ats-agent apply approved_changes.json
ats-agent format resume.docx --json
ats-agent benchmark
```

The job description supplies requirements and vocabulary. It is never treated as candidate evidence.

## Reproducible example

The repository ships a complete text-based example:

```bash
ats-agent propose \
  examples/sample_resume.txt \
  examples/sample_job.md \
  --evidence examples/sample_project_bank.md \
  --candidate-id sample-candidate \
  --output examples/proposal.json

ats-agent apply examples/approved_changes.json
```

Expected artifacts:

- `examples/proposal.json` — requirements, provenance-backed evidence, mappings, and proposed changes;
- `examples/tailored-resume.txt` — a new tailored output; the source remains unchanged;
- `examples/tailored-resume.txt.applied.json` — hashes, exact applied changes, diff, and validation results.

The sample approval manifest is intentionally separate from the proposal:

```json
{
  "proposal": "proposal.json",
  "approved_change_ids": ["C1"],
  "output": "tailored-resume.txt"
}
```

## Proposal contract

A proposal contains:

- source and job-description SHA-256 hashes;
- candidate ID;
- evidence ledger with file and line provenance;
- extracted requirements with source spans;
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

`PROPOSE` is read-only. `APPLY` enforces all of the following:

- approved change IDs must exist;
- evidence IDs must exist in the same candidate ledger;
- ownership cannot be escalated beyond evidence;
- unsupported known qualifications and numeric claims are blocked;
- the source hash must still match;
- expected text must occur exactly once;
- no-op and unsupported operations are rejected;
- output cannot overwrite the source;
- `.pdf` output is blocked unless a genuine renderer is implemented;
- the generated output is reopened and verified before success is reported.

## Document support

| Format | Input | Output | Notes |
|---|---:|---:|---|
| TXT / Markdown | Yes | Yes | Full current workflow |
| HTML / RTF | Basic | Text output | Normalized text extraction |
| DOCX | Yes | Yes | Current writer rebuilds text; it does **not yet preserve complex original styling** |
| Text-based PDF | Optional | No | Input requires `pypdf`; image-only/scanned PDFs are blocked when no text is extractable |

DOCX preserve-mode editing is intentionally not claimed yet. Until it is implemented, use a duplicate or the controlled rebuild output and review formatting before submission.

## Benchmarking

```bash
ats-agent benchmark
ats-agent benchmark --dataset benchmarks/datasets/cases.jsonl
```

The default smoke dataset is packaged with the installed CLI, so the command works outside the repository directory. Reported metrics are transparent engineering measures such as supported-requirement recall and unsupported-requirement detection. Unimplemented metrics return `null` with an explicit status; they are not fabricated.

## Repository map

- `SKILL.md` — portable agent instructions and approval boundary;
- `src/ats_agent/evidence.py` — candidate-specific evidence ledger and ownership model;
- `src/ats_agent/requirements.py` — hard-gate and requirement extraction plus evidence mapping;
- `src/ats_agent/rewriting.py` — conservative evidence-backed rewrites;
- `src/ats_agent/validation.py` — deterministic factual and ownership checks;
- `src/ats_agent/workflow.py` — proposal and approval-gated apply orchestration;
- `benchmarks/` — dataset contract and evaluation fixtures;
- `tests/` — workflow, safety, reporting, document, and CLI regression tests;
- `.github/workflows/ci.yml` — validation, compatibility, lint, typing, coverage, package, and end-to-end checks.

## Non-goals

The project does not:

- predict an employer's acceptance decision;
- produce a universal ATS score;
- submit job applications;
- invent candidate experience;
- autonomously approve edits;
- claim that a number in a CV proves the underlying statement.

See `ROADMAP.md` and the reference documents for remaining milestones.
