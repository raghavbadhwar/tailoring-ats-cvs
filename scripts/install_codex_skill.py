"""Install the portable tailor-cv skill into a Codex skills directory.

Usage:
    python scripts/install_codex_skill.py [--check | --uninstall | --force]

Default action installs or upgrades ``${CODEX_HOME:-~/.codex}/skills/tailor-cv``
from this repository. The installer is idempotent, refuses downgrades below
the repository skill version unless ``--force`` is given, and never touches
anything outside the destination directory.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

REPO_SKILL = Path(__file__).resolve().parents[1] / ".agents" / "skills" / "tailor-cv"
VERSION_PATTERN = re.compile(
    r'^\s*version:\s*"([^"]+)"', re.MULTILINE
)


def codex_skills_root() -> Path:
    home = os.environ.get("CODEX_HOME") or str(Path.home() / ".codex")
    return Path(home).expanduser() / "skills"


def destination() -> Path:
    return codex_skills_root() / "tailor-cv"


def _version_key(raw: str) -> tuple[tuple[int, ...], int, int]:
    normalized = raw.strip().lower()
    match = re.fullmatch(
        r"(\d+(?:\.\d+)*)(?:[.\-]?(a|b|rc|alpha|beta)(?:[.\-]?(\d+)))?",
        normalized,
    )
    if match is None:
        raise ValueError(f"unsupported version string: {raw!r}")
    release = tuple(int(part) for part in match.group(1).split("."))
    stage = {"a": 0, "alpha": 0, "b": 1, "beta": 1, "rc": 2, None: 3}[
        match.group(2)
    ]
    return release, stage, int(match.group(3) or 0)


def _skill_version(skill_dir: Path) -> str:
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    match = VERSION_PATTERN.search(text)
    if match is None:
        raise ValueError(f"no version metadata in {skill_dir / 'SKILL.md'}")
    return match.group(1)


def check() -> dict[str, object]:
    source_version = _skill_version(REPO_SKILL)
    dest = destination()
    payload: dict[str, object] = {
        "schema_version": 1,
        "source": str(REPO_SKILL),
        "destination": str(dest),
        "source_version": source_version,
    }
    if not dest.exists():
        payload.update(status="not_installed",
                       message=f"Not installed at {dest}.")
        return payload
    installed_version = _skill_version(dest)
    payload["installed_version"] = installed_version
    relation = (
        "up_to_date"
        if _version_key(installed_version) >= _version_key(source_version)
        else "upgrade_available"
    )
    payload.update(status=relation,
                   message=f"{installed_version} installed at {dest}.")
    return payload


def install(force: bool) -> dict[str, object]:
    source_version = _skill_version(REPO_SKILL)
    dest = destination()
    if dest.exists():
        installed_version = _skill_version(dest)
        if (_version_key(installed_version) > _version_key(source_version)
                and not force):
            return {
                "schema_version": 1,
                "status": "downgrade_refused",
                "installed_version": installed_version,
                "source_version": source_version,
                "message": (f"{dest} already has newer skill version "
                            f"{installed_version}; pass --force to downgrade."),
            }
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copytree(REPO_SKILL, dest, dirs_exist_ok=True)
    manifest = {
        "schema_version": 1,
        "skill": "tailor-cv",
        "version": source_version,
        "source_repository": "https://github.com/raghavbadhwar/tailoring-ats-cvs",
    }
    (dest / "INSTALL_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return {
        "schema_version": 1,
        "status": "installed",
        "destination": str(dest),
        "version": source_version,
        "message": f"Installed tailor-cv {source_version} into {dest}.",
        "next_prompt": (
            "Use the tailor-cv skill.\nCV: ./my-cv.docx\n"
            "Job description: ./job-description.md\nEvidence: ./evidence.md\n"
            "Prepare the proposal and summarize the evidence mapping. Do not "
            "approve or apply changes until I send an explicit list of change "
            "IDs and variants."
        ),
    }


def uninstall() -> dict[str, object]:
    dest = destination()
    if not dest.exists():
        return {"schema_version": 1, "status": "not_installed",
                "message": f"Nothing to remove at {dest}."}
    shutil.rmtree(dest)
    return {"schema_version": 1, "status": "uninstalled",
            "message": f"Removed {dest}."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true")
    group.add_argument("--uninstall", action="store_true")
    group.add_argument("--force", action="store_true",
                       help="allow replacing a newer installed version")
    args = parser.parse_args(argv)
    try:
        result = (
            check() if args.check
            else uninstall() if args.uninstall
            else install(args.force)
        )
    except (OSError, ValueError) as exc:
        result = {"schema_version": 1, "status": "error",
                  "message": str(exc)}
    print(json.dumps(result, sort_keys=True))
    statuses = {"installed": 0, "up_to_date": 0, "uninstalled": 0,
                "not_installed": 0, "upgrade_available": 1,
                "downgrade_refused": 2, "error": 3}
    return statuses.get(str(result.get("status")), 3)


if __name__ == "__main__":
    sys.exit(main())
