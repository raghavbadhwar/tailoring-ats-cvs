"""Measure requirement-extraction coverage over the frozen real-JD corpus.

Produces ``benchmarks/real-jd/coverage-report.json`` with:

- expected requirement-like lines (heuristic oracle inside requirement
  sections of each posting),
- extracted requirement counts from the engine,
- per-JD and aggregate miss rates,
- the ESCO adoption decision per the reviewed threshold (>15% aggregate gap
  warrants ontology enrichment; otherwise the hand-built alias table stays).

This is the evidence gate the multi-agent review attached to Phase 5.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ats_agent.requirements import TERM_ALIASES, _contains_alias, extract_requirements  # noqa: E402

CORPUS_PATH = ROOT / "benchmarks" / "real-jd" / "corpus.jsonl"
REPORT_PATH = ROOT / "benchmarks" / "real-jd" / "coverage-report.json"

SECTION_HEADING = re.compile(
    r"^(?:#+\s*)?(?:requirements|qualifications|what you.{0,3}ll need|"
    r"what we.{0,3}re looking for|skills? (?:and|&) (?:experience|abilities)|"
    r"basic qualifications|preferred qualifications|must[- ]haves?)\b",
    re.IGNORECASE,
)
ANY_HEADING = re.compile(r"^(?:#+\s*)?[A-Z][^a-z]+$|^(?:#+\s*)\w")
ESCO_THRESHOLD = 0.15


def _expected_lines(description: str) -> list[str]:
    expected: list[str] = []
    in_section = False
    for raw in description.splitlines():
        line = raw.strip()
        if not line:
            continue
        if SECTION_HEADING.search(line):
            in_section = True
            continue
        if in_section:
            if ANY_HEADING.match(line) and not line.startswith(("-", "•", "*")):
                in_section = False
                continue
            cleaned = line.lstrip("-•*0123456789. )\t")
            if len(cleaned.split()) >= 3:
                expected.append(cleaned)
    return expected


def _line_covered(line: str) -> bool:
    body = line.lower()
    for _canonical, aliases in TERM_ALIASES.items():
        for alias in aliases:
            if _contains_alias(body, alias):
                return True
    degree = re.search(
        r"\b(bachelor|master|b\.?\s*(?:tech|com|sc|a)|m\.?\s*(?:ba|com|sc|a)|mba|phd)\b",
        body,
    )
    if degree:
        return True
    years = re.search(r"\b\d+\+?\s*years?\b", body)
    if years:
        return True
    return False


def measure() -> dict[str, object]:
    payload = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    per_jd: list[dict[str, object]] = []
    total_expected = 0
    total_missed = 0
    for entry in payload["entries"]:
        description = str(entry["description"])
        found_rows = extract_requirements(description)
        expected = _expected_lines(description)
        missed = [line for line in expected if not _line_covered(line)]
        total_expected += len(expected)
        total_missed += len(missed)
        per_jd.append({
            "corpus_id": entry["corpus_id"],
            "role": entry["role"],
            "expected_requirement_lines": len(expected),
            "extracted_requirements": len(found_rows),
            "missed_expected_lines": len(missed),
            "miss_rate": round(len(missed) / len(expected), 4) if expected else 0.0,
            "sample_missed": missed[:3],
        })
    aggregate_gap = (
        round(total_missed / total_expected, 4) if total_expected else 0.0
    )
    decision = (
        "adopt_esco_enrichment"
        if aggregate_gap > ESCO_THRESHOLD
        else "keep_hand_alias_table"
    )
    return {
        "schema_version": 1,
        "corpus_entries": len(payload["entries"]),
        "total_expected_lines": total_expected,
        "total_missed_lines": total_missed,
        "aggregate_gap": aggregate_gap,
        "esco_threshold": ESCO_THRESHOLD,
        "esco_decision": decision,
        "per_jd": per_jd,
    }


def main() -> int:
    report = measure()
    REPORT_PATH.write_text(
        json.dumps(report, indent=1, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps({
        "aggregate_gap": report["aggregate_gap"],
        "threshold": report["esco_threshold"],
        "decision": report["esco_decision"],
        "entries": report["corpus_entries"],
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
