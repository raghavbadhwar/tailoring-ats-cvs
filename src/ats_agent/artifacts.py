"""Candidate-scoped input artifact registry."""
from __future__ import annotations

import mimetypes
from pathlib import Path

from .hashing import sha256_file
from .models import ArtifactFingerprint, ArtifactKind


class ArtifactIdentityError(ValueError):
    pass


def register_artifact(path: Path, kind: ArtifactKind, candidate_id: str | None = None) -> ArtifactFingerprint:
    if kind in {"resume", "candidate_evidence"} and not candidate_id:
        raise ArtifactIdentityError(f"candidate_id is required for {kind}")
    if kind in {"job_description", "company_context"}:
        candidate_id = None
    absolute = path.expanduser().resolve()
    mime = mimetypes.guess_type(absolute.name)[0] or "application/octet-stream"
    return ArtifactFingerprint(
        artifact_id=f"{kind}:{sha256_file(absolute)[:16]}", candidate_id=candidate_id, kind=kind,
        path=str(absolute), mime_type=mime, sha256=sha256_file(absolute),
    )


def verify_artifacts(records: list[dict]) -> None:
    for record in records:
        path = Path(str(record["path"]))
        actual = sha256_file(path)
        if actual != record["sha256"]:
            raise ValueError(f"stale artifact: {record['kind']}")
