# Codex

The project skill lives at `.agents/skills/tailor-cv` and the portable ZIP can be installed or uploaded in a supported Codex environment. It delegates all CV operations to the CLI, asks permission before bootstrap installation, and requires explicit approval before apply.

```text
Use the tailor-cv skill.
CV: ./Raghav_CV.docx
Job description: ./roles/company-analyst.md
Evidence: ./career/project-bank.md
Prepare the proposal and summarize the evidence mapping. Do not approve or apply changes until I send an explicit list of change IDs and variants.
```

For restricted environments, use the pinned manual installation path in the skill’s installation reference.

For discovery, use the existing AI Job Search workspace first, including its existing low-volume public LinkedIn skill when relevant. Retain roles without eligibility filtering and pass its read-only unfiltered export to `ats-agent research-jobs`; do not alter the export or tracker. If a role-relevant requirement is unsupported, ask the candidate neutrally whether they genuinely did it. A bare yes is not CV text: after yes, require a confirmed activity plus setting or timeframe, save the truthful response as a candidate-owned supplemental evidence artifact in the run directory, and rebuild the draft with the existing `--evidence` option. The source CV stays unchanged, and the fresh draft still requires explicit approval before apply.
