# Architecture

```mermaid
flowchart TD
    A[CV + JD + Evidence] --> B[Safe Ingestion]
    B --> C[Candidate Evidence Ledger]
    B --> D[Requirement and Hard-Gate Extraction]
    C --> E[Requirement-to-Evidence Mapping]
    D --> E
    E --> F[Protected Rewrite Variants]
    F --> G[Markdown and HTML Review]
    G --> H{Human Approval}
    H -->|Approved IDs + variants| I[Deterministic Apply Engine]
    I --> J[DOCX Preserve or ATS Rebuild]
    J --> K[Re-parse + Diff + Audit Log]
```

The intelligence layer may propose language, but evidence validation, approval, hashing, edit application, and final verification remain deterministic.

## Boundaries

- `ingestion.py` reads documents and reports quality.
- `evidence.py` owns candidate facts and provenance.
- `requirements.py` owns JD requirements, hard gates, and mappings.
- `rewriting.py` constructs safe variants from supported facts.
- `validation.py` prevents factual and ownership escalation.
- `documents.py` performs anchored edits.
- `workflow.py` coordinates the contract without bypassing a boundary.
