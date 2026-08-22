"""Check or, only after one explicit consent, install the canonical CLI.

Resolution order for the ``ats-agent`` executable:

1. ``ATS_AGENT_EXECUTABLE_OVERRIDE`` environment variable
2. the install-state manifest written by a previous successful install
3. ``PATH``

``--install`` walks the ordered tiers from the bootstrap policy under a
single consent: each tier is attempted in turn and the first verified
success wins. The state manifest records where the engine lives so later
checks keep working even when the chosen tier does not put anything on
``PATH`` (the isolated-venv tier).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_POLICY = Path(__file__).resolve().parents[1] / "assets" / "bootstrap-policy.json"
EXIT_CODES = {"ready": 0, "bootstrap_required": 20, "upgrade_required": 21,
              "manual_install_required": 22, "install_failed": 23,
              "post_install_verification_failed": 24, "invalid_policy": 25}
VERSION_PATTERN = re.compile(r"^(?P<release>\d+(?:\.\d+)*)(?:(?P<stage>a|b|rc)(?P<number>\d+))?$")
OVERRIDE_ENV = "ATS_AGENT_EXECUTABLE_OVERRIDE"


class CompletedShim:
    """Minimal subprocess result stand-in for OSError paths."""

    def __init__(self, *, returncode: int, stderr: str):
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ""


def version_key(raw: str) -> tuple[tuple[int, ...], int, int]:
    """Compare the stable/a/b/rc versions accepted by this pinned bootstrap policy."""
    match = VERSION_PATTERN.fullmatch(raw)
    if match is None:
        raise ValueError(f"unsupported version: {raw}")
    release = [int(part) for part in match.group("release").split(".")]
    while len(release) > 1 and release[-1] == 0:
        release.pop()
    stage = {"a": 0, "b": 1, "rc": 2, None: 3}[match.group("stage")]
    return tuple(release), stage, int(match.group("number") or 0)


def load_policy(path: Path) -> dict[str, Any]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    schema = policy.get("schema_version")
    if schema != 2:
        raise ValueError(
            f"unsupported bootstrap policy schema_version {schema!r}; "
            "regenerate from the current repository"
        )
    required = {"package_name", "minimum_version", "preferred_spec",
                "git_fallback_spec", "executable", "doctor_arguments",
                "requires_explicit_approval", "state_file", "install_attempts"}
    missing = sorted(required - policy.keys())
    if missing:
        raise ValueError("bootstrap policy missing fields: " + ", ".join(missing))
    if policy["requires_explicit_approval"] is not True:
        raise ValueError("unsupported or unsafe bootstrap policy")
    if not policy.get("install_attempts"):
        raise ValueError("bootstrap policy defines no install attempts")
    version_key(str(policy["minimum_version"]))
    return policy


def _state_file(policy: dict[str, Any]) -> Path:
    return Path(str(policy["state_file"])).expanduser()


def read_manifest(policy: dict[str, Any]) -> dict[str, Any]:
    path = _state_file(policy)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_manifest(policy: dict[str, Any], entry: dict[str, Any]) -> None:
    path = _state_file(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entry, sort_keys=True), encoding="utf-8")


def clear_manifest(policy: dict[str, Any]) -> bool:
    path = _state_file(policy)
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


def resolve_executable(policy: dict[str, Any]) -> tuple[str | None, str]:
    """Return the engine path plus how it was resolved."""

    override = os.environ.get(OVERRIDE_ENV)
    if override:
        path = Path(override).expanduser()
        if not path.is_file():
            raise RuntimeError(f"{OVERRIDE_ENV} is not a file: {override}")
        return str(path), "environment override"
    manifest = read_manifest(policy)
    recorded = manifest.get("executable")
    if isinstance(recorded, str) and Path(recorded).expanduser().is_file():
        expanded = str(Path(recorded).expanduser())
        return expanded, f"{manifest.get('tier', 'recorded')} install manifest"
    found = shutil.which(str(policy["executable"]))
    if found:
        return found, "PATH"
    return None, "not found"


def _attempt_steps(policy: dict[str, Any], attempt: dict[str, Any]) -> list[list[str]]:
    """Build the shell-less argv steps for one ordered install attempt."""

    spec = str(policy[attempt["source_key"]])
    manager = attempt["manager"]
    if manager == "uv":
        return [["uv", "tool", "install", spec]]
    if manager == "pipx":
        return [["pipx", "install", spec]]
    if manager == "venv":
        venv_dir = Path("~/.local/share/tailoring-ats-cvs/venv").expanduser()
        python = Path(venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
        pip_install = [str(python), "-m", "pip", "install", spec]
        if python.exists():
            return [pip_install]
        return [
            [sys.executable, "-m", "venv", str(venv_dir)],
            [str(python), "-m", "pip", "install", "--upgrade", "pip"],
            pip_install,
        ]
    raise ValueError(f"unknown installer manager: {manager}")


def _display_for(policy: dict[str, Any], attempt: dict[str, Any]) -> str:
    steps = _attempt_steps(policy, attempt)
    return "; ".join(" ".join(step) for step in steps)


def attempts(policy: dict[str, Any]) -> list[dict[str, Any]]:
    """Enumerate every ordered installation attempt for informed consent."""

    listed = []
    for attempt in policy["install_attempts"]:
        listed.append({
            "tier": str(attempt["tier"]),
            "display": _display_for(policy, attempt),
        })
    return listed


def check_cli(policy_path: Path) -> dict[str, Any]:
    policy = load_policy(policy_path)
    try:
        executable, resolved_from = resolve_executable(policy)
    except RuntimeError as exc:
        return {"schema_version": 2, "status": "unhealthy", "reason": str(exc),
                "message": f"The {OVERRIDE_ENV} override is invalid: {exc}"}
    minimum = str(policy["minimum_version"])
    chain_note = (
        "The engine can be installed after one explicit approval; "
        "attempts run in this order: "
        + " -> ".join(item["tier"] for item in attempts(policy))
    )
    if executable is None:
        return {"schema_version": 2, "status": "bootstrap_required",
                "requires_user_approval": True,
                "recommended_tier": attempts(policy)[0]["tier"],
                "attempts": attempts(policy),
                "message": "ats-agent is not installed yet. " + chain_note}
    completed = subprocess.run([executable, *map(str, policy["doctor_arguments"])],
                               capture_output=True, text=True, shell=False, timeout=60)
    if completed.returncode:
        return {"schema_version": 2, "status": "unhealthy", "exit_code": completed.returncode,
                "stderr": completed.stderr[-4000:],
                "message": f"ats-agent at {executable} failed its strict doctor check.",
                "resolved_from": resolved_from}
    try:
        payload = json.loads(completed.stdout)
        installed = str(payload["package"]["version"])
        installed_key, minimum_key = version_key(installed), version_key(minimum)
    except (KeyError, TypeError, json.JSONDecodeError, ValueError) as exc:
        return {"schema_version": 2, "status": "unhealthy", "reason": str(exc),
                "message": "ats-agent doctor output was not a valid readiness report.",
                "resolved_from": resolved_from}
    if installed_key < minimum_key:
        return {"schema_version": 2, "status": "upgrade_required", "version": installed,
                "minimum_version": minimum, "requires_user_approval": True,
                "resolved_from": resolved_from,
                "attempts": attempts(policy),
                "message": (f"ats-agent {installed} is older than the required {minimum}. "
                            + chain_note)}
    if payload.get("strict_check", {}).get("status") != "passed":
        return {"schema_version": 2, "status": "unhealthy",
                "reason": "strict doctor check did not pass",
                "message": "ats-agent reported an unhealthy strict doctor status.",
                "resolved_from": resolved_from}
    return {"schema_version": 2, "status": "ready", "executable": executable,
            "version": installed, "resolved_from": resolved_from,
            "message": f"ats-agent {installed} is ready ({resolved_from})."}


def _symlink_into_local_bin(executable: str, name: str) -> str | None:
    """Best-effort convenience link; the state manifest is the real resolver."""

    if os.name != "posix":
        return None
    source = Path(executable).resolve()
    target_dir = Path("~/.local/bin").expanduser()
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        link = target_dir / name
        if link.is_symlink() or link.exists():
            return str(link)
        os.symlink(source, link)
        return str(link)
    except OSError:
        return None


def install_cli(policy_path: Path, manager: str) -> dict[str, Any]:
    policy = load_policy(policy_path)
    all_attempts = policy["install_attempts"]
    if manager == "auto":
        selected = list(all_attempts)
    elif manager == "uv":
        selected = [a for a in all_attempts if a["manager"] == "uv"]
    elif manager == "pipx":
        selected = [a for a in all_attempts if a["manager"] == "pipx"]
    else:
        selected = [a for a in all_attempts if a["tier"] == manager]
    if not selected:
        return {"schema_version": 2, "status": "manual_install_required",
                "manual_instructions": [
                    _display_for(policy, attempt) for attempt in all_attempts
                ],
                "message": ("No installation tier matches that choice; run the "
                            "commands manually instead.")}

    failures: list[dict[str, Any]] = []
    for attempt in selected:
        steps = _attempt_steps(policy, attempt)
        failed = False
        stderr_tail = ""
        for step in steps:
            program = shutil.which(step[0]) or step[0]
            try:
                completed = subprocess.run(
                    [program, *step[1:]], capture_output=True, text=True,
                    shell=False, timeout=900,
                )
            except OSError as exc:
                completed = CompletedShim(returncode=127, stderr=str(exc))
            if completed.returncode:
                failed = True
                stderr_tail = getattr(completed, "stderr", "")[-2000:]
                break
        if failed:
            failures.append({"tier": attempt["tier"], "stderr": stderr_tail})
            continue

        verified = check_cli(policy_path)
        if verified.get("status") == "ready":
            executable = str(verified.get("executable") or "")
            version = str(verified.get("version") or "")
            link = _symlink_into_local_bin(
                executable, str(policy["executable"])
            ) if attempt["manager"] == "venv" else None
            write_manifest(policy, {
                "schema_version": 1,
                "tier": attempt["tier"],
                "executable": executable,
                "version": version,
            })
            result = {"schema_version": 2, "status": "installed",
                      "tier": attempt["tier"],
                      "version": version,
                      "verification": verified,
                      "message": (f"Installed ats-agent {version} via "
                                  f"{attempt['tier']} and verified it with a strict "
                                  "doctor check.")}
            if link:
                result["path_link"] = link
            return result
        failures.append({"tier": attempt["tier"],
                         "stderr": str(verified.get("message", ""))})

    manual = [_display_for(policy, attempt) for attempt in all_attempts]
    return {"schema_version": 2, "status": "manual_install_required",
            "failures": failures,
            "manual_instructions": manual,
            "message": ("Every automatic installation tier failed. Run one of the "
                        "manual commands yourself, then re-run --check.")}


def uninstall_cli(policy_path: Path) -> dict[str, Any]:
    policy = load_policy(policy_path)
    removed_manifest = clear_manifest(policy)
    link_removed = False
    if os.name == "posix":
        link = Path("~/.local/bin").expanduser() / str(policy["executable"])
        if link.is_symlink():
            try:
                link.unlink()
                link_removed = True
            except OSError:
                pass
    return {"schema_version": 2, "status": "uninstalled",
            "manifest_removed": removed_manifest,
            "link_removed": link_removed,
            "message": ("Removed local resolution records. Tools installed through "
                        "uv or pipx remain; remove them with their own commands.")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--install", action="store_true")
    group.add_argument("--uninstall", action="store_true")
    parser.add_argument(
        "--manager",
        choices=("auto", "uv", "pipx", "venv", "uv-pypi", "uv-git",
                 "pipx-pypi", "pipx-git"),
        default="auto",
    )
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    args = parser.parse_args(argv)
    try:
        if args.check:
            result = check_cli(args.policy)
        elif args.uninstall:
            result = uninstall_cli(args.policy)
        else:
            result = install_cli(args.policy, args.manager)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"schema_version": 2, "status": "invalid_policy", "error": str(exc),
                  "message": "The bootstrap policy file itself is invalid."}
    print(json.dumps(result, sort_keys=True))
    return EXIT_CODES.get(str(result["status"]), 24)


if __name__ == "__main__":
    raise SystemExit(main())
