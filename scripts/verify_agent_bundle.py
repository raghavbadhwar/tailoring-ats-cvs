"""Fail closed on malformed adapter archives and checksum mismatches."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


def verify(output: Path) -> None:
    archives = [output / "tailor-cv-agent-skill-v1.0.0-beta.3.zip", output / "tailoring-ats-cvs-claude-plugin-v1.0.0-beta.3.zip"]
    expected = {name: digest for digest, name in (line.split("  ", 1) for line in (output / "SHA256SUMS").read_text(encoding="utf-8").splitlines())}
    for path in archives:
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected.get(path.name):
            raise ValueError(f"checksum mismatch: {path.name}")
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if any(name.startswith("/") or ".." in Path(name).parts for name in names):
                raise ValueError("unsafe archive path")
            if any(item.file_size > 2_000_000 or (item.external_attr >> 16) & 0o170000 == 0o120000 for item in archive.infolist()):
                raise ValueError("unsafe archive member")
            if sum(item.file_size for item in archive.infolist()) > (5_000_000 if "skill" in path.name else 10_000_000):
                raise ValueError("archive too large")
    with zipfile.ZipFile(archives[0]) as archive:
        if "tailor-cv/SKILL.md" not in archive.namelist():
            raise ValueError("skill missing")
    with zipfile.ZipFile(archives[1]) as archive:
        manifest = json.loads(archive.read("tailoring-ats-cvs/.claude-plugin/plugin.json"))
        if manifest.get("skills") != ["./.agents/skills/tailor-cv"]:
            raise ValueError("plugin skill path mismatch")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    verify(args.output)
    print("agent bundles verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
