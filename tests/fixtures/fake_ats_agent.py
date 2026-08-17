#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _log(command: str) -> None:
    if path := os.environ.get("FAKE_ATS_AGENT_LOG"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with Path(path).open("a", encoding="utf-8") as handle:
            handle.write(command + "\n")


def main() -> int:
    arguments = sys.argv[1:]
    if arguments == ["doctor", "--strict"]:
        print(json.dumps({"schema_version": 1, "status": "ready", "package": {"name": "tailoring-ats-cvs", "version": "1.0.0b3"}, "strict_check": {"status": "passed"}}))
        return 0
    if not arguments:
        return 2
    command = arguments[0]
    _log(command)
    if command == "prepare":
        output = Path(arguments[arguments.index("--out") + 1])
        output.mkdir(parents=True, exist_ok=True)
        (output / "proposal.json").write_text(json.dumps({"schema_version": 5, "status": "draft", "proposal_id": "P1", "proposal_digest": "a" * 64, "hard_gates": [], "requirement_evidence": [], "changes": [{"id": "C1", "supported": True, "target_section": "projects", "reason": "test", "evidence_ids": [], "variants": [{"id": "balanced", "text": "Test"}]}]}), encoding="utf-8")
        (output / "review.html").write_text("review", encoding="utf-8")
    elif command == "approve":
        if "--select" not in arguments:
            return 4
        Path(arguments[arguments.index("--output") + 1]).write_text("{}", encoding="utf-8")
    elif command == "apply":
        if not Path(arguments[1]).is_file():
            return 4
    elif command == "validate":
        return 0
    print(json.dumps({"status": "ok", "arguments": arguments}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
