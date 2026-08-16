#!/usr/bin/env python3
"""Check a local ats-agent installation without changing it."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from typing import Any


PACKAGE_REF = (
    "git+https://github.com/raghavbadhwar/tailoring-ats-cvs.git"
    "@f666ab5a6a3b074fad6f470f986436814b56a3d3"
)


def install_commands() -> dict[str, str]:
    return {
        "uv": f'uv tool install "{PACKAGE_REF}"',
        "pipx": f'pipx install "{PACKAGE_REF}"',
        "manual": (
            "python -m venv .venv && "
            f'.venv/bin/python -m pip install "{PACKAGE_REF}"'
        ),
    }


def check() -> tuple[int, dict[str, Any]]:
    executable = shutil.which("ats-agent")
    if executable is None:
        return 1, {"status": "missing", "install_commands": install_commands()}

    checks: dict[str, int] = {}
    for name, arguments in {
        "doctor": ["doctor"],
        "help": ["--help"],
        "smoke": ["benchmark", "--suite", "smoke"],
    }.items():
        try:
            checks[name] = subprocess.run(
                [executable, *arguments],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            ).returncode
        except (OSError, subprocess.TimeoutExpired):
            checks[name] = 1
    status = "healthy" if not any(checks.values()) else "unhealthy"
    return (0 if status == "healthy" else 1), {
        "status": status,
        "executable": executable,
        "checks": checks,
        "install_commands": install_commands(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    args = parser.parse_args()
    result, payload = check()
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(payload["status"])
        if payload["status"] != "healthy":
            print(payload["install_commands"]["uv"])
    return result


if __name__ == "__main__":
    raise SystemExit(main())
