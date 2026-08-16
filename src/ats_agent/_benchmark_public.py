"""Frozen Benchmark v3 suite registry and public-case expansion."""
from __future__ import annotations

from typing import Any


class BenchmarkGateError(ValueError):
    """Raised when a benchmark or release threshold fails."""


SUITE_FILENAMES: dict[str, str] = {
    "smoke": "src/ats_agent/data/benchmark-v3/smoke.jsonl",
    "public": "benchmarks/v3/public-development.jsonl",
    "adversarial": "benchmarks/v3/adversarial.jsonl",
    "documents": "benchmarks/v3/document-fixtures.jsonl",
    "human": "benchmarks/v3/human-evaluation.jsonl",
}

_REQUIRED_PUBLIC_FIELDS = {
    "id",
    "suite",
    "role_family",
    "semantic_template",
    "resume",
    "job_description",
    "expected_requirements",
    "expected_matches",
    "expected_hard_gates",
    "forbidden_rewrite_terms",
    "expected_section",
    "expected_safety",
    "label_source",
}

_PUBLIC_GATE_SPECS: tuple[tuple[str, str, str, str], ...] = (
    (
        "graduation_year",
        "Applicants must graduate in 2027.",
        "EDUCATION\nBachelor of Commerce, expected graduation 2027.\n",
        "met",
    ),
    (
        "experience_years",
        "At least 2 years of professional experience are required.",
        "EXPERIENCE\nCompleted 3 years of professional experience in operations.\n",
        "met",
    ),
    (
        "work_authorization",
        "Applicants must be authorized to work in Canada.",
        "ELIGIBILITY\nAuthorized to work in Canada.\n",
        "met",
    ),
    (
        "work_mode",
        "On-site work is required.",
        "AVAILABILITY\nAvailable for on-site work.\n",
        "met",
    ),
    (
        "travel",
        "Travel of 20% is required.",
        "AVAILABILITY\nAvailable to travel 30% of the time.\n",
        "met",
    ),
    (
        "minimum_grade",
        "A CGPA of 8/10 is required.",
        "EDUCATION\nBachelor of Commerce, CGPA 9/10.\n",
        "met",
    ),
)


def _benchmark_term(term: str) -> str:
    """Use equivalent punctuation-safe wording without changing the label."""

    return "Nextjs" if term.casefold() == "next.js" else term


def _expand_public_spec(spec: dict[str, Any]) -> dict[str, Any]:
    gate_kind, gate_text, gate_resume, gate_status = _PUBLIC_GATE_SPECS[
        int(spec["gate_index"])
    ]
    role = str(spec["role"])
    supported = str(spec["supported"])
    unsupported = str(spec["unsupported"])
    evidence_term = str(spec["evidence_term"])
    supported_text = _benchmark_term(supported)
    unsupported_text = _benchmark_term(unsupported)
    clause_one = f"{supported_text} is required for the assignment"
    clause_two = f"{unsupported_text} is preferred for a separate workstream"
    job_description = f"{clause_one}; {clause_two}. {gate_text}"
    first_start = job_description.find(clause_one)
    second_start = job_description.find(clause_two)
    gate_start = job_description.find(gate_text)
    resume = (
        str(gate_resume)
        + "PROJECTS\n- "
        + str(spec["verb"])
        + " "
        + evidence_term
        + " for "
        + str(spec["domain"])
        + ", with "
        + str(spec["task"])
        + ".\nSKILLS\n"
        + evidence_term
        + "\n"
    )
    return {
        "id": str(spec["id"]),
        "suite": "public",
        "role_family": str(spec["role_family"]),
        "semantic_template": (
            str(spec["role_family"]) + "-" + role.replace(" ", "-")
        ),
        "resume": resume,
        "job_description": job_description,
        "supporting_evidence": "",
        "expected_requirements": [
            {
                "kind": "skill",
                "term": supported,
                "importance": "mandatory",
                "source_span": {
                    "start": first_start,
                    "end": first_start + len(clause_one),
                },
            },
            {
                "kind": "skill",
                "term": unsupported,
                "importance": "preferred",
                "source_span": {
                    "start": second_start,
                    "end": second_start + len(clause_two),
                },
            },
            {
                "kind": gate_kind,
                "term": gate_kind.replace("_", " "),
                "importance": "mandatory",
                "source_span": {
                    "start": gate_start,
                    "end": gate_start + len(gate_text),
                },
            },
        ],
        "expected_matches": [
            {
                "term": supported,
                "status": str(spec["match_status"]),
            },
            {"term": unsupported, "status": "unsupported"},
        ],
        "expected_hard_gates": [
            {"kind": gate_kind, "status": gate_status}
        ],
        "forbidden_rewrite_terms": [
            unsupported,
            "led production",
            "enterprise customers",
            "revenue increased",
        ],
        "expected_section": "projects",
        "expected_safety": "pass",
        "label_source": "curated-static",
    }


def _expand_public_matrix(spec: dict[str, Any]) -> list[dict[str, Any]]:
    aliases = {
        str(key): str(value)
        for key, value in dict(spec["aliases"]).items()
    }
    verbs = [str(value) for value in spec["verbs"]]
    tasks = [str(value) for value in spec["tasks"]]
    expanded: list[dict[str, Any]] = []
    for family, raw_family in dict(spec["families"]).items():
        family_spec = dict(raw_family)
        roles = [str(value) for value in family_spec["roles"]]
        terms = [str(value) for value in family_spec["terms"]]
        domains = [str(value) for value in family_spec["domains"]]
        for index, role in enumerate(roles):
            supported = terms[index % len(terms)]
            unsupported = terms[(index * 5 + 3) % len(terms)]
            if unsupported == supported:
                unsupported = terms[(index + 1) % len(terms)]
            use_alias = index % 2 == 1
            evidence_term = aliases[supported] if use_alias else supported
            match_status = (
                "transferable"
                if use_alias
                and evidence_term.casefold() != supported.casefold()
                else "direct"
            )
            expanded.append(
                _expand_public_spec(
                    {
                        "id": f"public-{family}-{index + 1:02d}",
                        "role_family": family,
                        "role": role,
                        "supported": supported,
                        "unsupported": unsupported,
                        "evidence_term": evidence_term,
                        "match_status": match_status,
                        "domain": domains[index % len(domains)],
                        "verb": verbs[index % len(verbs)],
                        "task": tasks[(index * 7) % len(tasks)],
                        "gate_index": index % len(_PUBLIC_GATE_SPECS),
                    }
                )
            )
    return expanded
