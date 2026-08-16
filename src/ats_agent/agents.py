"""Explainable report stages built on the evidence-grounded core."""
from __future__ import annotations

import re

from .evidence import EvidenceLedger
from .requirements import extract_requirements, map_requirements

GENERIC = ("innovative", "cutting-edge", "passionate about", "leveraged ai", "results-driven")
ROLE_TERMS = ("ai", "product", "engineer", "analyst", "strategy", "operations", "finance", "founder")


def _claims(cv: str) -> list[str]:
    return [
        line.strip(" -*•▪◦")
        for line in cv.splitlines()
        if re.match(r"^\s*[-*•▪◦]", line) and line.strip(" -*•▪◦")
    ]


def career_report(
    cv: str,
    jd: str,
    *,
    ledger: EvidenceLedger | None = None,
    requirements: list[dict] | None = None,
    mappings: list[dict] | None = None,
    hard_gates: list[dict] | None = None,
) -> dict:
    requirements = requirements if requirements is not None else extract_requirements(jd)
    mappings = mappings if mappings is not None else (map_requirements(requirements, ledger) if ledger else [])
    mandatory = [mapping for mapping in mappings if mapping["importance"] == "mandatory"]
    unsupported_mandatory = [mapping for mapping in mandatory if mapping["coverage"] == "unsupported"]
    first = " ".join(cv.splitlines()[:12])
    positive: list[str] = []
    if re.search(r"summary|profile", first, re.I):
        positive.append("summary or profile is visible near the top")
    if any(re.search(rf"\b{re.escape(term)}\b", first, re.I) for term in ROLE_TERMS):
        positive.append("target role direction is visible")
    supported_terms = sorted({term for mapping in mappings if mapping["coverage"] != "unsupported" for term in mapping["normalized_terms"]})
    if supported_terms:
        positive.append("supported job terminology: " + ", ".join(supported_terms))
    blockers = [
        "mandatory requirement lacks candidate evidence: " + ", ".join(mapping["normalized_terms"])
        for mapping in unsupported_mandatory
    ]
    gate_blockers = [gate for gate in hard_gates or [] if gate["status"] == "unmet"]
    blockers.extend("hard gate appears unmet: " + gate["requirement"] for gate in gate_blockers)
    decision = "aligned" if positive and not blockers else "partially-aligned" if positive else "unclear"
    confidence = "high" if mappings and not blockers else "medium" if mappings else "low"
    generic_findings = [phrase for phrase in GENERIC if phrase in cv.lower()]
    claims = _claims(cv)
    return {
        "schema_version": 3,
        "agents": {
            "ats": {
                "agent": "ats-parser",
                "parseable": bool(cv.strip()),
                "required_terms": sorted({term for r in requirements for term in r.get("normalized_terms", [])}),
                "covered_terms": supported_terms,
            },
            "jd": {"agent": "jd-intelligence", "requirements": requirements},
            "keywords": {
                "agent": "keyword-strategy",
                "mappings": mappings,
                "coverage": (sum(m["coverage"] != "unsupported" for m in mappings) / len(mappings)) if mappings else None,
                "coverage_kind": "transparent_supported_requirement_coverage",
            },
            "language": {
                "agent": "language-optimization",
                "generic_phrases": generic_findings,
                "bullet_count": len(claims),
            },
            "recruiter": {
                "agent": "recruiter-simulation",
                "decision": decision,
                "confidence": confidence,
                "positive_signals": positive,
                "blocking_signals": blockers,
                "unknowns": ["This is an explainable heuristic, not a calibrated employer decision."],
            },
            "hiring_manager": {
                "agent": "hiring-manager",
                "credibility": "review-needed" if claims else "low-signal",
                "questions": [
                    {"claim": claim, "question": f"What evidence, architecture, trade-offs, and validation support this claim: {claim}"}
                    for claim in claims[:10]
                ],
            },
            "evidence": {
                "agent": "evidence-ledger",
                "candidate_id": ledger.candidate_id if ledger else None,
                "items": ledger.to_dicts() if ledger else [],
                # Compatibility view for callers that consume claim-level status.
                # A number in a CV is not external verification; without a source-
                # verified ledger record, the claim remains unverified.
                "claims": [
                    {
                        "claim": claim,
                        "verification_status": "unverified",
                        "verified": False,
                    }
                    for claim in claims
                ],
            },
            "company_alignment": {
                "agent": "company-language-alignment",
                "source_status": "job-description-only",
                "note": "Supply an official company-context file to add sourced terminology.",
            },
            "interview_defense": {
                "agent": "interview-defense",
                "follow_ups": [
                    {"claim": claim, "questions": ["What was your exact contribution?", "How was it validated?", "What was not production-ready?"]}
                    for claim in claims
                ],
            },
        },
    }
