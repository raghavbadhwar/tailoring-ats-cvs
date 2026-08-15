# ATS CV Agent

An approval-first Agent Skill for evidence-backed CV tailoring. It makes real candidate evidence easier for parsers and recruiters to match without inventing qualifications.

## Quick start

```bash
python -m src.ats_agent.cli audit resume.txt job.md
python -m src.ats_agent.cli format resume.txt --json
python -m src.ats_agent.cli propose resume.txt job.md --output proposal.json
python -m src.ats_agent.cli apply approved_changes.json
python -m src.ats_agent.cli benchmark
```

The pipeline validates inputs, runs named deterministic review agents, and writes an auditable JSON proposal. It never invents evidence and never edits the source CV. TXT/Markdown/RTF/HTML use the standard library; DOCX uses its OOXML container; PDF analysis is blocked unless the optional `pypdf` adapter is installed. Unsupported or stale proposals stop before writing, and APPLY emits a new output plus diff and applied-change log.

The report stages are: ATS parsing, JD intelligence, keyword strategy, language optimization, recruiter simulation, hiring-manager review, evidence/achievement audit, company-language alignment, interview defense, approval, editor, and final validation.

### Formatting audit

```bash
python -m src.ats_agent.cli format resume.txt --json
```

The audit flags dense lines, tabular spacing, decorative bullets, missing standard headings, and files without extractable text. It returns recommendations for a one-column, text-first layout and never overwrites the source CV.

## Repository map

- `SKILL.md` — portable agent instructions and approval boundary.
- `src/ats_agent/` — dependency-free CLI scaffold.
- `benchmarks/` — anonymized case schema, fixtures, and metric contract.
- `integrations/` — adapter boundaries for Codex/ChatGPT, Claude, VS Code, and a future web dashboard.
- `.github/workflows/ci.yml` — validation, tests, and lint checks on pushes and pull requests.
- `references/` — workflow, benchmark, and integration details.

## Safety boundary

The project does not produce a universal ATS score and does not send applications. Applying edits always requires explicit change IDs and creates a new output artifact.
