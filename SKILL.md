---
name: tailoring-ats-cvs
description: Audit a candidate CV against a job description, map requirements to candidate-specific evidence, propose factual ATS-safe changes, review them, and apply only explicitly approved changes.
---

# ATS CV Agent

Use four explicit stages:

1. `INGEST`: read the complete CV, job description, and any candidate-authorized evidence files. Preserve candidate identity and source provenance. A job description is never candidate evidence.
2. `PROPOSE`: identify hard gates and parser risks, extract requirements with source spans, map each requirement to direct, transferable, or unsupported evidence, and emit numbered before/after changes. Do not edit files.
3. `REVIEW`: present the requirement-to-evidence matrix and proposed changes in Markdown or self-contained HTML. Unsupported gaps must be visibly disabled and excluded from approval.
4. `APPLY`: require an explicit allow-list of change IDs, validate every evidence ID, copy rather than overwrite the source, apply only approved supported changes, reopen the output, and rerun validation.

## Non-negotiable factual safeguards

Never infer a qualification from the job description. Never invent or strengthen:

- employers, roles, dates, qualifications, certifications, tools, or skills;
- metrics, customers, users, savings, revenue, outcomes, or deployment status;
- ownership such as `helped` → `built`, `contributed` → `led`, or `prototype` → `production`;
- solo authorship where the evidence establishes team or AI-assisted work.

Every factual addition must reference real evidence IDs from the same candidate ledger. Missing and invalid evidence IDs are blockers, not warnings.

## Apply safeguards

Before editing, verify:

- the source SHA-256 still matches the proposal;
- each approved change exists and is supported;
- each evidence ID exists and belongs to the same candidate;
- ownership and numerical claims remain within the evidence;
- expected text occurs exactly once;
- the change is not a no-op;
- the output path does not overwrite the source;
- the output format is genuinely supported.

Reject stale, missing, ambiguous, unsupported, no-op, cross-candidate, and source-overwriting operations.

## Document behavior

- TXT and Markdown support the full proposal/review/apply workflow.
- DOCX preserve mode patches ordinary paragraphs/runs in a duplicate and retains paragraph styles, run formatting, lists, tables, headers, and footers.
- Complex DOCX fields or hyperlink paragraphs that cannot be represented safely must be blocked rather than flattened.
- DOCX rebuild mode is explicit and produces a controlled text-first duplicate.
- Text-based PDF may be used as input when an extraction adapter is installed.
- Do not create a file named `.pdf` unless a genuine PDF renderer exists.

## CLI workflow

```bash
ats-agent propose resume.docx job.md \
  --evidence project-bank.md \
  --candidate-id candidate-id \
  --output run/proposal.json

ats-agent review run/proposal.json \
  --markdown run/review.md \
  --html run/review.html \
  --output-document tailored-resume.docx

ats-agent apply run/approval-manifest.json
```

`ats-agent review` must never modify the CV. `ats-agent apply` consumes the exact approval manifest and produces a new output plus hashes, diff, validation, and applied-change log.

## Reporting boundaries

Report transparent requirement coverage and parser risks. Do not present a universal ATS score or claim to predict employer acceptance. Recruiter-oriented outputs must be qualitative, evidence-based, and explicitly labelled heuristic.

See `references/workflow.md`, `references/benchmarking.md`, `references/formatting.md`, and `ROADMAP.md`.
