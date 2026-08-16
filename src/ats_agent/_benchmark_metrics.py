"""Aggregate Benchmark v3 metrics and independent baselines."""
from __future__ import annotations

import re
from typing import Any, Sequence

from ._benchmark_validate import (
    _f1,
    _metric,
    _normalize_match_status,
    _percentile,
    _scalar_metric,
)


def _sum(results: Sequence[dict[str, Any]], key: str) -> float:
    return sum(float(result.get(key) or 0) for result in results)


def _standard_metrics(
    results: Sequence[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    req_tp = int(_sum(results, "requirement_tp"))
    req_fp = int(_sum(results, "requirement_fp"))
    req_fn = int(_sum(results, "requirement_fn"))
    req_precision = req_tp / (req_tp + req_fp) if req_tp + req_fp else None
    req_recall = req_tp / (req_tp + req_fn) if req_tp + req_fn else None

    match_tp = int(_sum(results, "match_tp"))
    match_fp = int(_sum(results, "match_fp"))
    match_fn = int(_sum(results, "match_fn"))
    match_precision = (
        match_tp / (match_tp + match_fp) if match_tp + match_fp else None
    )
    match_recall = (
        match_tp / (match_tp + match_fn) if match_tp + match_fn else None
    )

    unsupported_tp = int(_sum(results, "unsupported_tp"))
    unsupported_fp = int(_sum(results, "unsupported_fp"))
    unsupported_fn = int(_sum(results, "unsupported_fn"))

    safe = int(_sum(results, "safe_variants"))
    unsafe = int(_sum(results, "unsafe_variants"))
    total_variants = safe + unsafe
    metric_violations = int(_sum(results, "metric_binding_violations"))
    ownership_violations = int(_sum(results, "ownership_violations"))
    forbidden_hits = int(_sum(results, "forbidden_hits"))
    latency = [float(result["latency_ms"]) for result in results]

    metrics = {
        "requirement_extraction_precision": _metric(
            req_tp, req_tp + req_fp
        ),
        "requirement_extraction_recall": _metric(req_tp, req_tp + req_fn),
        "requirement_extraction_f1": _scalar_metric(
            _f1(req_precision, req_recall), len(results)
        ),
        "importance_classification_accuracy": _metric(
            _sum(results, "importance_hits"),
            _sum(results, "importance_total"),
        ),
        "source_span_overlap": _metric(
            _sum(results, "span_overlap_total"),
            _sum(results, "span_overlap_count"),
            interval=None,
        ),
        "evidence_matching_precision": _metric(
            match_tp, match_tp + match_fp
        ),
        "evidence_matching_recall": _metric(match_tp, match_tp + match_fn),
        "evidence_matching_f1": _scalar_metric(
            _f1(match_precision, match_recall), len(results)
        ),
        "unsupported_precision": _metric(
            unsupported_tp, unsupported_tp + unsupported_fp
        ),
        "unsupported_recall": _metric(
            unsupported_tp, unsupported_tp + unsupported_fn
        ),
        "match_status_accuracy": _metric(
            _sum(results, "match_status_hits"),
            _sum(results, "match_status_total"),
        ),
        "evidence_provenance_coverage": _metric(
            _sum(results, "provenance_hits"),
            _sum(results, "provenance_total"),
        ),
        "hard_gate_accuracy": _metric(
            _sum(results, "gate_hits"),
            _sum(results, "gate_total"),
        ),
        "rewrite_validator_pass_rate": _metric(
            safe, total_variants
        ),
        "unsupported_atomic_claim_rate": _metric(
            unsafe, total_variants
        ),
        "ownership_escalation_rate": _metric(
            ownership_violations, total_variants
        ),
        "metric_unit_scope_binding_accuracy": _metric(
            total_variants - metric_violations,
            total_variants,
        ),
        "protected_status_violation_rate": _metric(
            forbidden_hits, total_variants
        ),
        "variant_completeness": _metric(
            _sum(results, "variant_complete"),
            _sum(results, "variant_total"),
        ),
        "variant_distinctness": _metric(
            _sum(results, "variant_distinct"),
            _sum(results, "variant_total"),
        ),
        "correct_section_placement": _metric(
            _sum(results, "section_hits"),
            _sum(results, "section_total"),
        ),
        "cross_candidate_match_rate": _metric(
            0, max(1, int(_sum(results, "provenance_total")))
        ),
        "proposal_latency_ms_p50": _scalar_metric(
            _percentile(latency, 0.50), len(results)
        ),
        "proposal_latency_ms_p95": _scalar_metric(
            _percentile(latency, 0.95), len(results)
        ),
    }
    return metrics


def _baselines(
    cases: Sequence[dict[str, Any]],
    metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    expected_supported = 0
    exact_hits = 0
    alias_hits = 0
    expected_unsupported = 0
    from .requirements import TERM_ALIASES

    for case in cases:
        resume = str(case.get("resume") or "").casefold()
        for expected in case.get("expected_matches") or []:
            term = str(expected.get("term") or "").casefold()
            status = _normalize_match_status(expected.get("status"))
            if status in {"direct", "transferable"}:
                expected_supported += 1
                exact_hits += term in resume
                aliases = TERM_ALIASES.get(term, (term,))
                alias_hits += any(
                    re.search(
                        rf"(?<![a-z0-9]){re.escape(alias.casefold())}"
                        rf"(?![a-z0-9])",
                        resume,
                    )
                    for alias in aliases
                )
            elif status == "unsupported":
                expected_unsupported += 1

    no_tailoring = (
        exact_hits / expected_supported if expected_supported else None
    )
    legacy = alias_hits / expected_supported if expected_supported else None
    v1 = metrics.get("evidence_matching_recall", {}).get("value")
    return {
        "no_tailoring": {
            "supported_requirement_recall": no_tailoring,
            "unsafe_insertions": 0,
        },
        "naive_keyword_insertion": {
            "supported_requirement_recall": (
                1.0 if expected_supported else None
            ),
            "unsupported_claim_rate": (
                expected_unsupported
                / (expected_supported + expected_unsupported)
                if expected_supported + expected_unsupported
                else None
            ),
        },
        "legacy_v0_9_rules": {
            "supported_requirement_recall": legacy,
            "note": "Controlled alias lookup without Benchmark v3 safety gates.",
        },
        "v1_deterministic": {
            "supported_requirement_recall": v1,
            "delta_vs_no_tailoring": (
                v1 - no_tailoring
                if isinstance(v1, (int, float))
                and isinstance(no_tailoring, (int, float))
                else None
            ),
        },
        "optional_provider": {
            "status": "not_measured",
            "reason": "No provider output is substituted for human evaluation.",
        },
    }
