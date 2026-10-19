# Codex

The project skill lives at `.agents/skills/tailor-cv` and the portable ZIP can be installed or uploaded in a supported Codex environment. It delegates all CV operations to the CLI, asks permission before bootstrap installation, and requires explicit approval before apply.

With only a CV, the same skill starts the native CV-first route: it grounds
suitable role families in the CV, asks the candidate to confirm location and
work-mode facts, searches packaged worldwide public sources, captures each
returned posting, and produces draft proposals. No external AI Job Search
workspace, Bun runtime, or tracker is required; approval is still required per
role before any document output is created.

```text
Use the tailor-cv skill.
CV: ./Raghav_CV.docx
Job description: ./roles/company-analyst.md
Evidence: ./career/project-bank.md
Prepare the proposal and summarize the evidence mapping. Do not approve or apply changes until I send an explicit list of change IDs and variants.
```

For restricted environments, use the pinned manual installation path in the skill’s installation reference.
