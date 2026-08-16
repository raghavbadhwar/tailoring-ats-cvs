"""Evaluate ordinary labelled CV and job-description benchmark cases."""
from __future__ import annotations

import time
from typing import Any

from ._benchmark_validate import (
    _expected_requirement_key,
    _normalize_match_status,
    _normalized_text,
    _requirement_key,
    _span_overlap,
)


def _evaluate_standard_case(case: dict[str, Any]) -> dict[str, Any]:
    from .evidence import EvidenceSource, build_evidence_ledger
    from .requirements import (
        evaluate_hard_gates,
        extract_requirements,
        map_requirements,
    )
    from .rewriting import propose_supported_changes
    from .validation import validate_change

    started = time.perf_counter()
    candidate_id = f"benchmark:{case['id']}"
    sources = [
        EvidenceSource(
            source="resume",
            source_file=f"{case['id']}.resume.txt",
            text=str(case.get("resume") or ""),
            candidate_id=candidate_id,
        )
    ]
    if case.get("supporting_evidence"):
        sources.append(
            EvidenceSource(
                source="supporting",
                source_file=f"{case['id']}.evidence.txt",
                text=str(case["supporting_evidence"]),
                candidate_id=candidate_id,
            )
        )
    ledger = build_evidence_ledger(candidate_id, sources)
    requirements = extract_requirements(str(case.get("job_description") or ""))
    mappings = map_requirements(requirements, ledger)
    gates = evaluate_hard_gates(requirements, ledger)
    changes = propose_supported_changes(
        str(case.get("resume") or ""),
        requirements,
        mappings,
        ledger,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000

    expected_requirements = list(case.get("expected_requirements") or [])
    expected_keys = {
        _expected_requirement_key(requirement)
        for requirement in expected_requirements
    }
    predicted_keys = {
        _requirement_key(requirement) for requirement in requirements
    }
    unexpected_keys = sorted(predicted_keys - expected_keys)
    missing_keys = sorted(expected_keys - predicted_keys)
    requirement_tp = len(expected_keys & predicted_keys)
    requirement_fp = len(unexpected_keys)
    requirement_fn = len(missing_keys)

    predicted_by_key = {
        _requirement_key(requirement): requirement
        for requirement in requirements
    }
    span_overlap_total = 0.0
    span_overlap_count = 0
    for expected in expected_requirements:
        key = _expected_requirement_key(expected)
        predicted = predicted_by_key.get(key)
        if predicted is not None:
            span_overlap_total += _span_overlap(expected, predicted)
            span_overlap_count += 1

    predicted_matches: dict[str, dict[str, Any]] = {}
    for mapping in mappings:
        if mapping.get("kind") != "skill":
            continue
        for term in mapping.get("normalized_terms") or []:
            predicted_matches[str(term).casefold()] = mapping

    expected_matches = {
        str(item.get("term") or "").casefold(): _normalize_match_status(
            item.get("status")
        )
        for item in case.get("expected_matches") or []
    }
    expected_supported = {
        term
        for term, status in expected_matches.items()
        if status in {"direct", "transferable"}
    }
    predicted_supported = {
        term
        for term, mapping in predicted_matches.items()
        if _normalize_match_status(mapping.get("coverage"))
        in {"direct", "transferable"}
    }
    match_tp = len(expected_supported & predicted_supported)
    match_fp = len(predicted_supported - expected_supported)
    match_fn = len(expected_supported - predicted_supported)

    expected_unsupported = {
        term for term, status in expected_matches.items() if status == "unsupported"
    }
    predicted_unsupported = {
        term
        for term, mapping in predicted_matches.items()
        if _normalize_match_status(mapping.get("coverage")) == "unsupported"
    }
    unsupported_tp = len(expected_unsupported & predicted_unsupported)
    unsupported_fp = len(predicted_unsupported - expected_unsupported)
    unsupported_fn = len(expected_unsupported - predicted_unsupported)

    status_hits = sum(
        _normalize_match_status(
            predicted_matches.get(term, {}).get("coverage")
        )
        == status
        for term, status in expected_matches.items()
    )
    status_total = len(expected_matches)

    provenance_total = len(expected_supported)
    provenance_hits = sum(
        bool(predicted_matches.get(term, {}).get("evidence_ids"))
        for term in expected_supported
    )

    expected_gates = {
        str(item.get("kind")): str(item.get("status"))
        for item in case.get("expected_hard_gates") or []
    }
    predicted_gates = {
        str(item.get("kind")): str(item.get("status")) for item in gates
    }
    gate_hits = sum(
        predicted_gates.get(kind) == status
        for kind, status in expected_gates.items()
    )

    safe_variants = 0
    unsafe_variants = 0
    metric_binding_violations = 0
    ownership_violations = 0
    forbidden_hits = 0
    variant_complete = 0
    variant_distinct = 0
    section_hits = 0
    section_total = 0
    supported_changes = [
        change for change in changes if change.get("supported")
    ]
    forbidden_terms = {
        str(term).casefold()
        for term in case.get("forbidden_rewrite_terms") or []
    }
    for change in supported_changes:
        variants = list(change.get("variants") or [])
        variant_ids = {str(variant.get("id")) for variant in variants}
        if {"conservative", "balanced", "compact"} <= variant_ids:
            variant_complete += 1
        normalized_variants = {
            _normalized_text(variant.get("text") or "") for variant in variants
        }
        if len(normalized_variants) == len(variants) and len(variants) >= 3:
            variant_distinct += 1
        if case.get("expected_section"):
            section_total += 1
            if change.get("target_section") == case["expected_section"]:
                section_hits += 1
        for variant in variants:
            text = str(variant.get("text") or "")
            body = text.casefold()
            forbidden_hits += sum(term in body for term in forbidden_terms)
            try:
                validate_change(
                    {**change, "replacement_text": text},
                    ledger,
                )
                safe_variants += 1
            except ValueError as exc:
                unsafe_variants += 1
                message = str(exc).casefold()
                metric_binding_violations += "metric binding" in message
                ownership_violations += "ownership escalation" in message

    return {
        "id": str(case["id"]),
        "requirement_tp": requirement_tp,
        "requirement_fp": requirement_fp,
        "requirement_fn": requirement_fn,
        "unexpected_requirements": [list(key) for key in unexpected_keys],
        "missing_requirements": [list(key) for key in missing_keys],
        "importance_hits": requirement_tp,
        "importance_total": len(expected_keys),
        "span_overlap_total": span_overlap_total,
        "span_overlap_count": span_overlap_count,
        "match_tp": match_tp,
        "match_fp": match_fp,
        "match_fn": match_fn,
        "unsupported_tp": unsupported_tp,
        "unsupported_fp": unsupported_fp,
        "unsupported_fn": unsupported_fn,
        "match_status_hits": status_hits,
        "match_status_total": status_total,
        "provenance_hits": provenance_hits,
        "provenance_total": provenance_total,
        "gate_hits": gate_hits,
        "gate_total": len(expected_gates),
        "safe_variants": safe_variants,
        "unsafe_variants": unsafe_variants,
        "metric_binding_violations": metric_binding_violations,
        "ownership_violations": ownership_violations,
        "forbidden_hits": forbidden_hits,
        "variant_complete": variant_complete,
        "variant_total": len(supported_changes),
        "variant_distinct": variant_distinct,
        "section_hits": section_hits,
        "section_total": section_total,
        "latency_ms": elapsed_ms,
    }
