"""Benchmark v3 diversity validation, metrics, and identifiers."""
from __future__ import annotations

import hashlib
import math
import os
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence

from ._benchmark_public import _REQUIRED_PUBLIC_FIELDS


def _normalized_text(value: object) -> str:
    text = re.sub(r"[^a-z0-9+#. ]+", " ", str(value).casefold())
    return re.sub(r"\s+", " ", text).strip()


def _number_agnostic_text(value: object) -> str:
    return re.sub(r"\b\d+(?:\.\d+)?\b", "<num>", _normalized_text(value))


def _pair_key(case: dict[str, Any], *, ignore_numbers: bool) -> tuple[str, str]:
    normalizer = _number_agnostic_text if ignore_numbers else _normalized_text
    return normalizer(case.get("resume", "")), normalizer(
        case.get("job_description", "")
    )


def validate_cases(
    cases: Sequence[dict[str, Any]],
    *,
    suite: str,
) -> dict[str, Any]:
    """Return fail-closed diversity and labelling diagnostics."""

    duplicate_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    numeric_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for case in cases:
        duplicate_groups[_pair_key(case, ignore_numbers=False)].append(
            str(case["id"])
        )
        numeric_groups[_pair_key(case, ignore_numbers=True)].append(
            str(case["id"])
        )

    if suite == "documents":
        duplicate_pairs: list[list[str]] = []
        numeric_only_duplicates: list[list[str]] = []
    else:
        duplicate_pairs = sorted(
            sorted(group)
            for group in duplicate_groups.values()
            if len(group) > 1
        )
        numeric_only_duplicates = []
        for group in numeric_groups.values():
            if len(group) < 2:
                continue
            exact_pairs = {
                _pair_key(
                    next(
                        item
                        for item in cases
                        if str(item["id"]) == case_id
                    ),
                    ignore_numbers=False,
                )
                for case_id in group
            }
            if len(exact_pairs) > 1:
                numeric_only_duplicates.append(sorted(group))
        numeric_only_duplicates.sort()

    templates = Counter(
        str(case.get("semantic_template") or "") for case in cases
    )
    template_limit = max(3, math.floor(len(cases) * 0.02))
    overrepresented_templates = {
        key: count
        for key, count in sorted(templates.items())
        if key and count > template_limit
    }

    overrepresented_role_families: dict[str, int] = {}
    if suite == "public":
        families = Counter(str(case.get("role_family") or "") for case in cases)
        family_limit = len(cases) * 0.25
        overrepresented_role_families = {
            key: count
            for key, count in sorted(families.items())
            if key and count > family_limit
        }

    missing_required_fields: list[dict[str, Any]] = []
    for case in cases:
        required = {
            "id",
            "suite",
            "role_family",
            "semantic_template",
            "label_source",
        }
        if suite == "public":
            required |= _REQUIRED_PUBLIC_FIELDS
        elif suite == "adversarial":
            required |= {"scenario", "resume", "job_description", "expected_safety"}
        elif suite == "documents":
            required |= {"format", "fixture", "expected_parse"}
        elif suite == "human":
            required |= {"resume", "job_description", "outputs", "ratings"}
        missing = sorted(key for key in required if key not in case)
        for expected in case.get("expected_requirements", []):
            span = expected.get("source_span")
            if not isinstance(span, dict) or not {
                "start",
                "end",
            } <= set(span):
                missing.append("expected_requirements[].source_span")
                break
        if case.get("label_source") == "engine-generated":
            missing.append("label_source must not be engine-generated")
        if missing:
            missing_required_fields.append(
                {"id": str(case.get("id")), "missing": sorted(set(missing))}
            )

    return {
        "suite": suite,
        "case_count": len(cases),
        "duplicate_pairs": duplicate_pairs,
        "numeric_only_duplicates": numeric_only_duplicates,
        "overrepresented_templates": overrepresented_templates,
        "overrepresented_role_families": overrepresented_role_families,
        "missing_required_fields": missing_required_fields,
    }


def wilson_interval(successes: int, total: int) -> tuple[float, float]:
    """Return a bounded 95% Wilson score interval."""

    if total <= 0:
        return (0.0, 0.0)
    z = 1.959963984540054
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(
            proportion * (1 - proportion) / total
            + z * z / (4 * total * total)
        )
        / denominator
    )
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _metric(
    numerator: float,
    denominator: float,
    *,
    status: str = "measured",
    interval: tuple[float, float] | None = None,
) -> dict[str, Any]:
    value = numerator / denominator if denominator else None
    if interval is None and denominator and float(numerator).is_integer():
        interval = wilson_interval(int(numerator), int(denominator))
    return {
        "status": status,
        "numerator": numerator,
        "denominator": denominator,
        "value": value,
        "confidence_interval_95": (
            [interval[0], interval[1]] if interval is not None else None
        ),
    }


def _scalar_metric(value: float | None, sample_count: int) -> dict[str, Any]:
    return {
        "status": "measured" if value is not None else "not_measured",
        "numerator": value,
        "denominator": 1 if value is not None else 0,
        "value": value,
        "confidence_interval_95": None,
        "sample_count": sample_count,
    }


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None or precision + recall == 0:
        return None
    return 2 * precision * recall / (precision + recall)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _code_sha(root: Path) -> str:
    configured = os.environ.get("GITHUB_SHA")
    if configured:
        return configured
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            text=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _percentile(values: Sequence[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _requirement_key(requirement: dict[str, Any]) -> tuple[str, str, str]:
    kind = str(requirement.get("kind") or "")
    if kind == "skill":
        terms = requirement.get("normalized_terms") or []
        term = str(terms[0] if terms else "")
    else:
        term = kind.replace("_", " ")
    return kind, term.casefold(), str(requirement.get("importance") or "")


def _expected_requirement_key(
    requirement: dict[str, Any],
) -> tuple[str, str, str]:
    kind = str(requirement.get("kind") or "")
    term = str(requirement.get("term") or kind.replace("_", " "))
    return kind, term.casefold(), str(requirement.get("importance") or "")


def _span_overlap(
    expected: dict[str, Any],
    predicted: dict[str, Any],
) -> float:
    left = expected.get("source_span") or {}
    right = predicted.get("source_span") or {}
    try:
        start = max(int(left["start"]), int(right["start"]))
        end = min(int(left["end"]), int(right["end"]))
        union_start = min(int(left["start"]), int(right["start"]))
        union_end = max(int(left["end"]), int(right["end"]))
    except (KeyError, TypeError, ValueError):
        return 0.0
    intersection = max(0, end - start)
    union = max(1, union_end - union_start)
    return intersection / union


def _normalize_match_status(status: object) -> str:
    value = str(status or "").casefold()
    if value == "equivalent":
        return "transferable"
    return value
