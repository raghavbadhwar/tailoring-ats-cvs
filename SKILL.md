---
name: tailoring-ats-cvs
description: Audit a candidate CV against a job description, map requirements to candidate-scoped evidence, propose evidence-backed ATS-safe rewrites, and apply only explicitly approved changes.
---

# Tailoring ATS CVs

Use a strict three-stage contract:

1. **PROPOSE** — read the complete CV, job description, and authorized evidence files; extract hard gates and requirements; create a requirement-to-evidence map; generate numbered conservative, balanced, and compact rewrites; do not edit the CV.
2. **APPROVE** — present every proposed change with its evidence IDs, source spans, ownership level, introduced terminology, and risk. Accept only an explicit allow-list of change IDs and selected variants.
3. **APPLY** — verify source hashes, evidence IDs, candidate identity, exact anchors, ownership, protected facts, and output path; apply only approved supported changes to a duplicate; re-parse and validate the output.

Never treat the job description as candidate evidence. Never invent or strengthen employment, dates, metrics, customers, users, revenue, deployment status, certifications, technologies, education, ownership, or outcomes. Mark unsupported requirements as gaps.

Prefer `ats-agent prepare` to create `proposal.json`, `proposal.md`, and `review.html`. After approval, use `ats-agent apply`, then `ats-agent validate`.

For DOCX, use `preserve` mode when the existing structure is parser-safe and `rebuild` mode when an ATS-safe one-column document is needed. PDF is input-only unless a genuine renderer is available.

Do not produce a universal ATS score or claim an acceptance probability. Report transparent requirement coverage, hard gates, parser risks, evidence strength, and remaining limitations.
