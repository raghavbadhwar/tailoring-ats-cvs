"""Validate the portable skill contract, benchmark, and executable examples."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert skill.startswith("---\nname: tailoring-ats-cvs\n")
    for phrase in ("PROPOSE", "APPROVE", "APPLY", "Never treat the job description"):
        assert phrase in skill, phrase

    cases = [
        json.loads(line)
        for line in (ROOT / "benchmarks/datasets/cases_v2.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(cases) >= 100
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))
    for case in cases:
        for key in ("resume", "job_description", "expected_supported_terms", "expected_unsupported_terms"):
            assert key in case, (case["id"], key)

    manifest = json.loads((ROOT / "examples/approved_changes.json").read_text(encoding="utf-8"))
    assert manifest["proposal"] == "proposal.json"
    assert manifest["selections"]
    assert manifest["mode"] in {"preserve", "rebuild"}
    print(f"skill validation passed: {len(cases)} benchmark cases")


if __name__ == "__main__":
    main()
