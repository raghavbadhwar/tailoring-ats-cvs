"""Produce a compact review summary without candidate artifact paths."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def summarize(proposal: dict[str, Any]) -> dict[str, Any]:
    if proposal.get("schema_version") != 5:
        raise ValueError("proposal schema must be 5")
    changes = proposal.get("changes", [])
    supported = [change for change in changes if change.get("supported")]
    gaps = [change for change in changes if not change.get("supported")]
    requirements = [{key: item.get(key) for key in ("requirement_id", "normalized_terms", "importance", "coverage", "evidence_ids")} for item in proposal.get("requirement_evidence", [])]
    safe_changes = [{key: item.get(key) for key in ("id", "kind", "target_section", "reason", "evidence_ids", "variants")} for item in supported]
    safe_gaps = [{key: item.get(key) for key in ("id", "kind", "requirement_id", "reason", "evidence_ids")} for item in gaps]
    return {"schema_version": 1, "status": proposal.get("status"), "proposal_id": proposal.get("proposal_id"), "proposal_digest": proposal.get("proposal_digest"), "approval_boundary": "explicit_selection_required", "hard_gates": proposal.get("hard_gates", []), "requirements": requirements, "supported_changes": safe_changes, "supported_change_ids": [item.get("id") for item in supported], "unsupported_gaps": safe_gaps, "unsupported_gap_ids": [item.get("id") for item in gaps]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("proposal", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = summarize(json.loads(args.proposal.read_text(encoding="utf-8")))
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
