"""Report independent Benchmark v3 baselines and measured deltas."""
from __future__ import annotations

import json
from pathlib import Path

from ats_agent.benchmark import run_suite

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    result = run_suite("public", root=ROOT)
    print(
        json.dumps(
            {
                "suite": result["suite"],
                "case_count": result["case_count"],
                "dataset_sha256": result["dataset_sha256"],
                "code_sha": result["code_sha"],
                "baselines": result["baselines"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
