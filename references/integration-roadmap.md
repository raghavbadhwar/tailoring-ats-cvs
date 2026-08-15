# Integration roadmap

- **ChatGPT/Codex:** package `SKILL.md` under the client's skill directory and invoke the CLI for local, approval-gated artifacts.
- **Claude:** expose the same `SKILL.md` and JSON proposal schema; keep adapters thin and client-specific.
- **VS Code:** add commands that call the CLI and open proposal/output files; no editor extension is required by the core.
- **Web dashboard:** later, place an authenticated UI over the CLI/service boundary. It must preserve local approval, provenance, and no-submit defaults.

No provider SDK or network connector is part of this scaffold.
