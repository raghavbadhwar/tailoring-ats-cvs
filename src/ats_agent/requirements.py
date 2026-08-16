"""Traceable requirement extraction, matching, and hard-gate evaluation."""
from __future__ import annotations

import re
from typing import Iterable

from .evidence import EvidenceItem, EvidenceLedger

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
    "kubernetes": ("kubernetes", "k8s"),
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
    "market research": (
        "market research",
        "market analysis",
        "customer research",
    ),
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

PREFERRED_MARKERS = (
    "preferred",
    "nice to have",
    "desirable",
    "a plus",
    "advantage",
)
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

EXPERIENCE_DURATION = re.compile(
    rf"(?P<value>\d+(?:\.\d+)?|{NUMBER_PATTERN})\s*\+?\s*"
    r"(?P<unit>years?|yrs?|months?|mos?)\b"
    r"(?:\s+of)?(?:\s+(?:professional|relevant|work|industry|internship))?"
    r"\s+experience",
    re.IGNORECASE,
)
GRADE_PATTERN = re.compile(
    r"\b(?:cgpa|gpa)\s*(?:of|:|=)?\s*(?P<value>\d+(?:\.\d+)?)"
    r"(?:\s*/\s*(?P<scale>\d+(?:\.\d+)?))?",
    re.IGNORECASE,
)
TRAVEL_PATTERNS = (
    re.compile(
        r"(?:travel|travelling|traveling)[^0-9]{0,24}(?P<value>\d{1,3})%",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<value>\d{1,3})%[^.!?;\n]{0,24}"
        r"(?:travel|travelling|traveling)",
        re.IGNORECASE,
    ),
)


def _segments(text: str) -> Iterable[tuple[str, int, int]]:
    """Yield clauses without splitting decimals or dotted technology names."""

    sentinel = "\ue000"
    protected = re.sub(r"(?<=[A-Za-z0-9])\.(?=[A-Za-z0-9])", sentinel, text)
    for match in re.finditer(r"[^.!?;\n]+(?:[.!?;]|$)", protected):
        raw = match.group(0).replace(sentinel, ".")
        left_trimmed = raw.lstrip(" \t-*•")
        leading = len(raw) - len(left_trimmed)
        segment = left_trimmed.strip(" \t;*")
        if not segment:
            continue
        start = match.start() + leading
        yield segment, start, start + len(segment)


def _importance(segment: str) -> str:
    body = segment.lower()
    if any(marker in body for marker in MANDATORY_MARKERS):
        return "mandatory"
    if any(marker in body for marker in PREFERRED_MARKERS):
        return "preferred"
    return "preferred"


def _contains_alias(text: str, alias: str) -> bool:
    return (
        re.search(
            rf"(?<![a-z0-9]){re.escape(alias.lower())}(?![a-z0-9])",
            text.lower(),
        )
        is not None
    )


def _parse_number(value: str) -> float:
    return float(value) if value.replace(".", "", 1).isdigit() else float(
        NUMBER_WORDS[value.lower()]
    )


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


def _travel_percentage(text: str) -> int | None:
    for pattern in TRAVEL_PATTERNS:
        match = pattern.search(text)
        if match:
            return int(match.group("value"))
    return None


def _work_mode(text: str) -> str | None:
    body = text.lower()
    if re.search(r"\b(?:on[- ]site|in[- ]office)\b", body):
        return "on-site"
    if re.search(r"\bhybrid\b", body):
        return "hybrid"
    if re.search(r"\bremote\b", body):
        return "remote"
    return None


def extract_requirements(job_description: str) -> list[dict]:
    requirements: list[dict] = []
    seen: set[tuple[str, tuple[str, ...], int]] = set()
    for segment, start, end in _segments(job_description):
        body = segment.lower()
        importance = _importance(segment)
        skill_body = re.sub(
            r"^for the [^,]{1,120} assignment,\s*",
            "",
            body,
            count=1,
        )

        years = EXPERIENCE_DURATION.search(body) or re.search(
            rf"(?P<years>\d+|{NUMBER_PATTERN})\s*\+?\s*"
            r"(?:years?|yrs?)\b",
            body,
        )
        if years and (
            "experience" in body
            or any(marker in body for marker in MANDATORY_MARKERS)
        ):
            raw_years = years.groupdict().get("value") or years.groupdict().get(
                "years"
            )
            requirements.append(
                _record(
                    kind="experience_years",
                    text=segment,
                    terms=["professional experience"],
                    category="eligibility",
                    importance=importance,
                    start=start,
                    end=end,
                    minimum_years=_parse_number(str(raw_years)),
                )
            )

        if re.search(
            r"authori[sz]ed to work|work authori[sz]ation|right to work",
            body,
        ):
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
            r"no sponsorship|sponsorship (?:is )?"
            r"(?:not available|unavailable)|will not sponsor|cannot sponsor",
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

        grade = GRADE_PATTERN.search(body)
        if grade:
            scale = grade.group("scale")
            requirements.append(
                _record(
                    kind="minimum_grade",
                    text=segment,
                    terms=["minimum grade"],
                    category="education",
                    importance=importance,
                    start=start,
                    end=end,
                    minimum=float(grade.group("value")),
                    scale=float(scale) if scale else None,
                )
            )

        mode = _work_mode(segment)
        if mode:
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

        travel = _travel_percentage(segment)
        if travel is not None:
            if not 0 <= travel <= 100:
                raise ValueError("travel percentage must be between 0 and 100")
            requirements.append(
                _record(
                    kind="travel",
                    text=segment,
                    terms=["travel"],
                    category="eligibility",
                    importance=importance,
                    start=start,
                    end=end,
                    percentage=travel,
                )
            )

        for canonical, aliases in TERM_ALIASES.items():
            if any(_contains_alias(skill_body, alias) for alias in aliases):
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
    match = re.search(
        r"(?i:authori[sz]ed to work|right to work|work authori[sz