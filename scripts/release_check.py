"""Fail-closed release checks for the trustworthy v1 beta."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from ats_agent import __version__
from ats_agent.benchmark import run

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "1.0.0b1"


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--private-holdout",
        type=Path,
        help="read-only private 60-case public-schema holdout JSONL used only in protected release CI",
    )
    args = parser.parse_args()

    if __version__ != EXPECTED_VERSION:
        raise SystemExit(
            f"package version {__version__!r} does not match beta {EXPECTED_VERSION!r}"
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
        holdout = {
            "case_count": report["case_count"],
            "dataset_sha256": _sha256(path),
            "metrics": report["metrics"],
        }

    print(
        json.dumps(
            {
                "status": "passed",
                "version": __version__,
                "private_holdout": holdout,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
