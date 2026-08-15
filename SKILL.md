---
name: tailoring-ats-cvs
description: Audit a candidate CV against a job description, propose evidence-backed ATS-safe changes, and apply only explicitly approved changes.
---

# ATS CV Agent

Use two explicit stages:

1. `PROPOSE`: read the complete CV and job description, identify hard gates and parser risks, map requirements to candidate evidence, and emit numbered changes. Do not edit files.
2. `APPLY`: require explicit approval of change IDs, copy rather than overwrite the source CV, apply only approved changes, and rerun validation.

Never infer a qualification from the job description. Mark unsupported skills, dates, metrics, employers, tools, certifications, and outcomes as unsupported or requiring confirmation. Preserve candidate identity and evidence provenance.

The CLI is a local scaffold for audit/proposal/apply orchestration; document parsing and model integrations remain deliberate extension points.

Use `ats-agent format resume.txt --json` after text extraction to check reading order, dense lines, tabular spacing, decorative bullets, and standard section headings. Formatting findings are recommendations, not proof of an employer's ATS decision. Never silently rewrite the source document.

See `references/workflow.md`, `references/benchmarking.md`, and `references/integration-roadmap.md`.
