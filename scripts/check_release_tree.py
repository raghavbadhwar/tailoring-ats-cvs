"""Fail closed when the repository hides source or self-replaces its release tree."""
from __future__ import annotations

from pathlib import Path


FORBIDDEN_PATHS = (".upgrade", ".release-v090")
FORBIDDEN_WORKFLOW_TOKENS = (
    "base64 --decode",
    "payload.part",
    "git push origin HEAD:",
)


def check_release_tree(root: Path) -> list[str]:
    """Return human-readable release-integrity violations for ``root``."""

    violations: list[str] = []
    for relative in FORBIDDEN_PATHS:
        if (root / relative).exists():
            violations.append(f"forbidden hidden release path exists: {relative}")

    workflows = root / ".github" / "workflows"
    for path in sorted(workflows.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_WORKFLOW_TOKENS:
            if token in text:
                violations.append(
                    f"self-replacing release token {token!r} found in {path.relative_to(root)}"
                )
    return violations


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    violations = check_release_tree(root)
    if violations:
        for violation in violations:
            print(f"release tree integrity failed: {violation}")
        return 1
    print("release tree integrity passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
