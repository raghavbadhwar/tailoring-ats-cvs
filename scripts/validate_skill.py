import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
assert skill.startswith("---\nname: tailoring-ats-cvs\n")
assert "PROPOSE" in skill and "APPLY" in skill and "explicit approval" in skill
for path in (ROOT / "benchmarks/datasets/cases.jsonl").read_text(encoding="utf-8").splitlines():
    case = json.loads(path)
    assert case["id"] and isinstance(case["evidence"], list)
print("skill validation passed")
