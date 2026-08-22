# Installation

Only install after explicit user permission:

```bash
uv tool install "tailoring-ats-cvs[documents]==1.0.0b3"
pipx install "tailoring-ats-cvs[documents]==1.0.0b3"
uv tool install "git+https://github.com/raghavbadhwar/tailoring-ats-cvs.git@v1.0.0-beta.3"
```

For a restricted environment, create an isolated virtual environment and install the pinned package manually.

Validate the portable skill in development with `uvx skills-ref validate .agents/skills/tailor-cv`.
