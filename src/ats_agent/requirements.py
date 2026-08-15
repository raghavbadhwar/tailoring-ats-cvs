"""Traceable job-requirement extraction and evidence matching."""
from __future__ import annotations

import re
from typing import Iterable

from .evidence import EvidenceLedger

TERM_ALIASES: dict[str, tuple[str, ...]] = {
    "python": ("python",),
    "typescript": ("typescript", "type script"),
    "javascript": ("javascript", "java script"),
    "sql": ("sql", "structured query language"),
    "react": ("react", "react.js", "reactjs"),
    "next.js": ("next.js", "nextjs", "next js"),
    "postgres": ("postgres", "postgresql"),
    "supabase": ("supabase",),
    "api": ("api", "apis", "application programming interface"),
    "workflow automation": (
        "workflow automation",
        "automated workflow",
        "automated workflows",
        "automating workflows",
        "workflow system",
        "workflow systems",
        "automated order workflows",
        "process automation",
    ),
    "ai agents": ("ai agents", "ai agent", "agentic ai", "agentic workflows", "multi-agent"),
    "human-in-the-loop": (
        "human-in-the-loop",
        "human in the loop",
        "approval-first",
        "approval gated",
        "approval-gated",
        "human approval",
    ),
    "product requirements": ("product requirements", "prd", "requirements document", "product specification"),
    "market research": ("market research", "market analysis", "customer research"),
    "market sizing": ("market sizing", "tam", "sam", "som"),
    "procurement": ("procurement", "tender", "tenders", "rfq", "sourcing"),
    "financial analysis": ("financial analysis", "financial modelling", "financial modeling", "unit economics"),
    "testing": ("testing", "tests", "test suite", "end-to-end", "e2e"),
}

MANDATORY_MARKERS = (
    "required",
    "must",
    "mandatory",
    "need ",
    "needs ",
    "minimum",
    "no sponsorship",
    "will not sponsor",
)
PREFERRED_MARKERS = ("preferred", "nice to have", "desirable", "a plus")


def _segments(text: str) -> Iterable[tuple[str, int, int]]:
    for match in re.finditer(r"[^.!?\n]+(?:[.!?]|$)", text):
        segment = match.group(0).strip()
        if segment:
            yield segment, match.start(), match.end()


def _importance(segment: str) -> str:
    body = segment.lower()
    if any(marker in body for marker in MANDATORY_MARKERS):
        return "mandatory"
    if any(marker in body for marker in PREFERRED_MARKERS):
        return "preferred"
    return "preferred"


def _record(
    *,
    kind: str,
    text: str,
    terms: list[str],
    category: str,
    importance: str,
    start: int,
    end: int,
    **extra: object,
) -> dict:
    return {
        "kind": kind,
        "text": text,
        "normalized_terms": terms,
        "category": category,
        "importance": importance,
        "source_span": {"start": start, "end": end},
        "confidence": "high",
        **extra,
    }


def extract_requirements(job_description: str) -> list[dict]:
    requirements: list[dict] = []
    seen: set[tuple[str, tuple[str, ...], int]] = set()
    for segment, start, end in _segments(job_description):
        body = segment.lower()
        importance = _importance(segment)

        years = re.search(r"(?:minimum\s+of\s+|at\s+least\s+|need(?:s)?\s+)?(\d+)\s*\+?\s*(?:years?|yrs?)", body)
        if years:
            requirements.append(
                _record(
                    kind="experience_years",
                    text=segment,
                    terms=["professional experience"],
                    category="eligibility",
                    importance="mandatory" if importance == "mandatory" or "experience" in body else importance,
                    start=start,
                    end=end,
                    minimum_years=int(years.group(1)),
                )
            )

        if re.search(r"authori[sz]ed to work|work authori[sz]ation|right to work", body):
            requirements.append(
                _record(
                    kind="work_authorization",
                    text=segment,
                    terms=["work authorization"],
                    category="eligibility",
                    importance="mandatory",
                    start=start,
                    end=end,
                )
            )

        if re.search(r"no sponsorship|sponsorship (?:is )?(?:not available|unavailable)|will not sponsor|cannot sponsor", body):
            requirements.append(
                _record(
                    kind="sponsorship",
                    text=segment,
                    terms=["sponsorship"],
                    category="eligibility",
                    importance="mandatory",
                    start=start,
                    end=end,
                    value="unavailable",
                )
            )

        graduation = re.search(r"(?:graduat(?:e|ing)|class of)[^0-9]{0,24}(20\d{2})", body)
        if graduation:
            requirements.append(
                _record(
                    kind="graduation_year",
                    text=segment,
                    terms=["graduation year"],
                    category="eligibility",
                    importance=importance,
                    start=start,
                    end=end,
                    year=int(graduation.group(1)),
                )
            )

        degree = re.search(r"\b(bachelor(?:'s)?|master(?:'s)?|b\.?(?:tech|com|sc)|m\.?(?:ba|com|sc))\b", body)
        if degree:
            requirements.append(
                _record(
                    kind="degree",
                    text=segment,
                    terms=[degree.group(1).replace(".", "")],
                    category="education",
                    importance=importance,
                    start=start,
                    end=end,
                )
            )

        for canonical, aliases in TERM_ALIASES.items():
            if any(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", body) for alias in aliases):
                key = ("skill", (canonical,), start)
                if key in seen:
                    continue
                seen.add(key)
                requirements.append(
                    _record(
                        kind="skill",
                        text=segment,
                        terms=[canonical],
                        category="technical" if canonical in {"python", "typescript", "javascript", "sql", "react", "next.js", "postgres", "supabase", "api", "testing"} else "capability",
                        importance=importance,
                        start=start,
                        end=end,
                    )
                )

    for index, requirement in enumerate(requirements, 1):
        requirement["id"] = f"R{index}"
    return requirements


def _direct_match(term: str, evidence_text: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", evidence_text.lower()) is not None


def _alias_match(term: str, evidence_text: str) -> bool:
    body = evidence_text.lower()
    return any(alias in body for alias in TERM_ALIASES.get(term, (term,)))


def map_requirements(requirements: Iterable[dict], ledger: EvidenceLedger) -> list[dict]:
    mappings: list[dict] = []
    for requirement in requirements:
        terms = list(requirement.get("normalized_terms", []))
        direct: list[str] = []
        transferable: list[str] = []
        for item in ledger.items:
            if any(_direct_match(term, item.text) for term in terms):
                direct.append(item.id)
            elif any(_alias_match(term, item.text) for term in terms):
                transferable.append(item.id)
        if direct:
            coverage = "direct"
            evidence_ids = direct
            confidence = "high"
        elif transferable:
            coverage = "transferable"
            evidence_ids = transferable
            confidence = "medium"
        else:
            coverage = "unsupported"
            evidence_ids = []
            confidence = "high"
        mappings.append(
            {
                "requirement_id": requirement["id"],
                "kind": requirement["kind"],
                "normalized_terms": terms,
                "importance": requirement["importance"],
                "coverage": coverage,
                "confidence": confidence,
                "evidence_ids": evidence_ids,
                "explanation": (
                    "Exact candidate evidence contains the requirement terminology."
                    if coverage == "direct"
                    else "Candidate evidence contains a recognized equivalent."
                    if coverage == "transferable"
                    else "No candidate evidence supports this requirement."
                ),
            }
        )
    return mappings
