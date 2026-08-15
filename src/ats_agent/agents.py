"""Deterministic Career Intelligence report stages.

These stages explain parsing, role alignment, language risks, and interview
questions. They do not verify candidate facts and do not predict employer
acceptance. Verified evidence is handled by :mod:`ats_agent.evidence`.
"""
from __future__ import annotations

import re
from typing import Any

from .requirements import TERM_ALIASES, extract_requirements

GENERIC = (
    "innovative",
    "cutting-edge",
    "passionate about",
    "leveraged ai",
    "results-driven",
)
WEAK = (
    "helped",
    "worked on",
    "assisted",
    "participated in",
    "responsible for",
)
ROLE_TERMS = (
    "ai",
    "product",
    "engineer",
    "analyst",
    "strategy",
    "operations",
    "finance",
    "founder",
)


def _lower(text: str) -> str:
    return str(text or "").lower()


def _terms(text: str) -> list[str]:
    return sorted(set(re.findall(r"[a-z][a-z0-9+#.-]{2,}", _lower(text))))


def _contains_alias(text: str, alias: str) -> bool:
    return (
        re.search(
            rf"(?<![a-z0-9]){re.escape(alias.lower())}(?![a-z0-9])",
            text.lower(),
        )
        is not None
    )


def _contains_term(text: str, term: str) -> bool:
    return any(
        _contains_alias(text, alias)
        for alias in TERM_ALIASES.get(term, (term,))
    )


def _claims(cv: str) -> list[str]:
    return [
        line.strip(" -*•▪◦")
        for line in str(cv).splitlines()
        if re.match(r"^\s*[-*•▪◦]", line) and line.strip(" -*•▪◦")
    ]


def jd_intelligence(jd: str) -> dict[str, Any]:
    requirements = extract_requirements(jd)
    body = _lower(jd)
    return {
        "agent": "jd-intelligence",
        "requirements": requirements,
        "seniority": next(
            (
                level
                for level in ("principal", "senior", "lead", "manager")
                if _contains_alias(body, level)
            ),
            "unspecified",
        ),
        "vocabulary": _terms(jd)[:80],
    }


def ats(cv: str, jd: str = "") -> dict[str, Any]:
    lines = str(cv or "").splitlines()
    issues: list[str] = []
    if not str(cv or "").strip():
        issues.append("resume contains no extractable text")
    if not re.search(
        r"(?im)^\s*(summary|experience|education|projects|skills)\s*:?[ \t]*$",
        cv,
    ):
        issues.append("standard section headings are not clearly detected")
    if "|" in cv or any("\t" in line for line in lines):
        issues.append("table or tabular spacing may reduce reading-order fidelity")
    if not re.search(r"\b(?:19|20)\d{2}\b", cv):
        issues.append("no year-like date detected")

    requirements = extract_requirements(jd)
    required_terms = [
        term
        for requirement in requirements
        for term in requirement.get("normalized_terms", [])
    ]
    covered_terms = [term for term in required_terms if _contains_term(cv, term)]
    return {
        "agent": "ats",
        "parseable": not issues,
        "issues": issues,
        "required_terms": required_terms,
        "covered_terms": sorted(set(covered_terms)),
    }


def keywords(cv: str, jd: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for requirement in extract_requirements(jd):
        terms = list(requirement.get("normalized_terms", []))
        covered = bool(terms) and all(_contains_term(cv, term) for term in terms)
        rows.append(
            {
                "requirement_id": requirement["id"],
                "terms": terms,
                "importance": requirement["importance"],
                "covered": covered,
                "action": (
                    "retain"
                    if covered
                    else "surface only when supported by candidate evidence"
                ),
            }
        )
    coverage = sum(row["covered"] for row in rows) / len(rows) if rows else None
    return {
        "agent": "keyword-strategy",
        "rows": rows,
        "coverage": coverage,
        "coverage_kind": "transparent_requirement_coverage",
    }


def language(cv: str) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    body = _lower(cv)
    for phrase in GENERIC:
        if phrase in body:
            findings.append(
                {
                    "type": "generic-language",
                    "phrase": phrase,
                    "suggestion": (
                        "replace with a concrete action, system, user, and result"
                    ),
                }
            )
    for phrase in WEAK:
        if phrase in body:
            findings.append(
                {
                    "type": "weak-verb",
                    "phrase": phrase,
                    "suggestion": "clarify the strongest truthful ownership level",
                }
            )
    bullets = _claims(cv)
    metric_signals = sum(
        bool(
            re.search(
                r"\d|%|tests?|users?|records?|github|https?://",
                line,
                re.IGNORECASE,
            )
        )
        for line in bullets
    )
    return {
        "agent": "language-optimization",
        "findings": findings,
        "bullet_count": len(bullets),
        "metric_signal_bullets": metric_signals,
        "note": "A metric signal is not proof that the claim is verified.",
    }


def recruiter(cv: str, jd: str) -> dict[str, Any]:
    first = " ".join(str(cv).splitlines()[:12])
    keyword_report = keywords(cv, jd)
    rows: list[dict[str, Any]] = keyword_report["rows"]
    mandatory = [row for row in rows if row["importance"] == "mandatory"]
    missing_mandatory = [
        term
        for row in mandatory
        if not row["covered"]
        for term in row["terms"]
    ]
    positive_signals: list[str] = []
    blocking_signals: list[str] = []

    if re.search(r"summary|profile", first, re.IGNORECASE):
        positive_signals.append("clear summary section appears near the top")
    if any(_contains_alias(first, term) for term in ROLE_TERMS):
        positive_signals.append("target role or professional direction is visible")
    covered = [
        term
        for row in rows
        if row["covered"]
        for term in row["terms"]
    ]
    if covered:
        positive_signals.append(
            "supported terminology visible: " + ", ".join(sorted(set(covered)))
        )
    if missing_mandatory:
        blocking_signals.append(
            "mandatory terminology not evidenced in the CV: "
            + ", ".join(sorted(set(missing_mandatory)))
        )

    if mandatory and not missing_mandatory and positive_signals:
        decision = "aligned"
        confidence = "high"
    elif positive_signals or (mandatory and len(missing_mandatory) < len(mandatory)):
        decision = "partially-aligned"
        confidence = "medium"
    else:
        decision = "unclear"
        confidence = "low"

    return {
        "agent": "recruiter-simulation",
        "decision": decision,
        "confidence": confidence,
        "positive_signals": positive_signals,
        "blocking_signals": blocking_signals,
        "unknowns": [
            "The disposition is heuristic and is not calibrated to an employer decision."
        ],
    }


def hiring_manager(cv: str, jd: str) -> dict[str, Any]:
    claims = _claims(cv)
    questions = [
        {
            "claim": claim,
            "question": f"What evidence and validation support this claim: {claim}",
        }
        for claim in claims
        if re.search(
            r"built|designed|architect|led|launched|owned|developed|increased|reduced",
            claim,
            re.IGNORECASE,
        )
    ]
    hard_requirements = [
        requirement["text"]
        for requirement in extract_requirements(jd)
        if requirement["importance"] == "mandatory"
    ]
    return {
        "agent": "hiring-manager",
        "credibility": "review-needed" if questions else "low-signal",
        "questions": questions[:8],
        "hard_requirements": hard_requirements,
    }


def evidence(cv: str) -> dict[str, Any]:
    rows = [
        {
            "id": f"C{index}",
            "claim": claim,
            "verified": False,
            "verification_status": "unverified",
            "source_span": f"resume bullet {index}",
        }
        for index, claim in enumerate(_claims(cv), 1)
    ]
    return {
        "agent": "evidence-achievement",
        "claims": rows,
        "source_of_truth": "Use the proposal evidence ledger for verified provenance.",
    }


def career_report(cv: str, jd: str) -> dict[str, Any]:
    agent_reports: dict[str, dict[str, Any]] = {
        "ats": ats(cv, jd),
        "jd": jd_intelligence(jd),
        "keywords": keywords(cv, jd),
        "language": language(cv),
        "recruiter": recruiter(cv, jd),
        "hiring_manager": hiring_manager(cv, jd),
        "evidence": evidence(cv),
    }
    agent_reports["company_alignment"] = {
        "agent": "company-language-alignment",
        "matched_vocabulary": [
            term
            for term in agent_reports["jd"]["vocabulary"]
            if term in _terms(cv)
        ][:20],
        "source_status": "job-description-only",
    }
    evidence_claims: list[dict[str, Any]] = agent_reports["evidence"]["claims"]
    agent_reports["interview_defense"] = {
        "agent": "interview-defense",
        "follow_ups": [row["claim"] for row in evidence_claims],
    }
    return {"schema_version": 2, "agents": agent_reports}


def proposals(cv: str, jd: str, report: dict[str, Any]) -> list[dict[str, Any]]:
    """Return non-applicable legacy suggestions.

    The supported rewrite path lives in :func:`rewriting.propose_supported_changes`,
    where every change is validated against a candidate-specific evidence ledger.
    """
    del cv, jd
    suggestions: list[dict[str, Any]] = []
    language_findings: list[dict[str, str]] = report["agents"]["language"]["findings"]
    for finding in language_findings:
        suggestions.append(
            {
                "id": f"L{len(suggestions) + 1}",
                "kind": finding["type"],
                "operation": "none",
                "expected_text": finding["phrase"],
                "replacement_text": "",
                "evidence_ids": [],
                "supported": False,
                "reason": (
                    "Legacy report suggestion only; use the evidence-grounded rewrite engine."
                ),
            }
        )
    return suggestions
