"""Validate thin adapters without invoking an installer or candidate data."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def validate_repository(root: Path) -> dict[str, object]:
    errors: list[str] = []
    skill_path = root / ".agents/skills/tailor-cv/SKILL.md"
    manifest_path = root / ".claude-plugin/plugin.json"
    required = [skill_path, manifest_path, root / "bin/ats-cv", root / "bin/ats-cv.cmd", root / ".agents/skills/tailor-cv/assets/bootstrap-policy.json"]
    for path in required:
        if not path.is_file():
            errors.append(f"missing: {path.relative_to(root)}")
    if errors:
        return {"errors": errors}
    skill = skill_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    scripts = list((root / ".agents/skills/tailor-cv/scripts").glob("*.py"))
    if not skill.startswith("---\nname: tailor-cv\n") or len(skill.splitlines()) > 500:
        errors.append("invalid skill frontmatter or length")
    if "explicit approval" not in skill.lower() or "automatically approve" in skill.lower():
        errors.append("missing explicit change approval boundary")
    if "--install" not in skill or "ask for permission" not in skill:
        errors.append("missing explicit installation approval")
    if any("shell=True" in script.read_text(encoding="utf-8") for script in scripts):
        errors.append("shell=True in adapter script")
    if manifest.get("version") != "1.0.0-beta.3" or manifest.get("skills") != ["./.agents/skills/tailor-cv"]:
        errors.append("plugin manifest mismatch")
    if os.name != "nt" and not (root / "bin/ats-cv").stat().st_mode & 0o111:
        errors.append("POSIX launcher is not executable")
    policy = json.loads(required[-1].read_text(encoding="utf-8"))
    if policy.get("requires_explicit_approval") is not True or "==1.0.0b3" not in str(policy.get("preferred_spec")):
        errors.append("unsafe bootstrap policy")
    return {"errors": errors, "skill_name": "tailor-cv", "plugin_name": "tailoring-ats-cvs", "explicit_install_approval": "--install" in skill and "permission" in skill, "explicit_change_approval": "explicit approval" in skill.lower()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    diagnostics = validate_repository(args.root.resolve())
    print(json.dumps(diagnostics, indent=2))
    return 0 if not diagnostics["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
