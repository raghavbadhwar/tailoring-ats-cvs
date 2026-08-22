"""Build the frozen real-JD regression corpus from live ATS board feeds.

Fetches genuine internship postings through the public Greenhouse/Lever/Ashby
syndication APIs, freezes them into ``benchmarks/real-jd/corpus.jsonl`` with
per-entry sha256 provenance, and reports collection statistics. Re-running
appends nothing: the corpus is content-frozen once written unless
``--rebuild`` is passed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ats_agent.boards import BoardError, fetch_board_url  # noqa: E402

CORPUS_PATH = ROOT / "benchmarks" / "real-jd" / "corpus.jsonl"

CANDIDATE_BOARDS = [
    "https://boards.greenhouse.io/stripe",
    "https://boards.greenhouse.io/databricks",
    "https://boards.greenhouse.io/figma",
    "https://boards.greenhouse.io/nvidia",
    "https://boards.greenhouse.io/doordash",
    "https://boards.greenhouse.io/robinhood",
    "https://boards.greenhouse.io/scaleai",
    "https://boards.greenhouse.io/flexport",
    "https://jobs.lever.co/ramp",
    "https://jobs.lever.co/plaid",
    "https://jobs.lever.co/brex",
    "https://jobs.lever.co/notion",
    "https://jobs.ashbyhq.com/openai",
    "https://jobs.ashbyhq.com/linear",
    "https://boards.greenhouse.io/affirm",
    "https://boards.greenhouse.io/coinbase",
    "https://boards.greenhouse.io/instacart",
    "https://boards.greenhouse.io/lyft",
    "https://boards.greenhouse.io/samsara",
    "https://boards.greenhouse.io/gusto",
    "https://boards.greenhouse.io/benchling",
    "https://jobs.lever.co/replit",
    "https://jobs.lever.co/substack",
]

INTERN_PATTERN = re.compile(r"\bintern(?:ship)?\b", re.IGNORECASE)
MIN_WORDS = 60


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def collect(min_count: int) -> list[dict[str, object]]:
    collected: list[dict[str, object]] = []
    errors: list[str] = []
    for board_url in CANDIDATE_BOARDS:
        if len(collected) >= min_count:
            break
        try:
            jobs = fetch_board_url(board_url)
        except BoardError as exc:
            errors.append(f"{board_url}: {exc}")
            continue
        for job in jobs:
            role = str(job.get("role") or "")
            description = str(job.get("description") or "")
            if not INTERN_PATTERN.search(role):
                continue
            if len(re.findall(r"[A-Za-z0-9]+", description)) < MIN_WORDS:
                continue
            collected.append({
                "corpus_id": f"real-{job['provider']}-{len(collected) + 1:02d}",
                "company": job["company"],
                "role": role,
                "job_url": job["job_url"],
                "description": description,
                "provenance": {
                    "source": "ats_syndication_api",
                    "provider": job["provider"],
                    "fetched_at": job["fetched_at"],
                    "sha256": _sha256_text(description),
                },
            })
            if len(collected) >= min_count:
                break
    return collected, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-count", type=int, default=12)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()

    if CORPUS_PATH.exists() and not args.rebuild:
        print(json.dumps({"status": "frozen", "path": str(CORPUS_PATH)}))
        return 0

    entries, errors = collect(args.min_count)
    CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "entry_count": len(entries),
        "entries": entries,
    }
    CORPUS_PATH.write_text(
        json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps({
        "status": "built",
        "entries": len(entries),
        "board_errors": len(errors),
        "path": str(CORPUS_PATH),
    }))
    for error in errors:
        print(f"note: {error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
