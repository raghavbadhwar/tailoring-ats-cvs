# Security Policy

## Supported versions

Security fixes are applied to the latest release branch.

## Reporting

Report vulnerabilities privately to the repository owner. Do not include real CVs, credentials, API keys, or personal data in a public issue.

## Security invariants

- Source documents are never overwritten.
- Job descriptions are never treated as candidate evidence.
- Unknown or cross-candidate evidence IDs are rejected.
- Stale, ambiguous, conflicting, unsupported, and no-op edits are rejected.
- PDF output is blocked without a genuine renderer.
- External model calls are not part of the default runtime.
- `research-jobs` captures only user-listed public HTTPS pages with ordinary Scrapling GET requests; no credentials, redirects, proxies, stealth mode, or browser automation are used.
