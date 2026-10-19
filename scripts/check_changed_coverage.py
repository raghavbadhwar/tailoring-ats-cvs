#!/usr/bin/env python3
"""Fail when changed executable ats_agent statements were not executed."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HUNK = re.compile(r"^@@ [^+]*\+(?P<start>\d+)(?:,(?P<count>\d+))? @@")


def fail(message: str) -> None:
    raise ValueError(f"coverage-guard: {message}")


def git(*args: str) -> str:
    done = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)
    if done.returncode:
        fail(done.stderr.strip() or "git command failed")
    return done.stdout


def added_lines(base: str, path: str) -> set[int]:
    output = git("-c", "core.quotePath=false", "diff", "--no-ext-diff", "--no-renames", "--unified=0", "--diff-filter=AM", f"{base}...HEAD", "--", path)
    result: set[int] = set()
    for line in output.splitlines():
        match = HUNK.match(line)
        if match:
            start, count = int(match["start"]), int(match["count"] or "1")
            result.update(range(start, start + count))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--coverage-json", required=True, type=Path)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        try:
            report = json.loads(args.coverage_json.read_text(encoding="utf-8"))["files"]
        except FileNotFoundError:
            fail("coverage JSON missing")
        except (json.JSONDecodeError, KeyError, TypeError):
            fail("coverage JSON is invalid")
        if not isinstance(report, dict):
            fail("coverage JSON is invalid")
        names = git("-c", "core.quotePath=false", "diff", "--no-ext-diff", "--no-renames", "--name-only", "-z", "--diff-filter=AM", f"{args.base}...HEAD", "--", "src/ats_agent").split("\0")
        missing: list[str] = []
        executable = 0
        changed = 0
        for name in filter(lambda p: p.startswith("src/ats_agent/") and p.endswith(".py"), names):
            candidates = [
                record
                for key, record in report.items()
                if (Path(key) if Path(key).is_absolute() else ROOT / key).resolve()
                == (ROOT / name).resolve()
            ]
            if len(candidates) != 1:
                fail(f"coverage entry missing or ambiguous for {name}")
            record = candidates[0]
            if not isinstance(record, dict):
                fail("coverage JSON is invalid")
            executed, absent = set(record.get("executed_lines", [])), set(record.get("missing_lines", []))
            changed_executable = sorted(added_lines(args.base, name) & (executed | absent))
            if changed_executable:
                changed += 1
            for line in changed_executable:
                executable += 1
                if line not in executed:
                    missing.append(f"{name}:{line}")
        if missing:
            fail(f"{len(missing)} changed executable lines are unexecuted: {', '.join(missing)}")
        print(f"changed-source coverage: {executable}/{executable} executed statement lines (100.00%)")
        print(f"base: {args.base} | files: {changed} | missing: none")
        return 0
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 0 if args.report_only else 1


if __name__ == "__main__":
    raise SystemExit(main())
