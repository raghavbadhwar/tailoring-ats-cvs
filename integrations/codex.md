# Codex

## Native install (recommended)

```bash
python scripts/install_codex_skill.py
```

Installs or upgrades `${CODEX_HOME:-~/.codex}/skills/tailor-cv` from this
repository. It is idempotent, refuses downgrades without `--force`, and
prints a ready-to-paste Codex prompt on success. `--check` reports the
installed version; `--uninstall` removes it.

Then paste into Codex:

```text
Use the tailor-cv skill.
CV: ./Raghav_CV.docx
Job description: ./roles/company-analyst.md
Evidence: ./career/project-bank.md
Prepare the proposal and summarize the evidence mapping in this chat. Do not ask me to open local output files. Do not approve or apply changes until I send an explicit list of change IDs and variants.
```

The skill delegates all CV operations to the CLI, asks permission before
bootstrap installation, and requires explicit approval before apply.

For restricted environments, use the pinned manual installation path in the skill’s installation reference.

For discovery, use the existing AI Job Search workspace first, including its existing low-volume public LinkedIn skill when relevant. Retain roles without eligibility filtering and pass its read-only unfiltered export to `ats-agent research-jobs`; do not alter the export or tracker. Present results and follow-up questions in chat, not as a request to open artifacts. If a role-relevant requirement is unsupported, ask the candidate neutrally whether they genuinely did it. A bare yes is not CV text: after yes, require a confirmed activity plus setting or timeframe, save the truthful response as a candidate-owned supplemental evidence artifact in the run directory, and rebuild the draft with the existing `--evidence` option. The source CV stays unchanged, and the fresh draft still requires explicit approval before apply.
