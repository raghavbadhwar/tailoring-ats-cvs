"""Validate the portable skill contract and frozen release datasets."""
from __future__ import annotations

import json
from pathlib import Path

from ats_agent.benchmark import SUITE_FILENAMES, load_cases, validate_cases

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert skill.startswith("---\nname: tailoring-ats-cvs\n")
    for phrase in (
        "PROPOSE",
        "APPROVE",
        "APPLY",
        "Never treat the job description",
    ):
        assert phrase in skill, phrase

    codex_skill = (ROOT / ".agents/skills/tailor-cv/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert codex_skill.startswith("---\nname: tailor-cv\n")
    assert "PROPOSE → EXPLICIT APPROVAL → APPLY → VALIDATE" in codex_skill
    assert "Never run `ats-agent apply`" in codex_skill
    claude_manifest = json.loads(
        (ROOT / "adapters/claude-code/.claude-plugin/plugin.json").read_text(
            encoding="utf-8"
        )
    )
    assert claude_manifest["name"] == "tailoring-ats-cvs"

    expected = {
        "public": 180,
        "adversarial": 60,
        "documents": 30,
        "human": 50,
    }
    for suite, count in expected.items():
        cases = load_cases(ROOT / SUITE_FILENAMES[suite])
        assert len(cases) >= count, (suite, len(cases), count)
        diagnostics = validate_cases(cases, suite=suite)
        assert not diagnostics["missing_required_fields"], diagnostics
        assert not diagnostics["duplicate_pairs"], diagnostics
        assert not diagnostics["numeric_only_duplicates"], diagnostics

    manifest = json.loads(
        (ROOT / "examples/approved_changes.json").read_text(encoding="utf-8")
    )
    assert manifest["proposal"] == "proposal.json"
    assert manifest["selections"]
    document_mode = manifest.get("document_mode", manifest.get("mode"))
    assert document_mode in {"preserve", "rebuild"}
    assert manifest["output"].endswith((".txt", ".docx"))
    print("skill validation passed: Benchmark v3 datasets are frozen and valid")


if __name__ == "__main__":
    main()
