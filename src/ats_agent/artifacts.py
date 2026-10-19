"""Candidate-scoped registration and safe persistence of workflow artifacts."""
from __future__ import annotations

import os
import shutil
import tempfile
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


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Replace one artifact without following a pre-existing final symlink.

    Review bundles, receipts, and recovery records live in user-selected run
    directories.  A predictable ``Path.write_text`` target can otherwise
    follow a stale or hostile symlink and overwrite a candidate document (or
    another unrelated file).  Writing a unique sibling first and atomically
    replacing the final directory entry preserves crash safety and never
    writes through that entry.
    """

    expanded = path.expanduser()
    parent = expanded.parent.resolve()
    if not expanded.name:
        raise ValueError("artifact output must name a file")
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / expanded.name
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.tmp-",
        dir=parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding=encoding) as handle:
            handle.write(text)
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def atomic_copyfile(source: Path, destination: Path) -> None:
    """Copy an artifact without following a pre-existing destination symlink."""

    expanded = destination.expanduser()
    parent = expanded.parent.resolve()
    if not expanded.name:
        raise ValueError("artifact output must name a file")
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / expanded.name
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.tmp-",
        dir=parent,
    )
    temporary = Path(temporary_name)
    try:
        with source.open("rb") as input_handle, os.fdopen(descriptor, "wb") as output_handle:
            shutil.copyfileobj(input_handle, output_handle)
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def assert_output_paths_safe(
    outputs: Iterable[Path],
    protected_inputs: Iterable[Path],
) -> None:
    """Reject outputs that resolve to a candidate or review input artifact."""

    protected = {
        path.expanduser().resolve()
        for path in protected_inputs
    }
    for output in outputs:
        if output.expanduser().resolve() in protected:
            raise ValueError("output must not overwrite an input artifact")


def assert_run_directory_is_separate(
    run_directory: Path,
    protected_inputs: Iterable[Path],
) -> None:
    """Keep generated run artifacts out of the directory holding inputs."""

    root = run_directory.expanduser().resolve()
    for path in protected_inputs:
        try:
            path.expanduser().resolve().relative_to(root)
        except ValueError:
            continue
        raise ValueError(
            "run directory must not contain an input artifact; choose a separate run directory"
        )


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
