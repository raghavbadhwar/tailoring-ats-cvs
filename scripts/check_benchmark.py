"""Fail CI when benchmark safety or coverage regressions cross release gates."""
from __future__ import annotations

from pathlib import Path

from ats_agent.benchmark import run


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    result = run(root / "benchmarks" / "datasets" / "cases_v2.jsonl")
    assert result["case_count"] >= 100, result
    assert (result["supported_requirement_recall"] or 0) >= 0.90, result
    assert (result["unsupported_requirement_detection_rate"] or 0) >= 0.90, result
    assert (result["evidence_provenance_coverage"] or 0) >= 0.99, result
    assert (result["hard_gate_accuracy"] or 0) >= 0.90, result
    assert result["unsafe_rewrite_count"] == 0, result
    assert result["forbidden_rewrite_hit_count"] == 0, result
    print({
        "case_count": result["case_count"],
        "supported_requirement_recall": result["supported_requirement_recall"],
        "unsupported_requirement_detection_rate": result["unsupported_requirement_detection_rate"],
        "evidence_provenance_coverage": result["evidence_provenance_coverage"],
        "hard_gate_accuracy": result["hard_gate_accuracy"],
        "unsafe_rewrite_count": result["unsafe_rewrite_count"],
        "forbidden_rewrite_hit_count": result["forbidden_rewrite_hit_count"],
    })


if __name__ == "__main__":
    main()
