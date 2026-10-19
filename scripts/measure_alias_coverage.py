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

from ats_agent.boards import html_to_text  # noqa: E402
from ats_agent.requirements import extract_requirements  # noqa: E402

CORPUS_PATH = ROOT / "benchmarks" / "real-jd" / "corpus.jsonl"
REPORT_PATH = ROOT / "benchmarks" / "real-jd" / "coverage-report.json"

SECTION_HEADING = re.compile(
    r"^(?:requirements|qualifications|your qualifications and qualities|required|"
    r"minimum requirements(?: for (?:this|the) role)?|preferred qualifications|"
    r"basic qualifications|what you.{0,3}ll need|what we.{0,3}re looking for|"
    r"what we look for|skills? (?:and|&) (?:experience|abilities)|must[- ]haves?|"
    r"we.{0,3}d love to hear from you if you have|what you bring|who should apply|"
    r"you should apply if|an ideal candidate has)\b",
    re.IGNORECASE,
)
ESCO_THRESHOLD = 0.15


def _mark_paragraph_heading(match: re.Match[str]) -> str:
    heading = html_to_text(match.group("heading")).strip()
    letters = "".join(character for character in heading if character.isalpha())
    if (
        SECTION_HEADING.search(heading)
        or match.group("strong")
        or (letters and letters == letters.upper())
    ):
        return f"\n## {heading}\n"
    return match.group(0)


def _measurement_text(description: str) -> str:
    """Preserve headings and list-item boundaries while stripping corpus HTML."""

    marked = re.sub(
        r"<\s*h[1-6]\b[^>]*>",
        "\n## ",
        description,
        flags=re.IGNORECASE,
    )
    marked = re.sub(
        r"<\s*/\s*h[1-6]\s*>",
        "\n",
        marked,
        flags=re.IGNORECASE,
    )
    marked = re.sub(
        r"<\s*p\b[^>]*>\s*(?P<strong><\s*strong\b[^>]*>)?"
        r"(?P<heading>[^<]{1,120})"
        r"(?:<\s*/\s*strong\s*>)?\s*(?::|&nbsp;)?\s*<\s*/\s*p\s*>",
        _mark_paragraph_heading,
        marked,
        flags=re.IGNORECASE,
    )
    marked = re.sub(r"<\s*li\b[^>]*>", "\n- ", marked, flags=re.IGNORECASE)
    return html_to_text(marked)


def _expected_lines(description: str) -> list[str]:
    expected: list[str] = []
    in_section = False
    for raw in description.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("## "):
            in_section = bool(SECTION_HEADING.search(line[3:].strip()))
            continue
        if in_section:
            cleaned = line.lstrip("-•*0123456789. )\t")
            if len(cleaned.split()) >= 3:
                expected.append(cleaned)
    return expected


def _line_covered(line: str, found_rows: list[dict]) -> bool:
    """Report coverage only when the requirement engine extracted this line."""

    expected = " ".join(re.findall(r"[a-z0-9]+", line.lower()))
    for row in found_rows:
        extracted = " ".join(
            re.findall(r"[a-z0-9]+", str(row.get("text") or "").lower())
        )
        if expected and extracted and (expected in extracted or extracted in expected):
            return True
    return False


def measure() -> dict[str, object]:
    payload = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    per_jd: list[dict[str, object]] = []
    total_expected = 0
    total_missed = 0
    measured_entries = 0
    for entry in payload["entries"]:
        description = _measurement_text(str(entry["description"]))
        found_rows = extract_requirements(description)
        expected = _expected_lines(description)
        missed = [line for line in expected if not _line_covered(line, found_rows)]
        if not expected:
            raise ValueError(
                f"real-JD corpus entry {entry['corpus_id']} has zero expected requirement lines"
            )
        measured_entries += 1
        total_expected += len(expected)
        total_missed += len(missed)
        per_jd.append({
            "corpus_id": entry["corpus_id"],
            "role": entry["role"],
            "expected_requirement_lines": len(expected),
            "extracted_requirements": len(found_rows),
            "missed_expected_lines": len(missed),
            "miss_rate": round(len(missed) / len(expected), 4) if expected else None,
            "sample_missed": missed[:3],
        })
    aggregate_gap = round(total_missed / total_expected, 4)
    decision = (
        "adopt_esco_enrichment"
        if aggregate_gap > ESCO_THRESHOLD
        else "keep_hand_alias_table"
    )
    return {
        "schema_version": 3,
        "label_source": "rule-derived",
        "measurement_status": "heuristic_diagnostic_not_human_validated",
        "interpretation": (
            "Miss rates diagnose parser coverage against section-derived lines; "
            "they are not human-labelled recall estimates."
        ),
        "corpus_entries": len(payload["entries"]),
        "measured_entries": measured_entries,
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
