# Engineering Decision Log — multi-agent review (2026-08-22)

Structured design review per the multi-agent brainstorming protocol:
Skeptic → Constraint Guardian → User Advocate → Arbiter.
Final disposition: **APPROVED** with the resolutions below baked in.

| ID | Objection | Resolution |
|----|-----------|------------|
| S1 | PTY false-positives would hang agent sessions | `tailor` modes are explicit: `--interactive` XOR `--approve-from`; adapters pass the file |
| S2 | Liveness check couples local writes to site availability | Tiered: DEAD→block · CHANGED→warn(+confirm interactively) · infra-fail→warn-only |
| S3 | ESCO adoption unproven, likely poor India-internship fit | Evidence-gated: adopted only if measured gap >15% on real-JD corpus |
| S4 | Synthetic benchmark circularity | Frozen real-JD corpus (12 live postings via ATS APIs) landed in P2 and asserted by tests |
| S5 | Idempotency digest underspecified | Digest = candidate ID+CV+JD+candidate evidence+company context+rewrite-provider identity and configuration+engine version; rerun equality additionally requires normalized selections match |
| C1 | No performance budget | ≤4 capture workers, per-host ≥1s; **10-role propose budget <90 s** (`scripts/perf_batch_benchmark.py`) |
| C2 | ATS rate-limit exposure | Per-host pacing, Retry-After honored, 24 h TTL response cache, soft ≤25 URLs/run |
| C3 | LLM provider privacy/injection | `[llm]` path is opt-in reference script; receipts disclose external calls; deterministic validation gates ALL provider output (injection test proves block) |
| C4 | Journal statefulness | Journal carries `schema_version` from birth |
| C5 | CI cost creep | Fuzz capped at 50 examples in CI runs |
| C6 | Windows parity | `NO_COLOR` respected; matrix covered by cross-platform CI jobs |
| U1 | Approval fatigue | Explicit persisted manifests only; users name each change and variant so reviewed wording remains bound to approval. |
| U2 | Card leads with process | Delivery card is outcome-first (`✔ role — ready: path`) |
| U3 | No undo story | Documented regenerate semantics: outputs are disposable; source CV immutable |
| U4 | Jargon leaks | Plain language on human surfaces; digests confined to `--json` outputs |
| D6 | Version sweep pain (19 files) | P0 single-sourcing: bundles/verifier/validator derive from `pyproject.toml`; contract drift fails loudly |

## ESCO decision (measured, not guessed)

`scripts/measure_alias_coverage.py` over the frozen corpus:

```json
{"aggregate_gap": 0.7604, "threshold": 0.15, "decision": "adopt_esco_enrichment"}
```

The corrected HTML-aware measurement found 96 heuristic requirement lines in
12 of 12 real internship postings and missed 73. The 76.04% gap crosses the
reviewed threshold, so ontology enrichment is now recommended. This heuristic
report is a prioritization signal, not a substitute for the labeled corpus and
human evaluation required by the stable-release gates.

## Addendum — deep-dive mechanism (2026-08-23)

- Discovery boundary refined: official ATS *syndication feeds* are treated as
  structured public data (they exist to be read), distinct from board scraping;
  Scrapling remains the labelled fallback for plain careers pages.
- Verdict honesty: ATS feeds expose only currently-published postings, so
  "internship program evidence" reflects live titles; closed-cohort history is
  out of scope and never claimed.
- Multi-word aspirations suppress their own sub-tokens ("data" ⊂ "data
  analyst") so generic single words cannot manufacture direct matches.
- Partial-failure isolation: one dead feed yields NO_SIGNAL for that company;
  the rest of a multi-board dive completes.
