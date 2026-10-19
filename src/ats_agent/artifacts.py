"""Candidate-scoped registration and fingerprinting of workflow inputs."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .hashing import sha256_path, stable_id
from .models import ArtifactFingerprint, ArtifactKind

MIME_TYPES = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".html": "text/html",
    ".htm": "text/html",
    ".rtf": "application/rtf",
    ".docx": (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    ),
    ".pdf": "application/pdf",
}


def fingerprint_artifact(
    path: Path,
    *,
    kind: ArtifactKind,
    candidate_id: str | None,
) -> ArtifactFingerprint:
    """Fingerprint one exact input file."""

    resolved = path.expanduser().resolve()
    digest = sha256_path(resolved)
    identity = {
        "kind": kind,
        "candidate_id": candidate_id,
        "path": str(resolved),
        "sha256": digest,
    }
    return ArtifactFingerprint(
        artifact_id=stable_id("A", identity),
        candidate_id=candidate_id,
        kind=kind,
        path=str(resolved),
        mime_type=MIME_TYPES.get(
            resolved.suffix.lower(),
            "application/octet-stream",
        ),
        sha256=digest,
    )


def register_artifacts(
    *,
    resume: Path,
    job_description: Path,
    evidence_paths: Iterable[Path],
    company_context: Path | None,
    candidate_id: str,
) -> tuple[ArtifactFingerprint, ...]:
    """Register every input with an explicit trust role and content hash."""

    if not candidate_id.strip():
        raise ValueError("candidate_id is required")
    artifacts: list[ArtifactFingerprint] = [
        fingerprint_artifact(
            resume,
            kind="resume",
            candidate_id=candidate_id,
        ),
        fingerprint_artifact(
            job_description,
            kind="job_description",
            candidate_id=None,
        ),
    ]
    artifacts.extend(
        fingerprint_artifact(
            path,
            kind="candidate_evidence",
            candidate_id=candidate_id,
        )
        for path in evidence_paths
    )
    if company_context is not None:
        artifacts.append(
            fingerprint_artifact(
                company_context,
                kind="company_context",
                candidate_id=None,
            )
        )
    return tuple(artifacts)
