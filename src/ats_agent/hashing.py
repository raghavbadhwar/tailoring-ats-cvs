"""Canonical content hashing for artifacts, proposals, and approvals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


def sha256_path(path: Path) -> str:
    """Return the SHA-256 digest of the exact file bytes."""

    return hashlib.sha256(path.expanduser().resolve().read_bytes()).hexdigest()


def canonical_json(value: Any) -> bytes:
    """Serialize JSON-compatible data deterministically."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def stable_id(prefix: str, value: Any, *, length: int = 20) -> str:
    """Create a stable upper-case identifier from canonical JSON."""

    digest = hashlib.sha256(canonical_json(value)).hexdigest()[:length].upper()
    return prefix + digest


def compute_proposal_digest(payload: Mapping[str, Any]) -> str:
    """Hash the full proposal except for its self-referential digest field."""

    clean = dict(payload)
    clean.pop("proposal_digest", None)
    return hashlib.sha256(canonical_json(clean)).hexdigest()


def verify_proposal_digest(proposal: Mapping[str, Any]) -> str:
    """Return the verified digest or raise when proposal content was edited."""

    stored = str(proposal.get("proposal_digest") or "").lower()
    actual = compute_proposal_digest(proposal)
    if not stored:
        raise ValueError("proposal digest is missing")
    if stored != actual:
        raise ValueError("proposal digest does not match proposal content")
    return stored
