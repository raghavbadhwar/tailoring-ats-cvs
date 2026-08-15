from __future__ import annotations

import json
from pathlib import Path

from .evidence import EvidenceSource, build_evidence_ledger
from .requirements import extract_requirements, map_requirements


def _normalized(values: list[object]) -> set[str]:
    return {
        str(value).strip().lower()
        for value in values
        if isinstance(value, str) and value.strip()
    }


def _terms_for(mappings: list[dict], coverage: set[str]) -> set[str]:
    return {
        term.lower()
        for mapping in mappings
        if mapping["coverage"] in coverage
        for term in mapping.get("normalized_terms", [])
    }


def _case_result(case: dict) -> dict:
    candidate_id = f"benchmark:{case['id']}"
    ledger = build_evidence_ledger(
        candidate_id,
        [
            EvidenceSource(
                source="benchmark-resume",
                source_file=f"{case['id']}.resume.txt",
                text=case["resume"],
            )
        ],
    )
    requirements = extract_requirements(case["job_description"])
    mappings = map_requirements(requirements, ledger)

    predicted_supported = _terms_for(mappings, {"direct", "transferable"})
    predicted_unsupported = _terms_for(mappings, {"unsupported"})
    requirement_terms = {
        term.lower()
        for requirement in requirements
        for term in requirement.get("normalized_terms", [])
    }
    expected_supported = requirement_terms & _normalized(case.get("evidence", []))
    expected_unsupported = _normalized(case.get("expected_unsupported_claims", []))

    supported_hits = len(expected_supported & predicted_supported)
    unsupported_hits = len(expected_unsupported & predicted_unsupported)
    supported_mappings = [
        mapping
        for mapping in mappings
        if mapping["coverage"] in {"direct", "transferable"}
    ]
    provenance_hits = sum(bool(mapping.get("evidence_ids")) for mapping in supported_mappings)

    return {
        "id": case["id"],
        "requirements": len(requirements),
        "predicted_supported_terms": sorted(predicted_supported),
        "predicted_unsupported_terms": sorted(predicted_unsupported),
        "expected_supported_terms": sorted(expected_supported),
        "expected_unsupported_terms": sorted(expected_unsupported),
        "supported_hits": supported_hits,
        "supported_total": len(expected_supported),
        "unsupported_hits": unsupported_hits,
        "unsupported_total": len(expected_unsupported),
        "provenance_hits": provenance_hits,
        "provenance_total": len(supported_mappings),
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def run(dataset: Path) -> dict:
    cases = [
        json.loads(line)
        for line in dataset.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    results = [_case_result(case) for case in cases]

    supported_hits = sum(item["supported_hits"] for item in results)
    supported_total = sum(item["supported_total"] for item in results)
    unsupported_hits = sum(item["unsupported_hits"] for item in results)
    unsupported_total = sum(item["unsupported_total"] for item in results)
    provenance_hits = sum(item["provenance_hits"] for item in results)
    provenance_total = sum(item["provenance_total"] for item in results)

    return {
        "case_count": len(results),
        "cases": results,
        "supported_requirement_recall": _ratio(supported_hits, supported_total),
        "unsupported_requirement_detection_rate": _ratio(
            unsupported_hits,
            unsupported_total,
        ),
        "evidence_provenance_coverage": _ratio(provenance_hits, provenance_total),
        "parser_risk_delta": None,
        "human_rewrite_preference": None,
        "measurement_status": {
            "parser_risk_delta": "not_implemented",
            "human_rewrite_preference": "requires human-labelled evaluation",
        },
    }
