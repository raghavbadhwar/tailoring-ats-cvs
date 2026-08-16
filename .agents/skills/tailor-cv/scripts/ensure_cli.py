"""Check or, only when explicitly requested, install the canonical CLI."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from packaging.version import InvalidVersion, Version

DEFAULT_POLICY = Path(__file__).resolve().parents[1] / "assets" / "bootstrap-policy.json"
EXIT_CODES = {"ready": 0, "bootstrap_required": 20, "upgrade_required": 21,
              "manual_install_required": 22, "install_failed": 23,
              "post_install_verification_failed": 24, "invalid_policy": 25}


def load_policy(path: Path) -> dict[str, Any]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    required = {"schema_version", "package_name", "minimum_version", "preferred_spec",
                "git_fallback_spec", "executable", "doctor_arguments",
                "supported_installers", "requires_explicit_approval"}
    missing = sorted(required - policy.keys())
    if missing:
        raise ValueError("bootstrap policy missing fields: " + ", ".join(missing))
    if policy["schema_version"] != 1 or policy["requires_explicit_approval"] is not True:
        raise ValueError("unsupported or unsafe bootstrap policy")
    Version(str(policy["minimum_version"]))
    return policy


def installation_commands(policy: dict[str, Any]) -> list[dict[str, Any]]:
    spec, git = str(policy["preferred_spec"]), str(policy["git_fallback_spec"])
    return [
        {"manager": "uv", "command": ["uv", "tool", "install", spec], "display": f'uv tool install "{spec}"'},
        {"manager": "pipx", "command": ["pipx", "install", spec], "display": f'pipx install "{spec}"'},
        {"manager": "uv-git", "command": ["uv", "tool", "install", git], "display": f'uv tool install "{git}"'},
    ]


def _manual(policy: dict[str, Any]) -> list[str]:
    return [f'python -m venv ~/.local/share/tailoring-ats-cvs/venv && ~/.local/share/tailoring-ats-cvs/venv/bin/python -m pip install "{policy["preferred_spec"]}"']


def check_cli(policy_path: Path) -> dict[str, Any]:
    policy = load_policy(policy_path)
    executable = shutil.which(str(policy["executable"]))
    if executable is None:
        return {"schema_version": 1, "status": "bootstrap_required", "requires_user_approval": True,
                "recommended_installer": "uv", "commands": installation_commands(policy)}
    completed = subprocess.run([executable, *map(str, policy["doctor_arguments"])], capture_output=True,
                               text=True, shell=False, timeout=60)
    if completed.returncode:
        return {"schema_version": 1, "status": "unhealthy", "exit_code": completed.returncode,
                "stderr": completed.stderr[-4000:]}
    try:
        payload = json.loads(completed.stdout)
        installed, minimum = Version(str(payload["package"]["version"])), Version(str(policy["minimum_version"]))
    except (KeyError, TypeError, json.JSONDecodeError, InvalidVersion) as exc:
        return {"schema_version": 1, "status": "unhealthy", "reason": str(exc)}
    if installed < minimum:
        return {"schema_version": 1, "status": "upgrade_required", "version": str(installed),
                "minimum_version": str(minimum), "requires_user_approval": True,
                "commands": installation_commands(policy)}
    if payload.get("strict_check", {}).get("status") != "passed":
        return {"schema_version": 1, "status": "unhealthy", "reason": "strict doctor check did not pass"}
    return {"schema_version": 1, "status": "ready", "executable": executable, "version": str(installed)}


def install_cli(policy_path: Path, manager: str) -> dict[str, Any]:
    policy = load_policy(policy_path)
    commands = installation_commands(policy)
    selected = next((item for item in commands if item["manager"] == manager), None)
    if manager == "auto":
        selected = next((item for item in commands if shutil.which(item["command"][0])), None)
    if selected is None or (executable := shutil.which(selected["command"][0])) is None:
        return {"schema_version": 1, "status": "manual_install_required", "manual_instructions": _manual(policy)}
    completed = subprocess.run([executable, *selected["command"][1:]], capture_output=True, text=True, shell=False, timeout=600)
    if completed.returncode:
        return {"schema_version": 1, "status": "install_failed", "exit_code": completed.returncode, "stderr": completed.stderr[-4000:]}
    verified = check_cli(policy_path)
    if verified.get("status") != "ready":
        return {"schema_version": 1, "status": "post_install_verification_failed", "verification": verified}
    return {"schema_version": 1, "status": "installed", "manager": selected["manager"], "verification": verified}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--install", action="store_true")
    parser.add_argument("--manager", choices=("auto", "uv", "pipx", "uv-git"), default="auto")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    args = parser.parse_args(argv)
    try:
        result = install_cli(args.policy, args.manager) if args.install else check_cli(args.policy)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"schema_version": 1, "status": "invalid_policy", "error": str(exc)}
    print(json.dumps(result, sort_keys=True))
    return EXIT_CODES.get(str(result["status"]), 24)


if __name__ == "__main__":
    raise SystemExit(main())
