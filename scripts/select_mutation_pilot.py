#!/usr/bin/env python3
"""Select one deterministic authority-boundary mutation per target module."""
from __future__ import annotations

import argparse
from pathlib import Path

from cosmic_ray.work_db import WorkDB, use_db

TARGETS = {
    "src/ats_agent/workflow.py": "_validate_research_freshness",
    "src/ats_agent/evidence.py": "_proof_text",
    "src/ats_agent/documents.py": "patch_document",
    "src/ats_agent/validation.py": "validate_change",
}


def _key(item: object) -> tuple[str, str, int]:
    mutation = item.mutations[0]  # type: ignore[attr-defined]
    return (
        mutation.definition_name or "",
        mutation.operator_name,
        mutation.occurrence,
    )


def select(source: Path, destination: Path) -> int:
    with use_db(source, mode=WorkDB.Mode.open) as database:
        items = database.work_items
    selected = []
    for module, definition in TARGETS.items():
        candidates = sorted(
            (
                item
                for item in items
                if Path(item.mutations[0].module_path).as_posix() == module
                and item.mutations[0].definition_name == definition
            ),
            key=_key,
        )
        if not candidates:
            raise ValueError(f"mutation-pilot: no mutation found for {module}:{definition}")
        selected.append(candidates[0])
    with use_db(destination) as database:
        database.clear()
        database.add_work_items(selected)
    return len(selected)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args(argv)
    count = select(args.source, args.destination)
    print(f"mutation-pilot: selected {count} deterministic mutations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
