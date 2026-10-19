from pathlib import Path

FORBIDDEN_PATHS = {".upgrade", ".release-v090"}
FORBIDDEN_WORKFLOW_TOKENS = ("base64 --decode", "git push origin HEAD:", "payload.part")


def test_release_tree_contains_no_hidden_source_or_self_replacement():
    root = Path(__file__).resolve().parents[1]
    assert not any((root / path).exists() for path in FORBIDDEN_PATHS)
    workflows = "\n".join(path.read_text(encoding="utf-8") for path in (root / ".github" / "workflows").glob("*.yml"))
    for token in FORBIDDEN_WORKFLOW_TOKENS:
        assert token not in workflows
