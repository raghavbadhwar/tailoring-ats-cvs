"""Validate Benchmark v3 scale, labels, and semantic diversity."""
from __future__ import annotations

import json
from pathlib import Path

from ats_agent.benchmark import SUITE_FILENAMES, load_cases, validate_cases

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    expected_counts = {
        "public": 180,
        "adversarial": 60,
        "documents": 30,
        "human": 50,
    }
    reports = {}
    for suite, minimum in expected_counts.items():
        cases = load_cases(ROOT / SUITE_FILENAMES[suite])
        if len(cases) < minimum:
            raise SystemExit(
                f"{suite} suite has {len(cases)} cases; expected at least {minimum}"
            )
        diagnostics = validate_cases(cases, suite=suite)
        failing = {
            key: value
            for key, value in diagnostics.items()
            if key
            in {
                "duplicate_pairs",
                "numeric_only_duplicates",
                "overrepresented_templates",
                "overrepresented_role_families",
                "missing_required_fields",
            }
            and value
        }
        if failing:
            raise SystemExit(
                "benchmark diversity validation failed: "
                + json.dumps({suite: failing}, sort_keys=True)
            )
        reports[suite] = {"case_count": len(cases), "status": "valid"}
    print(json.dumps(reports, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
