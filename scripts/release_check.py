"""Fail-closed release checks for the trustworthy v1 beta."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from ats_agent import __version__
from ats_agent.benchmark import run

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "1.0.0b3"


def _run(*command: str) -> None:
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode:
        raise SystemExit(completed.returncode)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _metric(report: dict[str, Any], name: str) -> float:
    value = report["metrics"][name]["value"]
    if value is None:
        raise SystemExit(f"private holdout metric is not measured: {name}")
    return float(value)


def _at_least(report: dict[str, Any], name: str, threshold: float) -> None:
    actual = _metric(report, name)
    if actual < threshold:
        raise SystemExit(
            f"private holdout {name}={actual:.6f} is below {threshold:.6f}"
        )


def _equals(report: dict[str, Any], name: str, expected: float) -> None:
    actual = _metric(report, name)
    if actual != expected:
        raise SystemExit(
            f"private holdout {name}={actual:.6f} does not equal {expected:.6f}"
        )


def _check_private_holdout(report: dict[str, Any]) -> None:
    _at_least(report, "requirement_extraction_precision", 0.94)
    _at_least(report, "requirement_extraction_recall", 0.94)
    _at_least(report, "evidence_matching_precision", 0.95)
    _at_least(report, "evidence_matching_recall", 0.90)
    _at_least(report, "unsupported_precision", 0.95)
    _at_least(report, "unsupported_recall", 0.90)
    _at_least(report, "hard_gate_accuracy", 0.95)
    _equals(report, "evidence_provenance_coverage", 1.0)
    _equals(report, "unsupported_atomic_claim_rate", 0.0)
    _equals(report, "ownership_escalation_rate", 0.0)
    _equals(report, "protected_status_violation_rate", 0.0)
    _equals(report, "metric_unit_scope_binding_accuracy", 1.0)
    _at_least(report, "variant_completeness", 0.98)
    _at_least(report, "variant_distinctness", 0.95)
    _at_least(report, "correct_section_placement", 0.97)
    _equals(report, "cross_candidate_match_rate", 0.0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--private-holdout",
        type=Path,
        help="read-only private 60-case public-schema holdout JSONL used only in protected release CI",
    )
    parser.add_argument(
        "--require-holdout",
        action="store_true",
        help="fail closed when --private-holdout is absent (mandatory for stable releases)",
    )
    args = parser.parse_args()

    if __version__ != EXPECTED_VERSION:
        raise SystemExit(
            f"package version {__version__!r} does not match beta {EXPECTED_VERSION!r}"
        )

    if args.require_holdout and args.private_holdout is None:
        raise SystemExit(
            "--require-holdout was set but no private holdout was provided; "
            "stable releases must pass the protected holdout"
        )

    _run(sys.executable, "scripts/check_release_tree.py")
    _run(sys.executable, "scripts/validate_skill.py")
    _run(sys.executable, "scripts/validate_benchmark_diversity.py")
    _run(sys.executable, "scripts/check_benchmark.py")

    holdout = None
    if args.private_holdout is not None:
        path = args.private_holdout.expanduser().resolve()
        if not path.is_file():
            raise SystemExit(f"private holdout is missing: {path}")
        report = run(path)
        if report.get("schema_version") != 3 or "metrics" not in report:
            raise SystemExit("private holdout must use the Benchmark v3 public-case schema")
        if report["case_count"] < 60:
            raise SystemExit(
                f"private holdout has {report['case_count']} cases; expected at least 60"
            )
        _check_private_holdout(report)
        holdout = {
            "executed": True,
            "case_count": report["case_count"],
            "dataset_sha256": _sha256(path),
            "metrics": report["metrics"],
        }
    elif args.require_holdout:
        raise SystemExit("unreachable: require-holdout precheck should have failed")

    print(
        json.dumps(
            {
                "status": "passed",
                "version": __version__,
                "protected_holdout": holdout
                or {
                    "executed": False,
                    "disclosure": (
                        "Protected 60-case private holdout was NOT executed for this "
                        "prerelease. Public Benchmark v3, full CI, and security gates passed."
                    ),
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
