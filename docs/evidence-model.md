# Evidence Model

Every supported factual change references one or more candidate-scoped evidence IDs. An evidence record stores:

- candidate ID;
- exact text;
- source type and file;
- source span, line, paragraph, and document part where available;
- ownership level;
- confidence and verification status;
- fact categories;
- source-content hash.

Ownership levels are ordered:

```text
observed < contributor < direct < lead < owner
```

A rewrite may clarify language but may not exceed the maximum ownership level supported by the original text and referenced evidence.

The ledger rejects duplicate IDs, unknown IDs, and records belonging to another candidate. Job descriptions and company-context documents are never inserted into the candidate evidence ledger.
