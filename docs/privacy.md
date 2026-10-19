# Privacy

The default workflow is local and file-based. It does not send CVs, job descriptions, or evidence to an external service.

Recommended practices:

- Use a stable opaque candidate ID rather than an email address.
- Store run directories outside public repositories.
- Do not commit real CVs, contact details, or employer-confidential evidence.
- Review `proposal.json` and `review.html` before sharing; they contain evidence excerpts and local paths.
- Delete run artifacts when no longer needed.

Any future model-provider adapter must be opt-in, document exactly what leaves the machine, support redaction, and preserve deterministic evidence and approval checks.
