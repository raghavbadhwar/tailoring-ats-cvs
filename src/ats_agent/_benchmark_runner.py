"""Benchmark v3 suite orchestration and report writing."""
from __future__ import annotations

import json
import platform
import sys
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any, Sequence

from ._benchmark_adversarial import _evaluate_adversarial_case
from ._benchmark_documents import _evaluate_document_case
from ._benchmark_legacy import _legacy_result
from ._benchmark_load import load_cases
from ._benchmark_metrics import _baselines, _standard_metrics, _sum
from ._benchmark_public import BenchmarkGateError, SUITE_FILENAMES
from ._benchmark_standard import _evaluate_standard_case
from ._benchmark_validate import _code_sha, _metric, _sha256, validate_cases


def _resolve_suite_path(suite: str, root: Path | None) -> tuple[Path, Path]:
    if suite not in SUITE_FILENAMES:
        raise ValueError(
            "unknown benchmark suite: "
            + suite
            + "; choose "
            + ", ".join(sorted(SUITE_FILENAMES))
        )
    if root is not None:
        resolved_root = root.expanduser().resolve()
        path = resolved_root / SUITE_FILENAMES[suite]
        return resolved_root, path
    inferred_root = Path(__file__).resolve().parents[2]
    inferred_path = inferred_root / SUITE_FILENAMES[suite]
    if inferred_path.is_file():
        return inferred_root, inferred_path
    if suite != "smoke":
        raise ValueError(
            f"benchmark suite {suite!r} requires a repository checkout"
        )
    packaged = resources.files("ats_agent").joinpath(
        "data/benchmark-v3/smoke.jsonl"
    )
    with resources.as_file(packaged) as path:
        return inferred_root, Path(path)


def run_cases(
    cases: Sequence[dict[str, Any]],
    *,
    suite: str,
    dataset_path: Path,
    root: Path,
) -> dict[str, Any]:
    diagnostics = validate_cases(cases, suite=suite)
    if any(
        diagnostics[key]
        for key in (
            "duplicate_pairs",
            "numeric_only_duplicates",
            "overrepresented_templates",
            "overrepresented_role_families",
            "missing_required_fields",
        )
    ):
        raise BenchmarkGateError(
            "benchmark diversity validation failed: "
            + json.dumps(diagnostics, sort_keys=True)
        )

    if suite in {"smoke", "public"}:
        case_results = [_evaluate_standard_case(case) for case in cases]
        metrics = _standard_metrics(case_results)
        baselines = _baselines(cases, metrics)
    elif suite == "adversarial":
        case_results = [_evaluate_adversarial_case(case) for case in cases]
        passed = sum(bool(result["passed"]) for result in case_results)
        metrics = {
            "adversarial_scenario_pass_rate": _metric(
                passed, len(case_results)
            ),
            "cross_candidate_match_rate": _metric(
                0,
                sum(
                    result["scenario"] == "cross_candidate_evidence"
                    for result in case_results
                )
                or 1,
            ),
        }
        baselines = {
            "v1_deterministic": {
                "scenario_pass_rate": passed / len(case_results)
                if case_results
                else None
            }
        }
    elif suite == "documents":
        case_results = [
            _evaluate_document_case(case, root=root) for case in cases
        ]
        passed = sum(bool(result["passed"]) for result in case_results)
        parsed_expected = sum(bool(case.get("expected_parse")) for case in cases)
        parsed_success = sum(
            bool(result["parsed"]) and bool(case.get("expected_parse"))
            for case, result in zip(cases, case_results)
        )
        metrics = {
            "document_case_pass_rate": _metric(passed, len(case_results)),
            "output_reparse_rate": _metric(
                parsed_success, parsed_expected
            ),
        }
        baselines = {
            "v1_ingestion": {
                "document_case_pass_rate": passed / len(case_results)
                if case_results
                else None
            }
        }
    else:
        case_results = [
            {
                "id": str(case["id"]),
                "status": (
                    "rated"
                    if case.get("ratings") is not None
                    else "awaiting_review"
                ),
            }
            for case in cases
        ]
        rated = sum(case.get("ratings") is not None for case in cases)
        metrics = {
            "human_evaluation_completion": _metric(rated, len(cases))
        }
        baselines = {
            "human_preference": {
                "status": "not_measured" if not rated else "partially_measured"
            }
        }

    result: dict[str, Any] = {
        "schema_version": 3,
        "suite": suite,
        "case_count": len(cases),
        "dataset_path": str(dataset_path),
        "dataset_sha256": _sha256(dataset_path),
        "code_sha": _code_sha(root),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
        "diversity": diagnostics,
        "metrics": metrics,
        "baselines": baselines,
        "measurement_status": {
            "parser_risk_delta": "not_measured",
            "human_preference": (
                "measured"
                if suite == "human"
                and any(case.get("ratings") is not None for case in cases)
                else "not_measured"
            ),
        },
        "cases": case_results,
    }

    if suite in {"smoke", "public"}:
        result.update(
            {
                "supported_requirement_recall": metrics[
                    "evidence_matching_recall"
                ]["value"],
                "unsupported_requirement_detection_rate": metrics[
                    "unsupported_recall"
                ]["value"],
                "evidence_provenance_coverage": metrics[
                    "evidence_provenance_coverage"
                ]["value"],
                "hard_gate_accuracy": metrics["hard_gate_accuracy"]["value"],
                "rewrite_validator_pass_rate": metrics[
                    "rewrite_validator_pass_rate"
                ]["value"],
                "unsafe_rewrite_count": int(
                    _sum(case_results, "unsafe_variants")
                ),
                "forbidden_rewrite_hit_count": int(
                    _sum(case_results, "forbidden_hits")
                ),
                "parser_risk_delta": None,
                "human_rewrite_preference": None,
            }
        )
    return result


def run_suite(
    suite: str,
    *,
    root: Path | None = None,
    report_path: Path | None = None,
) -> dict[str, Any]:
    resolved_root, dataset_path = _resolve_suite_path(suite, root)
    cases = load_cases(dataset_path)
    result = run_cases(
        cases,
        suite=suite,
        dataset_path=dataset_path,
        root=resolved_root,
    )
    if report_path is not None:
        output = report_path.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return result


def run(dataset: Path) -> dict[str, Any]:
    """Run a custom dataset, preserving legacy v0.9 fixture compatibility."""

    path = dataset.expanduser().resolve()
    cases = load_cases(path)
    suite = str(cases[0].get("suite") or "")
    if suite in SUITE_FILENAMES:
        root = Path(__file__).resolve().parents[2]
        return run_cases(
            cases,
            suite=suite,
            dataset_path=path,
            root=root,
        )
    return _legacy_result(cases)
