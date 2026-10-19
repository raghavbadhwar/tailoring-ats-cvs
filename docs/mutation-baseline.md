# Mutation Pilot Baseline

The pilot is a bounded assertion-strength signal, not a quality score and not
evidence that a CV will pass an employer's screener.

## Local baseline

- Commit: `4306d1c`
- Host: macOS, Python 3.14 project environment
- Cosmic Ray: 8.7.0
- Execution: detached disposable worktree with `PYTHONPATH` pinned to that copy
- Runtime: 5 seconds
- Selected: four deterministic mutations, one per authority-boundary module
- Result: four killed, zero survived, zero incompetent
- Primary checkout: unchanged; temporary worktree removed

| Module | Definition | Mutation | Result | Classification |
|---|---|---|---|---|
| `workflow.py` | `_validate_research_freshness` | `core/AddNot` | killed | test detected changed freshness behavior |
| `evidence.py` | `_proof_text` | `core/AddNot` | killed | test detected changed proof-card validation |
| `documents.py` | `patch_document` | `core/AddNot` | killed | test detected changed document application |
| `validation.py` | `validate_change` | `core/AddNot` | killed | test detected changed claim validation |

There are no survivors to classify as `equivalent`, `out-of-scope`, or
`test-gap` in this run.

## Rollout gate

Linux/Python 3.10 baselines completed: **0 of 2**. The scheduled/manual GitHub
Actions job therefore remains `continue-on-error` and does not block pull
requests. Promote it to a required check only after two Linux runs each finish
within ten minutes, import the disposable worktree package, clean up reliably,
and leave no unclassified `test-gap` survivor.
