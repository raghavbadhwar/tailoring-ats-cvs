# Claude Code

```bash
git clone https://github.com/raghavbadhwar/tailoring-ats-cvs.git
cd tailoring-ats-cvs
claude --plugin-dir .
```

Invoke `/tailoring-ats-cvs:tailor-cv resume.docx job-description.md`. For discovery, have AI Job Search export its unfiltered public-jobs JSON, then run `ats-agent research-jobs` with the same portable skill; do not copy discovery, ranking, portal, or tracker logic into the plugin. The skill asks for explicit approval before applying any change. A release bundle can be loaded with `unzip tailoring-ats-cvs-claude-plugin-v1.0.0-beta.3.zip` then `claude --plugin-dir ./tailoring-ats-cvs`. Marketplace publication is optional and later.
