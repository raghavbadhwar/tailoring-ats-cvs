from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")

assert skill.startswith("---\nname: tailoring-ats-cvs\n")
for stage in ("INGEST", "PROPOSE", "REVIEW", "APPLY"):
    assert f"`{stage}`" in skill, f"missing {stage} workflow stage"
assert re.search(r"explicit(?:ly)?\s+approv", skill, re.IGNORECASE), (
    "skill must require explicit approval before applying changes"
)
assert "same candidate" in skill.lower(), "candidate isolation safeguard is missing"
assert "source sha-256" in skill.lower(), "stale-source safeguard is missing"


def load_cases(path: Path) -> list[dict]:
    cases = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert cases, f"benchmark dataset is empty: {path}"
    ids: list[str] = []
    for case in cases:
        assert isinstance(case.get("id"), str) and case["id"].strip()
        assert isinstance(case.get("resume"), str)
        assert isinstance(case.get("job_description"), str)
        assert isinstance(case.get("evidence"), list)
        assert isinstance(case.get("expected_hard_gates"), list)
        assert isinstance(case.get("expected_unsupported_claims"), list)
        ids.append(case["id"])
    assert len(ids) == len(set(ids)), f"duplicate benchmark case IDs in {path}"
    return cases


load_cases(ROOT / "benchmarks/datasets/cases.jsonl")
packaged_cases = load_cases(ROOT / "src/ats_agent/data/cases.jsonl")
assert len(packaged_cases) >= 3, "packaged smoke benchmark must contain at least 3 cases"

print("skill validation passed")
