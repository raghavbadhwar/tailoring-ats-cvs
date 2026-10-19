# Workflow contract

The product uses four explicit stages. Safety boundaries do not depend on a model provider.

## 1. INGEST

Read the complete CV, job description, and any candidate-authorized evidence files. Build a candidate-specific evidence ledger containing stable evidence IDs, source files, source spans, confidence, and ownership level.

The job description is a source of requirements and vocabulary. It is never added to the candidate evidence ledger.

Extraction failures block the run. Unsupported binary text must not continue into requirement or recruiter analysis.

## 2. PROPOSE

`PROPOSE` is read-only. It records source hashes and returns:

- parser and formatting risks;
- common hard eligibility gates;
- requirements with JD source spans;
- direct, transferable, or unsupported requirement-to-evidence mappings;
- complete numbered before/after changes;
- evidence IDs and ownership before/after for supported changes;
- unsupported qualification gaps that cannot be applied;
- qualitative recruiter and hiring-manager review signals.

A proposed change is not supported merely because a metric appears in the CV. Every factual addition must be justified by evidence records from the same candidate ledger.

## 3. REVIEW

`REVIEW` never edits the CV. It may render:

- a Markdown audit;
- a self-contained local HTML approval page.

The review displays the requirement-to-evidence matrix, source evidence, exact before/after language, and reasons. Supported changes are selectable. Unsupported gaps are disabled and excluded from the downloaded approval manifest.

## 4. APPLY

`APPLY` accepts only an explicit allow-list of change IDs and enforces:

- proposal/source SHA-256 match;
- valid same-candidate evidence IDs;
- ownership and factual-claim limits;
- exact unique text match;
- no-op and unsupported-operation rejection;
- source overwrite protection;
- genuine output-format support.

The engine produces a duplicate, reopens and verifies it, then writes:

- exact applied changes;
- source/output hashes;
- unified diff;
- validation findings;
- applied-change log.

For ordinary DOCX paragraphs and runs, preserve mode retains styles, lists, tables, headers, and footers. Complex field or hyperlink paragraphs that cannot be patched safely are blocked rather than flattened. PDF output remains disabled until a real renderer is implemented.

## Models and future adapters

Optional models may improve semantic retrieval and prose generation, but they cannot:

- add evidence;
- approve changes;
- bypass protected-fact validation;
- apply document edits directly.

A model response is always treated as a draft and must pass the same deterministic evidence and apply checks.
