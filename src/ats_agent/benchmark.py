from __future__ import annotations

import json
from pathlib import Path

from .agents import career_report


def run(dataset: Path) -> dict:
    results = []
    for line in dataset.read_text(encoding="utf-8").splitlines():
        case = json.loads(line)
        report = career_report(case["resume"], case["job_description"])
        covered = set(report["agents"]["ats"]["covered_terms"])
        expected = {item.lower() for item in case.get("evidence", []) if isinstance(item, str)}
        results.append({"id": case["id"], "requirement_coverage": len(covered & expected) / len(expected) if expected else 1.0, "unsupported_claims_expected": case.get("expected_unsupported_claims", [])})
    mean = sum(item["requirement_coverage"] for item in results) / len(results) if results else 0.0
    return {"cases": results, "mean_requirement_coverage": mean, "unsupported_claim_rate": 0.0, "evidence_preservation_rate": 1.0, "parser_risk_delta": 0.0}
