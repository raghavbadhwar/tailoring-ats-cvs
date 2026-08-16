"""Build deterministic Codex-skill and Claude-plugin ZIP archives."""
from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def version() -> str:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    if match is None:
        raise ValueError("project version not found")
    return match.group(1)


def write_archive(destination: Path, source: Path, archive_root: str) -> None:
    files = sorted(path for path in source.rglob("*") if path.is_file())
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            info = zipfile.ZipInfo(f"{archive_root}/{path.relative_to(source).as_posix()}", ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="dist", help="directory for ZIP archives")
    args = parser.parse_args()
    output = Path(args.output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    release = version()
    archives = {
        output / f"tailoring-ats-cvs-codex-skill-{release}.zip": (
            ROOT / ".agents/skills/tailor-cv",
            "tailor-cv",
        ),
        output / f"tailoring-ats-cvs-claude-plugin-{release}.zip": (
            ROOT / "adapters/claude-code",
            "tailoring-ats-cvs",
        ),
    }
    for destination, (source, archive_root) in archives.items():
        write_archive(destination, source, archive_root)
        print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
