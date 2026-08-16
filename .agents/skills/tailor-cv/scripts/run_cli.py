"""Delegate an exact argument list to a previously verified ats-agent CLI."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ensure_cli import EXIT_CODES, check_cli

DEFAULT_POLICY = Path(__file__).resolve().parents[1] / "assets" / "bootstrap-policy.json"


def resolve_cli(policy_path: Path) -> str:
    override = os.environ.get("ATS_AGENT_EXECUTABLE_OVERRIDE")
    if override:
        path = Path(override).expanduser().resolve()
        if not path.is_file():
            raise RuntimeError("ATS_AGENT_EXECUTABLE_OVERRIDE is not a file")
        return str(path)
    status = check_cli(policy_path)
    if status.get("status") != "ready":
        raise RuntimeError(json.dumps(status, sort_keys=True))
    return str(status["executable"])


def run_agent_cli(arguments: list[str], policy_path: Path) -> int:
    executable = resolve_cli(policy_path)
    command = [executable, *arguments]
    if executable.endswith(".py"):
        command = [sys.executable, *command]
    return subprocess.run(command, text=True, shell=False).returncode


def main(argv: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    if not values or values[0] != "--":
        print("run_cli.py requires -- before delegated arguments", file=sys.stderr)
        return 2
    try:
        return run_agent_cli(values[1:], DEFAULT_POLICY)
    except RuntimeError as exc:
        try:
            reason = json.loads(str(exc))
        except json.JSONDecodeError:
            reason = {"status": "unhealthy", "error": str(exc)}
        print(json.dumps({"schema_version": 1, "status": "adapter_blocked", "reason": reason}), file=sys.stderr)
        return EXIT_CODES.get(str(reason.get("status")), 24)


if __name__ == "__main__":
    raise SystemExit(main())
