# Claude Code

```bash
git clone https://github.com/raghavbadhwar/tailoring-ats-cvs.git
cd tailoring-ats-cvs
claude --plugin-dir .
```

Invoke `/tailoring-ats-cvs:tailor-cv resume.docx job-description.md` for a known role, or invoke it with only `resume.docx` for the complete CV-first flow. The latter grounds role directions, asks the candidate to confirm locations and work modes, searches packaged worldwide public sources, captures job descriptions, and produces ranked draft proposals. It requires no AI Job Search checkout, Bun runtime, tracker, or manual JSON export. The skill asks for explicit approval before applying any change. A release bundle can be loaded with `unzip tailoring-ats-cvs-claude-plugin-v1.0.0-beta.3.zip` then `claude --plugin-dir ./tailoring-ats-cvs`. Marketplace publication is optional and later.
