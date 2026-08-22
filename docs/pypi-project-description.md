# PyPI project description (ready to paste)

> This is the exact markdown to enter as the PyPI project description when
> configuring `tailoring-ats-cvs` on pypi.org (or verifying what
> Trusted Publishing will publish — `pyproject.toml` already wires this
> repository's `README.md` as the source description; the text below mirrors
> it in condensed, registry-friendly form).

---

# Tailoring ATS CVs — Evidence-Grounded Career Intelligence Agent

An **approval-first** tool that reads a candidate CV, a job description, and
optional supporting evidence; maps role requirements to traceable candidate
facts; proposes safe, role-aligned rewrites; and applies **only explicitly
approved changes** to a brand-new output document.

## Why

Most "ATS optimizers" fabricate keywords. This tool does the opposite: every
factual statement it introduces must be entailed by same-candidate evidence,
and anything unsupported is reported as a gap — never inserted.

## Highlights

- **Ingest** TXT, Markdown, HTML, RTF, DOCX, and text-based PDF
- **Evidence ledger**: atomic claims with ownership level and provenance
- **Requirement matching**: clause-level extraction, alias ontology
  (B.Com → bachelor's degree), hard eligibility gates
- **Honest refusals**: negation-aware ("No A/B testing experience" is not
  coverage); disavowal lines are never surfaced into your CV
- **Rewrite variants**: conservative / balanced / compact, deterministic and
  reviewable
- **Approval-gated apply**: change-ID manifests bound to proposal digests;
  transactional writes with post-write reparse
- **Auditable output**: applied-change receipts, layout findings, redacted
  review bundles

## Install

```bash
# From GitHub (works today)
uv tool install "git+https://github.com/raghavbadhwar/tailoring-ats-cvs.git@v1.0.0-beta.4"

# Or via Claude Code / Codex adapters — see the repository README
# for one-command native installs.
```

## Quickstart

```bash
ats-agent propose my-cv.docx job-description.md \
  --candidate-id me --evidence projects.md \
  --output proposal.json      # human-readable summary prints alongside

ats-agent review  proposal.json --markdown review.md --html review.html
ats-agent approve proposal.json --select C1:conservative \
  --output approval.json --output-document tailored-resume.docx
ats-agent apply   approval.json
ats-agent validate tailored-resume.docx
```

## Guarantees

- Your source CV is never modified.
- Nothing is applied without an explicit, digest-bound approval naming each
  change ID and variant.
- No universal ATS score, interview probability, or employer-acceptance
  claims are made — only measured properties.

## Status

`1.0.0b4` beta. Public Benchmark v3 (270 cases), full CI, security scans,
and SBOM generation pass. The protected private-holdout gate is deferred for
prereleases and remains mandatory for stable v1.0.0.

MIT licensed. Source: <https://github.com/raghavbadhwar/tailoring-ats-cvs>
