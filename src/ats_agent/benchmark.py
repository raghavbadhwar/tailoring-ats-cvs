"""Measured offline benchmark for requirements, provenance, and rewrite safety."""
from __future__ import annotations

import json
from pathlib import Path

from .evidence import EvidenceSource, build_evidence_ledger
from .requirements import evaluate_hard_gates, extract_requirements, map_requirements
from .rewriting import propose_supported_changes
from .validation import validate_change


def _set(values: object) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {str(value).strip().lower() for value in values if str(value).strip()}


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _case(case: dict) -> dict:
    candidate_id = f"benchmark:{case['id']}"
    sources = [EvidenceSource(source="resume", source_file=f"{case['id']}.resume.txt", text=case["resume"])]
    if case.get("supporting_evidence"):
        sources.append(EvidenceSource(source="supporting", source_file=f"{case['id']}.evidence.txt", text=str(case["supporting_evidence"])))
    ledger = build_evidence_ledger(candidate_id, sources)
    requirements = extract_requirements(case["job_description"])
    mappings = map_requirements(requirements, ledger)
    gates = evaluate_hard_gates(requirements, ledger)
    changes = propose_supported_changes(case["resume"], requirements, mappings, ledger)

    predicted_supported = {
        term.lower()
        for mapping in mappings
        if mapping["coverage"] in {"direct", "transferable"}
        for term in mapping.get("normalized_terms", [])
    }
    predicted_unsupported = {
        term.lower()
        for mapping in mappings
        if mapping["coverage"] == "unsupported"
        for term in mapping.get("normalized_terms", [])
    }
    # Schema-v2 names are preferred; v1 fixtures used ``evidence`` for the
    # expected supported terms and ``expected_unsupported_claims`` for gaps.
    unsupported_v1 = case.get("expected_unsupported_claims")
    expected_supported = _set(
        case.get("expected_supported_terms")
        if case.get("expected_supported_terms") is not None
        else ([] if unsupported_v1 else case.get("evidence"))
    )
    expected_unsupported = _set(
        case.get("expected_unsupported_terms")
        if case.get("expected_unsupported_terms") is not None
        else unsupported_v1
    )
    expected_gates = {
        str(item["kind"]): str(item["status"])
        for item in case.get("expected_hard_gates", [])
        if isinstance(item, dict)
    }
    predicted_gates = {item["kind"]: item["status"] for item in gates}

    provenance_total = sum(mapping["coverage"] != "unsupported" for mapping in mappings)
    provenance_hits = sum(bool(mapping.get("evidence_ids")) for mapping in mappings if mapping["coverage"] != "unsupported")
    safe_rewrites = 0
    unsafe_rewrites = 0
    forbidden_terms = _set(case.get("forbidden_rewrite_terms"))
    forbidden_rewrite_hits = 0
    for change in changes:
        if not change.get("supported"):
            continue
        for variant in change.get("variants", []):
            variant_text = variant["text"].lower()
            forbidden_rewrite_hits += sum(term in variant_text for term in forbidden_terms)
            try:
                validate_change({**change, "replacement_text": variant["text"]}, ledger)
                safe_rewrites += 1
            except ValueError:
                unsafe_rewrites += 1

    gate_hits = sum(predicted_gates.get(kind) == status for kind, status in expected_gates.items())
    return {
        "id": case["id"],
        "supported_hits": len(expected_supported & predicted_supported),
        "supported_total": len(expected_supported),
        "unsupported_hits": len(expected_unsupported & predicted_unsupported),
        "unsupported_total": len(expected_unsupported),
        "provenance_hits": provenance_hits,
        "provenance_total": provenance_total,
        "hard_gate_hits": gate_hits,
        "hard_gate_total": len(expected_gates),
        "safe_rewrites": safe_rewrites,
        "unsafe_rewrites": unsafe_rewrites,
        "forbidden_rewrite_hits": forbidden_rewrite_hits,
    }


def run(dataset: Path) -> dict:
    cases = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    results = [_case(case) for case in cases]
    def total(key: str) -> int:
        return sum(int(item[key]) for item in results)

    return {
        "case_count": len(results),
        "cases": results,
        "supported_requirement_recall": _ratio(total("supported_hits"), total("supported_total")),
        "unsupported_requirement_detection_rate": _ratio(total("unsupported_hits"), total("unsupported_total")),
        "evidence_provenance_coverage": _ratio(total("provenance_hits"), total("provenance_total")),
        "hard_gate_accuracy": _ratio(total("hard_gate_hits"), total("hard_gate_total")),
        "rewrite_validator_pass_rate": _ratio(total("safe_rewrites"), total("safe_rewrites") + total("unsafe_rewrites")),
        "unsafe_rewrite_count": total("unsafe_rewrites"),
        "forbidden_rewrite_hit_count": total("forbidden_rewrite_hits"),
        "parser_risk_delta": None,
        "human_rewrite_preference": None,
        "measurement_status": {
            "parser_risk_delta": "not_implemented",
            "human_rewrite_preference": "requires human-labelled evaluation",
        },
    }
