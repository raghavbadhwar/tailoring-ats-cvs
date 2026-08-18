# Claude Code

```bash
git clone https://github.com/raghavbadhwar/tailoring-ats-cvs.git
cd tailoring-ats-cvs
claude --plugin-dir .
```

Invoke `/tailoring-ats-cvs:tailor-cv resume.docx job-description.md`. For discovery, use the existing AI Job Search workspace and its existing low-volume public LinkedIn skill when relevant; retain roles, export its read-only unfiltered public-jobs JSON, then run `ats-agent research-jobs` with the same portable skill. Do not copy discovery, ranking, portal, or tracker logic into the plugin. For a role-relevant unsupported gap, ask neutrally whether the candidate genuinely did it. A bare yes is never CV text: after yes, require a confirmed activity and setting or timeframe, write the truthful response to a candidate-owned supplemental evidence artifact in the run directory, then rebuild the draft with the existing `--evidence` option. The source CV stays unchanged and the fresh draft still needs explicit approval before apply. A release bundle can be loaded with `unzip tailoring-ats-cvs-claude-plugin-v1.0.0-beta.3.zip` then `claude --plugin-dir ./tailoring-ats-cvs`. Marketplace publication is optional and later.
