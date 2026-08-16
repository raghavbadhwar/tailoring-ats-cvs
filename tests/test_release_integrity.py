from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PATHS = (".upgrade", ".release-v090")
FORBIDDEN_WORKFLOW_TOKENS = (
    "base64 --decode",
    "payload.part",
    "git push origin HEAD:",
)


def _workflow_text() -> str:
    workflows = ROOT / ".github" / "workflows"
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(workflows.glob("*.yml"))
    )


def test_release_tree_contains_no_hidden_source_or_self_replacement() -> None:
    assert not any((ROOT / path).exists() for path in FORBIDDEN_PATHS)
    workflow_text = _workflow_text()
    for token in FORBIDDEN_WORKFLOW_TOKENS:
        assert token not in workflow_text


def test_ci_uses_current_node24_actions() -> None:
    workflow_text = _workflow_text()
    assert "actions/checkout@v7" in workflow_text
    assert "actions/setup-python@v7" in workflow_text
    assert "actions/checkout@v4" not in workflow_text
    assert "actions/setup-python@v5" not in workflow_text
