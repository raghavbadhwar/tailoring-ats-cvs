# CLI contract

Use `ats-agent COMMAND ...`; successful machine-readable commands write JSON to stdout and failures write JSON to stderr. Core exit codes are 0 and 2–7; adapter bootstrap codes are 20–25. Proposal schema is 5, approval schema is 2, and doctor schema is 1. Every run uses a fresh user-selected directory.
