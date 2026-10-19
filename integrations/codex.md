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

For discovery, use the existing AI Job Search workspace first, including its existing low-volume public LinkedIn skill when relevant. Retain roles without eligibility filtering and pass its read-only unfiltered export to `ats-agent research-jobs`; do not alter the export or tracker. Write the result, provenance, supported changes, and gaps in chat. For each role-relevant unsupported gap ask: "Have you genuinely done work involving <gap>? If yes, what did you do, and in what setting or timeframe? Include a result or artifact if available." A bare yes is not CV text. After sufficient truthful detail, have the engine validate and append a candidate-owned proof card in the selected run directory, then rebuild with `--evidence-card`; the source CV stays unchanged and the fresh digest still requires explicit approval before apply. Declined, insufficient, contradictory, corrected, and withdrawn answers must never authorize a rewrite.
