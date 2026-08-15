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
        claims = report["agents"]["evidence"]["claims"]
        detected_unsupported = sum(not row["has_evidence"] for row in claims)
        results.append({"id": case["id"], "requirement_coverage": len(covered & expected) / len(expected) if expected else 1.0, "unsupported_claims_expected": case.get("expected_unsupported_claims", []), "unsupported_claim_rate": detected_unsupported / max(len(claims), 1), "unsupported_claims_detected": detected_unsupported, "evidence_preservation_rate": sum(row["has_evidence"] for row in claims) / max(len(claims), 1)})
    mean = sum(item["requirement_coverage"] for item in results) / len(results) if results else 0.0
    return {"cases": results, "mean_requirement_coverage": mean, "unsupported_claim_rate": sum(item["unsupported_claim_rate"] for item in results) / len(results) if results else 0.0, "evidence_preservation_rate": sum(item["evidence_preservation_rate"] for item in results) / len(results) if results else 0.0, "parser_risk_delta": None, "measurement_status": {"parser_risk_delta": "not_implemented"}}
