"""Single source of release versioning derived from pyproject.toml.

Every artifact that names the release (bundle filenames, plugin manifests,
adapter validators) derives from here so a version bump touches exactly one
file. ``scripts/release_check.py`` intentionally keeps its literal pin as
tamper-evidence and is excluded from this indirection.
"""
from __future__ import annotations

import re
from pathlib import Path


def package_version(root: Path) -> str:
    match = re.search(
        r'^version\s*=\s*"([^"]+)"',
        (root / "pyproject.toml").read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if match is None:
        raise ValueError("project version not found in pyproject.toml")
    return match.group(1)


def display_version(version: str) -> str:
    """Render PEP 440 prerelease in user-facing form: ``1.0.0b4`` → ``1.0.0-beta.4``."""
    match = re.fullmatch(r"(\d+(?:\.\d+)*)(a|b|rc)(\d+)", version)
    if match is None:
        return version
    return f"{match.group(1)}-{ {'a': 'alpha', 'b': 'beta', 'rc': 'rc'}[match.group(2)] }.{match.group(3)}"
