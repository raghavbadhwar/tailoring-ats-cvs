# Integration scaffolding

The core contract is file-based and client-neutral. Each future adapter should call the same CLI, preserve JSON proposal/change schemas, and stop at the human approval boundary.

Planned adapters are documented in `../references/integration-roadmap.md`; this directory intentionally contains no provider credentials, network calls, or extension boilerplate.
