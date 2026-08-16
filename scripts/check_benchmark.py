"""Enforce the published Benchmark v3 beta release gates."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ats_agent.benchmark import BenchmarkGateError, run_suite

ROOT = Path(__file__).resolve().parents[1]


def _value(report: dict[str, Any], metric: str) -> float:
    value = report["metrics"][metric]["value"]
    if value is None:
        raise BenchmarkGateError(f"{metric} is not measured")
    return float(value)


def _at_least(report: dict[str, Any], metric: str, threshold: float) -> None:
    actual = _value(report, metric)
    if actual < threshold:
        raise BenchmarkGateError(
            f"{metric}={actual:.6f} is below release gate {threshold:.6f}"
        )


def _equals(report: dict[str, Any], metric: str, expected: float) -> None:
    actual = _value(report, metric)
    if actual != expected:
        raise BenchmarkGateError(
            f"{metric}={actual:.6f} does not equal release gate {expected:.6f}"
        )


def _print_requirement_mismatches(report: dict[str, Any]) -> None:
    mismatches = [
        {
            "id": case["id"],
            "unexpected": case.get("unexpected_requirements") or [],
            "missing": case.get("missing_requirements") or [],
        }
        for case in report.get("cases", [])
        if case.get("requirement_fp") or case.get("requirement_fn")
    ]
    if mismatches:
        print("Benchmark v3 requirement mismatches:")
        print(json.dumps(mismatches[:60], indent=2, sort_keys=True))


def _print_variant_mismatches(report: dict[str, Any]) -> None:
    mismatches = [
        {
            "id": case["id"],
            "variant_complete": case.get("variant_complete"),
            "variant_total": case.get("variant_total"),
            "variant_distinct": case.get("variant_distinct"),
            "diagnostics": case.get("variant_diagnostics") or [],
        }
        for case in report.get("cases", [])
        if case.get("variant_complete") != case.get("variant_total")
        or case.get("variant_distinct") != case.get("variant_total")
    ]
    if mismatches:
        print("Benchmark v3 rewrite variant mismatches:")
        print(json.dumps(mismatches[:30], indent=2, sort_keys=True))


def _print_adversarial_failures(report: dict[str, Any]) -> None:
    failures = [
        {
            "id": case.get("id"),
            "scenario": case.get("scenario"),
            "detail": case.get("detail") or "predicate returned false",
        }
        for case in report.get("cases", [])
        if not case.get("passed")
    ]
    if failures:
        print("Benchmark v3 adversarial failures:")
        print(json.dumps(failures, indent=2, sort_keys=True))


def main() -> None:
    public = run_suite(
        "public",
        root=ROOT,
        report_path=ROOT / "benchmarks/v3/reports/public.json",
    )
    adversarial = run_suite(
        "adversarial",
        root=ROOT,
        report_path=ROOT / "benchmarks/v3/reports/adversarial.json",
    )
    documents = run_suite(
        "documents",
        root=ROOT,
        report_path=ROOT / "benchmarks/v3/reports/documents.json",
    )

    _print_requirement_mismatches(public)
    _print_variant_mismatches(public)
    _print_adversarial_failures(adversarial)
    _at_least(public, "requirement_extraction_precision", 0.94)
    _at_least(public, "requirement_extraction_recall", 0.94)
    _at_least(public, "evidence_matching_precision", 0.95)
    _at_least(public, "evidence_matching_recall", 0.90)
    _at_least(public, "unsupported_precision", 0.95)
    _at_least(public, "unsupported_recall", 0.90)
    _equals(public, "evidence_provenance_coverage", 1.0)
    _at_least(public, "hard_gate_accuracy", 0.95)
    _equals(public, "unsupported_atomic_claim_rate", 0.0)
    _equals(public, "ownership_escalation_rate", 0.0)
    _equals(public, "protected_status_violation_rate", 0.0)
    _at_least(public, "metric_unit_scope_binding_accuracy", 1.0)
    _at_least(public, "variant_completeness", 0.98)
    _at_least(public, "variant_distinctness", 0.95)
    _at_least(public, "correct_section_placement", 0.97)
    _equals(public, "cross_candidate_match_rate", 0.0)
    if _value(public, "proposal_latency_ms_p95") >= 2000:
        raise BenchmarkGateError("deterministic proposal p95 must be below 2 seconds")

    _equals(adversarial, "adversarial_scenario_pass_rate", 1.0)
    _equals(adversarial, "cross_candidate_match_rate", 0.0)
    _equals(documents, "document_case_pass_rate", 1.0)
    _equals(documents, "output_reparse_rate", 1.0)

    print(
        json.dumps(
            {
                "status": "passed",
                "public_sha256": public["dataset_sha256"],
                "adversarial_sha256": adversarial["dataset_sha256"],
                "documents_sha256": documents["dataset_sha256"],
                "code_sha": public["code_sha"],
                "case_count": (
                    public["case_count"]
                    + adversarial["case_count"]
                    + documents["case_count"]
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
