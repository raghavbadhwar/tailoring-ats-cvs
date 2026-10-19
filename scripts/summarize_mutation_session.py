#!/usr/bin/env python3
"""Summarize a Cosmic Ray JSONL dump without exposing test output."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def summarize(dump: Path) -> dict[str, object]:
    records = []
    outcomes: Counter[str] = Counter()
    for number, line in enumerate(dump.read_text(encoding="utf-8").splitlines(), 1):
        try:
            work, result = json.loads(line)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError(f"mutation-pilot: invalid dump line {number}") from exc
        if not isinstance(work, dict) or not isinstance(result, dict):
            raise ValueError(f"mutation-pilot: incomplete dump line {number}")
        mutations = work.get("mutations")
        if not isinstance(mutations, list) or len(mutations) != 1:
            raise ValueError(f"mutation-pilot: invalid work item on line {number}")
        mutation = mutations[0]
        outcome = str(result.get("test_outcome") or result.get("worker_outcome") or "unknown")
        outcomes[outcome] += 1
        records.append(
            {
                "module": mutation["module_path"],
                "definition": mutation.get("definition_name"),
                "operator": mutation["operator_name"],
                "occurrence": mutation["occurrence"],
                "outcome": outcome,
            }
        )
    if not records:
        raise ValueError("mutation-pilot: dump contains no results")
    return {
        "schema_version": 1,
        "status": "completed" if outcomes["killed"] else "no_mutation_killed",
        "mutation_count": len(records),
        "outcomes": dict(sorted(outcomes.items())),
        "records": records,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dump", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    summary = summarize(args.dump)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(
        f"mutation-pilot: {summary['mutation_count']} mutations; "
        f"outcomes={summary['outcomes']}"
    )
    return 0 if summary["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
