"""Benchmark v3 compact-matrix expansion and JSONL loading."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ._benchmark_public import _expand_public_matrix, _expand_public_spec


def _format_matrix_value(
    value: Any,
    *,
    suffix: str,
    number: int,
) -> Any:
    if isinstance(value, str):
        return value.replace("{suffix}", suffix).replace(
            "{number}", str(number)
        )
    if isinstance(value, list):
        return [
            _format_matrix_value(item, suffix=suffix, number=number)
            for item in value
        ]
    if isinstance(value, dict):
        return {
            str(key): _format_matrix_value(
                item,
                suffix=suffix,
                number=number,
            )
            for key, item in value.items()
        }
    return value


def _expand_adversarial_matrix(
    spec: dict[str, Any],
) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    variants = [dict(item) for item in spec["variants"]]
    forbidden = [
        str(value) for value in spec["forbidden_rewrite_terms"]
    ]
    for raw_scenario in spec["scenarios"]:
        scenario = dict(raw_scenario)
        name = str(scenario.pop("scenario"))
        number_base = int(scenario.pop("number_base", 0))
        per_variant = dict(scenario.pop("per_variant", {}))
        additional_forbidden = [
            str(value)
            for value in scenario.pop("additional_forbidden", [])
        ]
        for index, variant in enumerate(variants):
            suffix = str(variant["suffix"])
            number = number_base + int(variant.get("offset", index))
            values = _format_matrix_value(
                scenario,
                suffix=suffix,
                number=number,
            )
            values.update(
                {
                    key: _format_matrix_value(
                        list(options)[index],
                        suffix=suffix,
                        number=number,
                    )
                    for key, options in per_variant.items()
                }
            )
            values.update(
                {
                    "id": f"adversarial-{name}-{suffix}",
                    "suite": "adversarial",
                    "role_family": str(variant["role_family"]),
                    "scenario": name,
                    "semantic_template": f"{name}-{suffix}",
                    "forbidden_rewrite_terms": (
                        forbidden + additional_forbidden
                    ),
                    "label_source": "curated-static",
                }
            )
            expanded.append(values)
    return expanded


def _expand_human_spec(spec: dict[str, Any]) -> dict[str, Any]:
    supported = str(spec["supported"])
    role = str(spec["role"])
    domain = str(spec["domain"])
    resume = f"PROJECTS\n- Supported {supported} work for {domain}.\n"
    return {
        "id": str(spec["id"]),
        "suite": "human",
        "role_family": str(spec["role_family"]),
        "semantic_template": (
            "human-"
            + str(spec["role_family"])
            + "-"
            + str(spec["id"]).rsplit("-", 1)[-1]
        ),
        "resume": resume,
        "job_description": f"{supported} is required for the {role} role.",
        "outputs": {
            "original": resume,
            "legacy_v0_9": None,
            "v1_deterministic_balanced": None,
            "optional_provider_balanced": None,
        },
        "ratings": None,
        "dimensions": [
            "factual_faithfulness",
            "relevance",
            "clarity",
            "concision",
            "credibility",
            "preference",
        ],
        "measurement_status": "awaiting_blinded_human_review",
        "label_source": "curated-static",
    }


def _expand_case_spec(
    case: dict[str, Any],
) -> dict[str, Any] | list[dict[str, Any]]:
    case_type = case.get("_type")
    if case_type == "public-v3":
        return _expand_public_spec(case)
    if case_type == "public-v3-matrix":
        return _expand_public_matrix(case)
    if case_type == "adversarial-v3-matrix":
        return _expand_adversarial_matrix(case)
    if case_type == "human-v3":
        return _expand_human_spec(case)
    return case


def load_cases(dataset: Path) -> list[dict[str, Any]]:
    """Load newline-delimited benchmark cases without deriving any labels."""

    path = dataset.expanduser().resolve()
    cases: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expanded = _expand_case_spec(json.loads(line))
        if isinstance(expanded, list):
            cases.extend(expanded)
        else:
            cases.append(expanded)
    if not cases:
        raise ValueError(f"benchmark dataset is empty: {path}")
    ids = [str(case.get("id") or "") for case in cases]
    if any(not case_id for case_id in ids):
        raise ValueError(f"benchmark case without id: {path}")
    if len(ids) != len(set(ids)):
        raise ValueError(f"benchmark dataset contains duplicate case ids: {path}")
    return cases
