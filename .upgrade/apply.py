"""Apply the verified upgrade payload to the current branch.

This temporary bootstrap is removed by its own payload application. It exists only
because the execution environment can write through the GitHub connector but cannot
clone the repository directly.
"""
from __future__ import annotations

import base64
import hashlib
import shutil
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ARCHIVE_SHA256 = "4ae3d95d22826db10b308b1b1d323a8b99e06d9563723b4ef6ba58e1172d4a4b"


def _payload_bytes() -> bytes:
    parts = sorted((ROOT / ".upgrade").glob("payload.part*"))
    if len(parts) != 4:
        raise RuntimeError(f"expected 4 payload parts, found {len(parts)}")
    encoded = "".join(path.read_text(encoding="ascii").strip() for path in parts)
    archive = base64.b64decode(encoded, validate=True)
    digest = hashlib.sha256(archive).hexdigest()
    if digest != EXPECTED_ARCHIVE_SHA256:
        raise RuntimeError(f"payload checksum mismatch: {digest}")
    return archive


def _safe_members(archive: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = archive.getmembers()
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise RuntimeError(f"unsafe archive member: {member.name}")
        if member.issym() or member.islnk():
            raise RuntimeError(f"links are not permitted in payload: {member.name}")
    return members


def main() -> None:
    payload = _payload_bytes()
    with tempfile.TemporaryDirectory(prefix="ats-upgrade-") as directory:
        stage = Path(directory)
        archive_path = stage / "payload.tar.gz"
        archive_path.write_bytes(payload)
        extracted = stage / "extracted"
        extracted.mkdir()
        with tarfile.open(archive_path, "r:gz") as archive:
            archive.extractall(extracted, members=_safe_members(archive))

        for source in sorted(extracted.rglob("*")):
            if not source.is_file():
                continue
            relative = source.relative_to(extracted)
            target = ROOT / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    # The new suite supersedes the earlier draft tests.
    for obsolete in (ROOT / "tests/test_cli.py", ROOT / "tests/test_intelligence.py"):
        obsolete.unlink(missing_ok=True)

    # Remove the temporary delivery mechanism from the final branch.
    shutil.rmtree(ROOT / ".upgrade", ignore_errors=True)
    (ROOT / ".github/workflows/apply-upgrade.yml").unlink(missing_ok=True)
    print("verified upgrade payload applied")


if __name__ == "__main__":
    main()
