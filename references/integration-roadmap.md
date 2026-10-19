# Agent integration roadmap

The first supported integrations are:

1. Portable Agent Skill for Codex and other Agent Skills clients.
2. Claude Code plugin that loads the same skill.
3. `ats-cv` adapter launcher that delegates to `ats-agent`.

All integrations use the same CLI, proposal schemas, approval manifests, exit
codes, and document outputs. No adapter can approve changes automatically. MCP
and web interfaces remain out of scope for the first adapter release.
