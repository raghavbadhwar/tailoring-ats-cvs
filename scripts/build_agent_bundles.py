"""Build deterministic portable skill and Claude Code plugin archives."""
from __future__ import annotations

import argparse
import hashlib
import json
import tomllib
import zipfile
from pathlib import Path

FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def _version(root: Path) -> str:
    return tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def _write(archive: zipfile.ZipFile, name: str, source: Path, executable: bool = False) -> None:
    info = zipfile.ZipInfo(name, FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = ((0o755 if executable else 0o644) & 0xFFFF) << 16
    archive.writestr(info, source.read_bytes())


def _archive(destination: Path, root: Path, files: list[Path], prefix: str) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in sorted(
            path
            for path in files
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        ):
            relative = source.relative_to(root).as_posix()
            _write(archive, f"{prefix}/{relative}" if prefix else relative, source, relative == "bin/ats-cv")


def build_bundles(root: Path, output: Path) -> list[Path]:
    version = _version(root)
    if version != "1.0.0b2":
        raise ValueError("agent adapter release expects 1.0.0b2")
    manifest = json.loads((root / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    if manifest.get("version") != "1.0.0-beta.2":
        raise ValueError("plugin version does not match package version")
    output.mkdir(parents=True, exist_ok=True)
    skill = output / "tailor-cv-agent-skill-v1.0.0-beta.2.zip"
    plugin = output / "tailoring-ats-cvs-claude-plugin-v1.0.0-beta.2.zip"
    _archive(skill, root / ".agents/skills", list((root / ".agents/skills/tailor-cv").rglob("*")), "")
    files = [path for path in (root / ".agents").rglob("*") if path.is_file()]
    files += [root / ".claude-plugin/plugin.json", root / "bin/ats-cv", root / "bin/ats-cv.cmd"]
    _archive(plugin, root, files, "tailoring-ats-cvs")
    sums = output / "SHA256SUMS"
    sums.write_text("".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in (skill, plugin)), encoding="utf-8")
    return [skill, plugin]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="dist/agent-adapters")
    args = parser.parse_args()
    for path in build_bundles(Path(__file__).resolve().parents[1], Path(args.output)):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
