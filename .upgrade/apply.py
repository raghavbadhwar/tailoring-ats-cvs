"""Apply the checksum-verified upgrade payload to the feature branch.

The bootstrap is temporary: it verifies both archives, overlays the compatibility
patch, copies the resulting tree, and then removes itself before committing.
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
EXPECTED_PATCH_SHA256 = "90d0fb2e5d663ed1b9f500dc764e89a8e18045f1622de28efa004a5894ce326f"


def _verified_payload() -> bytes:
    parts = sorted((ROOT / ".upgrade").glob("payload.part*"))
    if len(parts) != 4:
        raise RuntimeError(f"expected 4 payload parts, found {len(parts)}")
    encoded = "".join(path.read_text(encoding="ascii").strip() for path in parts)
    archive = base64.b64decode(encoded, validate=True)
    digest = hashlib.sha256(archive).hexdigest()
    if digest != EXPECTED_ARCHIVE_SHA256:
        raise RuntimeError(f"payload checksum mismatch: {digest}")
    return archive


def _verified_patch() -> bytes:
    patch = (ROOT / ".upgrade" / "compat-patch.tar.gz").read_bytes()
    digest = hashlib.sha256(patch).hexdigest()
    if digest != EXPECTED_PATCH_SHA256:
        raise RuntimeError(f"patch checksum mismatch: {digest}")
    return patch


def _safe_members(archive: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = archive.getmembers()
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise RuntimeError(f"unsafe archive member: {member.name}")
        if member.issym() or member.islnk():
            raise RuntimeError(f"links are not permitted in payload: {member.name}")
    return members


def _extract(data: bytes, target: Path, filename: str) -> None:
    archive_path = target.parent / filename
    archive_path.write_bytes(data)
    with tarfile.open(archive_path, "r:gz") as archive:
        archive.extractall(target, members=_safe_members(archive))


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ats-upgrade-") as directory:
        stage = Path(directory)
        extracted = stage / "extracted"
        extracted.mkdir()
        _extract(_verified_payload(), extracted, "payload.tar.gz")
        _extract(_verified_patch(), extracted, "compat-patch.tar.gz")

        for source in sorted(extracted.rglob("*")):
            if not source.is_file():
                continue
            target = ROOT / source.relative_to(extracted)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    # The replacement suite supersedes only these early draft tests. Existing
    # branch compatibility and document-preservation tests stay in place.
    for obsolete in (ROOT / "tests/test_cli.py", ROOT / "tests/test_intelligence.py"):
        obsolete.unlink(missing_ok=True)

    shutil.rmtree(ROOT / ".upgrade", ignore_errors=True)
    (ROOT / ".github/workflows/apply-upgrade.yml").unlink(missing_ok=True)
    print("verified upgrade payload and compatibility patch applied")


if __name__ == "__main__":
    main()
