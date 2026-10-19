"""Canonical hashes used to bind proposals, approvals, and source artifacts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compute_proposal_digest(payload: Mapping[str, Any]) -> str:
    clean = dict(payload)
    clean.pop("proposal_digest", None)
    return hashlib.sha256(canonical_json(clean)).hexdigest()
