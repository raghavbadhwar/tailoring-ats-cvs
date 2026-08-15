"""Small, deterministic Career Intelligence agents.

The report is deliberately model-neutral: an optional model adapter may improve
wording later, but it cannot bypass the evidence and approval contract.
"""
from __future__ import annotations

import re

TERMS = {
    "technical": ("python", "typescript", "javascript", "sql", "api", "react", "postgres", "testing"),
    "product": ("product requirements", "roadmap", "discovery", "stakeholder", "prioritization"),
    "business": ("strategy", "market research", "market sizing", "operations", "procurement", "supply chain", "unit economics"),
    "ai": ("ai", "llm", "agent", "rag", "orchestration", "evaluation", "human-in-the-loop", "mcp"),
}
GENERIC = ("innovative", "cutting-edge", "passionate about", "leveraged ai", "results-driven")
WEAK = ("helped", "worked on", "assisted", "participated in", "responsible for")


def _lower(text: str) -> str:
    return str(text or "").lower()


def _terms(text: str) -> list[str]:
    return sorted(set(re.findall(r"[a-z][a-z0-9+#.-]{2,}", _lower(text))))


def jd_intelligence(jd: str) -> dict:
    body = _lower(jd)
    requirements = []
    for category, terms in TERMS.items():
        for term in terms:
            if term in body:
                requirements.append({"term": term, "category": category, "hard": bool(re.search(r"(required|must|mandatory).{0,80}" + re.escape(term), body))})
    return {"agent": "jd-intelligence", "requirements": requirements, "seniority": next((x for x in ("senior", "lead", "manager", "principal") if x in body), "unspecified"), "vocabulary": _terms(jd)[:80]}


def ats(cv: str, jd: str = "") -> dict:
    lines = str(cv or "").splitlines()
    issues = []
    if not str(cv or "").strip():
        issues.append("resume contains no extractable text")
    if not re.search(r"(?im)^\s*(summary|experience|education|projects|skills)\s*:?[ \t]*$", cv):
        issues.append("standard section headings are not clearly detected")
    if "|" in cv or any("\t" in line for line in lines):
        issues.append("table or tabular spacing may reduce reading-order fidelity")
    if not re.search(r"\b(?:19|20)\d{2}\b", cv):
        issues.append("no year-like date detected")
    required = [r["term"] for r in jd_intelligence(jd)["requirements"]]
    return {"agent": "ats", "parseable": not issues, "issues": issues, "required_terms": required, "covered_terms": [t for t in required if t in _lower(cv)]}


def keywords(cv: str, jd: str) -> dict:
    rows = []
    for req in jd_intelligence(jd)["requirements"]:
        covered = req["term"] in _lower(cv)
        rows.append({**req, "covered": covered, "action": "retain" if covered else "add only when supported by evidence"})
    return {"agent": "keyword-strategy", "rows": rows, "coverage": sum(r["covered"] for r in rows) / len(rows) if rows else 1.0}


def language(cv: str) -> dict:
    findings = []
    body = _lower(cv)
    for phrase in GENERIC:
        if phrase in body:
            findings.append({"type": "generic-language", "phrase": phrase, "suggestion": "replace with a concrete action, system, user, and result"})
    for phrase in WEAK:
        if phrase in body:
            findings.append({"type": "weak-verb", "phrase": phrase, "suggestion": "use the strongest truthful ownership verb"})
    bullets = [line for line in str(cv).splitlines() if re.match(r"^\s*[-*•]", line)]
    quantified = sum(bool(re.search(r"\d|%|tests?|users?|records?|github|https?://", line, re.IGNORECASE)) for line in bullets)
    return {"agent": "language-optimization", "findings": findings, "bullet_count": len(bullets), "quantified_bullets": quantified}


def recruiter(cv: str, jd: str) -> dict:
    first = " ".join(str(cv).splitlines()[:12])
    score = round(min(100, (25 if re.search(r"summary|profile", first, re.IGNORECASE) else 0) + (25 if re.search(r"ai|product|engineer|analyst|strategy", first, re.IGNORECASE) else 0) + keywords(cv, jd)["coverage"] * 50))
    return {"agent": "recruiter-simulation", "score": score, "decision": "interview" if score >= 65 else "unclear"}


def hiring_manager(cv: str, jd: str) -> dict:
    claims = [line.strip(" -*•") for line in str(cv).splitlines() if re.match(r"^\s*[-*•]", line)]
    questions = [{"claim": claim, "question": f"How did you validate this claim: {claim}"} for claim in claims if re.search(r"built|designed|architect|led|launched|owned|developed", claim, re.IGNORECASE)]
    return {"agent": "hiring-manager", "credibility": "review-needed" if questions else "low-signal", "questions": questions[:8], "hard_requirements": [r["term"] for r in jd_intelligence(jd)["requirements"] if r["hard"]]}


def evidence(cv: str) -> dict:
    claims = [line.strip(" -*•") for line in str(cv).splitlines() if re.match(r"^\s*[-*•]", line)]
    rows = [{"id": f"E{index}", "claim": claim, "has_evidence": bool(re.search(r"\d|%|tests?|users?|records?|github|https?://", claim, re.IGNORECASE)), "source_span": f"resume bullet {index}"} for index, claim in enumerate(claims, 1)]
    return {"agent": "evidence-achievement", "claims": rows, "source_of_truth": "candidate-provided CV and profile only"}


def career_report(cv: str, jd: str) -> dict:
    report = {"schema_version": 1, "agents": {"ats": ats(cv, jd), "jd": jd_intelligence(jd), "keywords": keywords(cv, jd), "language": language(cv), "recruiter": recruiter(cv, jd), "hiring_manager": hiring_manager(cv, jd), "evidence": evidence(cv)}}
    report["agents"]["company_alignment"] = {"agent": "company-language-alignment", "matched_vocabulary": [term for term in report["agents"]["jd"]["vocabulary"] if term in _terms(cv)][:20]}
    report["agents"]["interview_defense"] = {"agent": "interview-defense", "follow_ups": [row["claim"] for row in report["agents"]["evidence"]["claims"] if not row["has_evidence"]]}
    return report


def proposals(cv: str, jd: str, report: dict) -> list[dict]:
    changes = []
    for index, finding in enumerate(report["agents"]["language"]["findings"], 1):
        row = next((item for item in report["agents"]["evidence"]["claims"] if finding["phrase"] in item["claim"].lower()), None)
        words = row["claim"].split() if row else []
        position = next((i for i, part in enumerate(words) if part.lower() == finding["phrase"]), None)
        expected = " ".join(words[position:position + 2]) if position is not None and finding["phrase"] in WEAK and position + 1 < len(words) else (words[position] if position is not None else "")
        supported = bool(row and row["has_evidence"] and expected)
        replacement = {"helped": "Built", "worked on": "Built", "assisted": "Built", "participated in": "Contributed to", "responsible for": "Owned"}.get(finding["phrase"], "Built")
        changes.append({"id": f"C{index}", "kind": finding["type"], "expected_text": expected, "replacement_text": replacement if supported else "", "evidence_ids": [row["id"]] if supported else [], "supported": supported, "reason": finding["suggestion"]})
    for req in report["agents"]["keywords"]["rows"]:
        if not req["covered"]:
            changes.append({"id": f"C{len(changes) + 1}", "kind": "keyword-gap", "expected_text": "", "replacement_text": req["term"], "evidence_ids": [], "supported": False, "reason": "required terminology is absent; add only when candidate evidence supports it"})
    return changes
