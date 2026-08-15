"""Traceable job-requirement extraction, matching, and hard-gate evaluation."""
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
    "excel": ("excel", "spreadsheets", "google sheets"),
    "power bi": ("power bi", "powerbi"),
    "tableau": ("tableau",),
    "git": ("git", "github", "version control"),
    "docker": ("docker", "containers", "containerization"),
    "aws": ("aws", "amazon web services"),
    "azure": ("azure", "microsoft azure"),
    "gcp": ("gcp", "google cloud platform"),
    "workflow automation": (
        "workflow automation",
        "automated workflow",
        "automated workflows",
        "automating workflows",
        "workflow system",
        "workflow systems",
        "automated order workflows",
        "automated procurement workflows",
        "process automation",
    ),
    "ai agents": (
        "ai agents",
        "ai agent",
        "agentic ai",
        "agentic workflows",
        "multi-agent",
        "agent orchestration",
    ),
    "human-in-the-loop": (
        "human-in-the-loop",
        "human in the loop",
        "approval-first",
        "approval gated",
        "approval-gated",
        "human approval",
    ),
    "retrieval-augmented generation": (
        "retrieval-augmented generation",
        "retrieval augmented generation",
        "rag",
    ),
    "product requirements": (
        "product requirements",
        "prd",
        "requirements document",
        "product specification",
    ),
    "stakeholder management": (
        "stakeholder management",
        "stakeholder communication",
        "cross-functional collaboration",
    ),
    "market research": ("market research", "market analysis", "customer research"),
    "market sizing": ("market sizing", "tam", "sam", "som"),
    "procurement": ("procurement", "tender", "tenders", "rfq", "sourcing"),
    "financial analysis": (
        "financial analysis",
        "financial modelling",
        "financial modeling",
        "unit economics",
    ),
    "data analysis": ("data analysis", "analytics", "business analysis"),
    "testing": ("testing", "tests", "test suite", "end-to-end", "e2e"),
}

PREFERRED_MARKERS = ("preferred", "nice to have", "desirable", "a plus", "advantage")
MANDATORY_MARKERS = (
    "required",
    "must",
    "mandatory",
    "need ",
    "needs ",
    "minimum",
    "at least",
    "no sponsorship",
    "will not sponsor",
    "cannot sponsor",
)
NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "fifteen": 15,
}
NUMBER_PATTERN = "|".join(NUMBER_WORDS)


def _segments(text: str) -> Iterable[tuple[str, int, int]]:
    # Keep semicolon-connected eligibility conditions together while still
    # treating bullets/newlines and sentence terminators as independent spans.
    for match in re.finditer(r"[^.!?\n]+(?:[.!?]|$)", text):
        segment = match.group(0).strip(" \t-*•")
        if segment:
            yield segment, match.start(), match.end()


def _importance(segment: str) -> str:
    body = segment.lower()
    if any(marker in body for marker in PREFERRED_MARKERS):
        return "preferred"
    if any(marker in body for marker in MANDATORY_MARKERS):
        return "mandatory"
    return "preferred"


def _contains_alias(text: str, alias: str) -> bool:
    return re.search(
        rf"(?<![a-z0-9]){re.escape(alias.lower())}(?![a-z0-9])",
        text.lower(),
    ) is not None


def _parse_number(value: str) -> int:
    return int(value) if value.isdigit() else NUMBER_WORDS[value.lower()]


def _record(
    *,
    kind: str,
    text: str,
    terms: list[str],
    category: str,
    importance: str,
    start: int,
    end: int,
    confidence: str = "high",
    **extra: object,
) -> dict:
    return {
        "kind": kind,
        "text": text,
        "normalized_terms": terms,
        "category": category,
        "importance": importance,
        "source_span": {"start": start, "end": end},
        "confidence": confidence,
        **extra,
    }


def extract_requirements(job_description: str) -> list[dict]:
    requirements: list[dict] = []
    seen: set[tuple[str, tuple[str, ...], int]] = set()
    for segment, start, end in _segments(job_description):
        body = segment.lower()
        importance = _importance(segment)

        years = re.search(
            rf"(?:minimum\s+of\s+|at\s+least\s+|need(?:s)?\s+)?"
            rf"(?P<years>\d+|{NUMBER_PATTERN})\s*\+?\s*(?:years?|yrs?)"
            rf"(?:\s+of)?(?:\s+(?:professional|relevant|work|industry|internship))?\s+experience",
            body,
        ) or re.search(
            rf"(?P<years>\d+|{NUMBER_PATTERN})\s*\+?\s*(?:years?|yrs?)",
            body,
        )
        if years:
            requirements.append(
                _record(
                    kind="experience_years",
                    text=segment,
                    terms=["professional experience"],
                    category="eligibility",
                    importance=importance,
                    start=start,
                    end=end,
                    minimum_years=_parse_number(years.group("years")),
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
                    country=_extract_country(segment),
                )
            )

        if re.search(
            r"no sponsorship|sponsorship (?:is )?(?:not available|unavailable)|"
            r"will not sponsor|cannot sponsor",
            body,
        ):
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

        graduation = re.search(
            r"(?:graduat(?:e|ing)|class of)[^0-9]{0,30}(20\d{2})",
            body,
        ) or re.search(r"(20\d{2})\s+(?:graduate|graduating|batch)", body)
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

        degree = re.search(
            r"\b(bachelor(?:'s)?|master(?:'s)?|b\.?\s*(?:tech|com|sc|a)|"
            r"m\.?\s*(?:ba|com|sc|a)|mba)\b",
            body,
        )
        if degree:
            requirements.append(
                _record(
                    kind="degree",
                    text=segment,
                    terms=[_normalize_degree(degree.group(1))],
                    category="education",
                    importance=importance,
                    start=start,
                    end=end,
                )
            )

        cgpa = re.search(r"(?:cgpa|gpa)[^0-9]{0,10}(\d+(?:\.\d+)?)", body)
        if cgpa:
            requirements.append(
                _record(
                    kind="minimum_grade",
                    text=segment,
                    terms=["minimum grade"],
                    category="education",
                    importance=importance,
                    start=start,
                    end=end,
                    minimum=float(cgpa.group(1)),
                )
            )

        if re.search(r"\b(on[- ]site|in[- ]office|hybrid|remote)\b", body):
            mode = next(
                value
                for value in ("on-site", "hybrid", "remote")
                if (
                    value in body
                    or (value == "on-site" and re.search(r"on[- ]site|in[- ]office", body))
                )
            )
            requirements.append(
                _record(
                    kind="work_mode",
                    text=segment,
                    terms=[mode],
                    category="eligibility",
                    importance=importance,
                    start=start,
                    end=end,
                    value=mode,
                )
            )

        travel = (
            re.search(r"(?:travel|travelling|traveling)[^0-9]{0,15}(\d{1,3})%", body)
            or re.search(r"(\d{1,3})%[^.!?]{0,15}(?:travel|travelling|traveling)", body)
        )
        if travel:
            requirements.append(
                _record(
                    kind="travel",
                    text=segment,
                    terms=["travel"],
                    category="eligibility",
                    importance=importance,
                    start=start,
                    end=end,
                    percentage=int(travel.group(1)),
                )
            )

        for canonical, aliases in TERM_ALIASES.items():
            if any(_contains_alias(body, alias) for alias in aliases):
                key = ("skill", (canonical,), start)
                if key in seen:
                    continue
                seen.add(key)
                requirements.append(
                    _record(
                        kind="skill",
                        text=segment,
                        terms=[canonical],
                        category=_term_category(canonical),
                        importance=importance,
                        start=start,
                        end=end,
                    )
                )

    for index, requirement in enumerate(requirements, 1):
        requirement["id"] = f"R{index}"
    return requirements


def _extract_country(segment: str) -> str | None:
    match = re.search(r"(?:work|right to work)\s+in\s+([A-Z][A-Za-z .-]{2,30})", segment)
    return match.group(1).strip(" .") if match else None


def _normalize_degree(value: str) -> str:
    compact = re.sub(r"[.\s]", "", value.lower())
    if compact.startswith("bachelor") or compact in {"btech", "bcom", "bsc", "ba"}:
        return "bachelor"
    if compact.startswith("master") or compact in {"mba", "mcom", "msc", "ma"}:
        return "master"
    return compact


def _term_category(term: str) -> str:
    technical = {
        "python", "typescript", "javascript", "sql", "react", "next.js",
        "postgres", "supabase", "api", "excel", "power bi", "tableau",
        "git", "docker", "aws", "azure", "gcp", "testing",
        "retrieval-augmented generation",
    }
    return "technical" if term in technical else "capability"


def _direct_match(term: str, evidence_text: str) -> bool:
    return _contains_alias(evidence_text, term)


def _alias_match(term: str, evidence_text: str) -> bool:
    return any(_contains_alias(evidence_text, alias) for alias in TERM_ALIASES.get(term, (term,)))


def _token_similarity(left: str, right: str) -> float:
    stop = {"the", "and", "for", "with", "from", "into", "experience", "required"}
    a = {token for token in re.findall(r"[a-z0-9+#.]+", left.lower()) if token not in stop}
    b = {token for token in re.findall(r"[a-z0-9+#.]+", right.lower()) if token not in stop}
    return len(a & b) / len(a | b) if a and b else 0.0


def map_requirements(requirements: Iterable[dict], ledger: EvidenceLedger) -> list[dict]:
    mappings: list[dict] = []
    for requirement in requirements:
        terms = list(requirement.get("normalized_terms", []))
        direct: list[str] = []
        transferable: list[tuple[float, str]] = []
        for item in ledger.items:
            if any(_direct_match(term, item.text) for term in terms):
                direct.append(item.id)
            elif any(_alias_match(term, item.text) for term in terms):
                transferable.append((0.9, item.id))
            else:
                score = max((_token_similarity(requirement["text"], item.text),), default=0.0)
                if score >= 0.45:
                    transferable.append((score, item.id))
        if direct:
            coverage = "direct"
            evidence_ids = direct
            confidence = "high"
        elif transferable:
            coverage = "transferable"
            evidence_ids = [item_id for _, item_id in sorted(transferable, reverse=True)[:3]]
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
                    else "Candidate evidence contains a recognized equivalent or closely related supported description."
                    if coverage == "transferable"
                    else "No candidate evidence supports this requirement."
                ),
            }
        )
    return mappings


def evaluate_hard_gates(requirements: Iterable[dict], ledger: EvidenceLedger) -> list[dict]:
    evidence_text = "\n".join(item.text for item in ledger.items)
    years = [int(value) for value in re.findall(r"\b(\d+)\s*\+?\s*years?\b", evidence_text, re.I)]
    candidate_years = max(years, default=None)
    graduation_years = {int(value) for value in re.findall(r"\b(20\d{2})\b", evidence_text)}
    degree_levels = set()
    if re.search(r"\b(?:bachelor|b\.?\s*(?:tech|com|sc|a))\b", evidence_text, re.I):
        degree_levels.add("bachelor")
    if re.search(r"\b(?:master|m\.?\s*(?:ba|com|sc|a)|mba)\b", evidence_text, re.I):
        degree_levels.add("master")

    results: list[dict] = []
    for requirement in requirements:
        if requirement.get("importance") != "mandatory" or requirement.get("kind") == "skill":
            continue
        kind = requirement["kind"]
        status = "unknown"
        evidence_ids: list[str] = []
        if kind == "experience_years":
            minimum = int(requirement["minimum_years"])
            status = "met" if candidate_years is not None and candidate_years >= minimum else "unmet" if candidate_years is not None else "unknown"
            evidence_ids = [item.id for item in ledger.items if re.search(r"\b\d+\s*\+?\s*years?\b", item.text, re.I)]
        elif kind == "graduation_year":
            status = "met" if int(requirement["year"]) in graduation_years else "unmet" if graduation_years else "unknown"
            evidence_ids = [item.id for item in ledger.items if str(requirement["year"]) in item.text]
        elif kind == "degree":
            required = requirement["normalized_terms"][0]
            status = "met" if required in degree_levels else "unmet" if degree_levels else "unknown"
            evidence_ids = [item.id for item in ledger.items if "qualification" in item.fact_types]
        elif kind in {"work_authorization", "sponsorship", "work_mode", "travel", "minimum_grade"}:
            status = "unknown"
        results.append(
            {
                "requirement_id": requirement["id"],
                "kind": kind,
                "status": status,
                "evidence_ids": evidence_ids,
                "requirement": requirement["text"],
            }
        )
    return results
