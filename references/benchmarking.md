# Benchmark contract

Each case in `benchmarks/datasets/cases.jsonl` contains anonymized `resume`, `job_description`, `evidence`, `expected_hard_gates`, and `expected_unsupported_claims` fields. Do not store contact details or raw personal documents.

Report at least:

- `unsupported_claim_rate`: unsupported claims introduced / claims introduced;
- `evidence_preservation_rate`: approved supported facts retained / supported facts selected;
- `requirement_coverage_delta`: supported requirement coverage after minus before;
- `parser_risk_delta`: parser-risk findings after minus before.

These are transparent evaluation metrics, not a prediction of an employer's ATS decision.
