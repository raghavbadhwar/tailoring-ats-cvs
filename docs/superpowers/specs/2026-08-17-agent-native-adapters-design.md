# Agent-native adapters

The local `ats-agent` CLI is canonical. Codex and Claude Code share one portable
skill and only discover, permissionedly install, and delegate to that CLI. The
first release has no MCP, plugin-side candidate storage, or remote processing.

Each request uses a fresh user-selected run directory. Adapters preserve JSON
stdout and documented exit codes, stop after proposal summary, and require an
explicit change-and-variant allow-list before approval. Distribution consists of
a wheel plus deterministic skill and plugin archives. Public beta checks do not
replace protected holdout and release checks required for stable publication.
