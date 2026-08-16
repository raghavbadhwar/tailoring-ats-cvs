"""Traceable job-requirement extraction, matching, and hard-gate evaluation."""
from __future__ import annotations

import re
from collections.abc import Iterable

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
    "not available",
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

_DURATION_RE = re.compile(
    rf"(?P<value>\d+(?:\.\d+)?|{NUMBER_PATTERN})\s*\+?\s*"
    r"(?P<unit>years?|yrs?|months?|mos?)\b",
    re.IGNORECASE,
)
_GRADE_RE = re.compile(
    r"\b(?P<kind>cgpa|gpa)\b\s*(?:of|:|>=|at\s+least)?\s*"
    r"(?P<value>\d+(?:\.\d+)?)"
    r"(?:\s*/\s*(?P<scale>\d+(?:\.\d+)?))?",
    re.IGNORECASE,
)
_TRAVEL_PATTERNS = (
    re.compile(
        r"(?:travel|travelling|traveling)[^0-9]{0,24}(?P<value>\d{1,3})\s*%",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<value>\d{1,3})\s*%[^.!?;\n]{0,24}"
        r"(?:travel|travelling|traveling)",
        re.IGNORECASE,
    ),
)
_WORK_MODE_PATTERNS: dict[str, re.Pattern[str]] = {
    "on-site": re.compile(r"\b(?:on[- ]site|in[- ]office)\b", re.IGNORECASE),
    "hybrid": re.compile(r"\bhybrid\b", re.IGNORECASE),
    "remote": re.compile(r"\bremote\b", re.IGNORECASE),
}


def _is_decimal_point(text: str, index: int) -> bool:
    return (
        text[index] == "."
        and index > 0
        and index + 1 < len(text)
        and text[index - 1].isdigit()
        and text[index + 1].isdigit()
    )


def _is_abbreviation_point(text: str, index: int) -> bool:
    if text[index] != "." or index == 0 or index + 1 >= len(text):
        return False
    previous = text[index - 1]
    following = text[index + 1]
    return previous.isalpha() and following.isalpha()


def _segments(text: str) -> Iterable[tuple[str, int, int]]:
    """Yield clause-level spans while preserving decimals and abbreviations."""

    start = 0
    for index, character in enumerate(text):
        if character not in ".!?;\n":
            continue
        if _is_decimal_point(text, index) or _is_abbreviation_point(text, index):
            continue
        raw = text[start : index + 1]
        leading = len(raw) - len(raw.lstrip(" \t-*•"))
        segment = raw.strip(" \t-*•")
        if segment:
            yield segment, start + leading, index + 1
        start = index + 1
    if start < len(text):
        raw = text[start:]
        leading = len(raw) - len(raw.lstrip(" \t-*•"))
        segment = raw.strip(" \t-*•")
        if segment:
            yield segment, start + leading, len(text)


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
    if value.replace(".", "", 1).isdigit():
        return float(value)
    return float(NUMBER_WORDS[value.lower()])


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


def _experience_requirement(segment: str) -> tuple[int, float] | None:
    body = segment.lower()
    if "experience" not in body:
        return None
    match = _DURATION_RE.search(body)
    if match is None:
        return None
    value = _parse_number(match.group("value"))
    unit = match.group("unit").lower()
    months = round(value * 12) if unit.startswith(("year", "yr")) else round(value)
    return months, months / 12


def _extract_country(segment: str) -> str | None:
    patterns = (
        r"(?:authori[sz]ed|eligible)\s+to\s+work\s+in\s+"
        r"(?P<country>[A-Za-z][A-Za-z .'-]{1,40}?)"
        r"(?=\s+(?:without|with|and|or|for)\b|[.;,]|$)",
        r"(?:right|permission)\s+to\s+work\s+in\s+"
        r"(?P<country>[A-Za-z][A-Za-z .'-]{1,40}?)"
        r"(?=\s+(?:without|with|and|or|for)\b|[.;,]|$)",
        r"work\s+authori[sz]ation\s+(?:for|in)\s+"
        r"(?P<country>[A-Za-z][A-Za-z .'-]{1,40}?)"
        r"(?=\s+(?:without|with|and|or|for)\b|[.;,]|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, segment, re.IGNORECASE)
        if match:
            return match.group("country").strip(" .")
    return None


def _normalize_degree(value: str) -> str:
    compact = re.sub(r"[.\s]", "", value.lower())
    if compact.startswith("bachelor") or compact in {"btech", "bcom", "bsc", "ba"}:
        return "bachelor"
    if compact.startswith("master") or compact in {"mba", "mcom", "msc", "ma"}:
        return "master"
    return compact


def _term_category(term: str) -> str:
    technical = {
        "python",
        "typescript",
        "javascript",
        "sql",
        "react",
        "next.js",
        "postgres",
        "supabase",
        "api",
        "excel",
        "power bi",
        "tableau",
        "git",
        "docker",
        "aws",
        "azure",
        "gcp",
        "testing",
        "retrieval-augmented generation",
    }
    return "technical" if term in technical else "capability"


def _travel_percentage(segment: str) -> int | None:
    for pattern in _TRAVEL_PATTERNS:
        match = pattern.search(segment)
        if match is None:
            continue
        percentage = int(match.group("value"))
        if not 0 <= percentage <= 100:
            raise ValueError("travel percentage must be between 0 and 100")
        return percentage
    return None


def _work_modes(text: str) -> list[str]:
    return [
        mode
        for mode, pattern in _WORK_MODE_PATTERNS.items()
        if pattern.search(text)
    ]


def extract_requirements(job_description: str) -> list[dict]:
    requirements: list[dict] = []
    seen: set[tuple[str, tuple[str, ...], int]] = set()
    for segment, start, end in _segments(job_description):
        body = segment.lower()
        importance = _importance(segment)

        experience = _experience_requirement(segment)
        if experience is not None:
            minimum_months, minimum_years = experience
            requirements.append(
                _record(
                    kind="experience_years",
                    text=segment,
                    terms=["professional experience"],
                    category="eligibility",
                    importance=importance,
                    start=start,
                    end=end,
                    minimum_months=minimum_months,
                    minimum_years=minimum_years,
                )
            )

        if re.search(
            r"authori[sz]ed to work|work authori[sz]ation|right to work|"
            r"eligible to work|permission to work",
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
            r"no sponsorship|sponsorship (?:is )?(?:not available|unavailable)|"
            r"will not sponsor|cannot sponsor|must not require sponsorship|"
            r"without sponsorship",
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

        grade = _GRADE_RE.search(segment)
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
                    grade_kind=grade.group("kind").lower(),
                    scale=float(scale) if scale else None,
                )
            )

        modes = _work_modes(segment)
        if modes:
            requirements.append(
                _record(
                    kind="work_mode",
                    text=segment,
                    terms=modes,
                    category="eligibility",
                    importance=importance,
                    start=start,
                    end=end,
                    value=modes[0],
                    allowed_values=modes,
                )
            )

        travel = _travel_percentage(segment)
        if travel is not None:
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


def _direct_match(term: str, evidence_text: str) -> bool:
    return _contains_alias(evidence_text, term)


def _alias_match(term: str, evidence_text: str) -> bool:
    return any(
        _contains_alias(evidence_text, alias)
        for alias in TERM_ALIASES.get(term, (term,))
    )


def _token_similarity(left: str, right: str) -> float:
    stop = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "into",
        "experience",
        "required",
    }
    left_tokens = {
        token
        for token in re.findall(r"[a-z0-9+#.]+", left.lower())
        if token not in stop
    }
    right_tokens = {
        token
        for token in re.findall(r"[a-z0-9+#.]+", right.lower())
        if token not in stop
    }
    return (
        len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
        if left_tokens and right_tokens
        else 0.0
    )


def map_requirements(
    requirements: Iterable[dict],
    ledger: EvidenceLedger,
) -> list[dict]:
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
                score = _token_similarity(requirement["text"], item.text)
                if score >= 0.45:
                    transferable.append((score, item.id))
        if direct:
            coverage = "direct"
            evidence_ids = direct
            confidence = "high"
        elif transferable:
            coverage = "transferable"
            evidence_ids = [
                item_id
                for _, item_id in sorted(transferable, reverse=True)[:3]
            ]
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
                    else "Candidate evidence contains a recognized equivalent or "
                    "closely related supported description."
                    if coverage == "transferable"
                    else "No candidate evidence supports this requirement."
                ),
            }
        )
    return mappings


def _duration_months(text: str) -> int | None:
    if not re.search(
        r"\b(?:experience|internship|employment|worked|professional|industry)\b",
        text,
        re.IGNORECASE,
    ):
        return None
    total = 0
    found = False
    for match in _DURATION_RE.finditer(text):
        value = _parse_number(match.group("value"))
        unit = match.group("unit").lower()
        total += round(value * 12) if unit.startswith(("year", "yr")) else round(value)
        found = True
    return total if found else None


def _candidate_experience(ledger: EvidenceLedger) -> tuple[int | None, list[str]]:
    durations: list[int] = []
    evidence_ids: list[str] = []
    for item in ledger.items:
        months = _duration_months(item.text)
        if months is None:
            continue
        durations.append(months)
        evidence_ids.append(item.id)
    return (sum(durations), evidence_ids) if durations else (None, [])


def _graduation_evidence(ledger: EvidenceLedger) -> tuple[set[int], list[str]]:
    years: set[int] = set()
    evidence_ids: list[str] = []
    context = re.compile(
        r"\b(?:expected|graduat(?:e|ing|ion)|class of|batch|"
        r"bachelor|master|b\.?\s*(?:tech|com|sc|a)|"
        r"m\.?\s*(?:ba|com|sc|a)|mba|degree)\b",
        re.IGNORECASE,
    )
    for item in ledger.items:
        if not context.search(item.text):
            continue
        item_years = {
            int(value) for value in re.findall(r"\b(20\d{2})\b", item.text)
        }
        if item_years:
            years.update(item_years)
            evidence_ids.append(item.id)
    return years, evidence_ids


def _degree_evidence(ledger: EvidenceLedger) -> tuple[set[str], list[str]]:
    levels: set[str] = set()
    evidence_ids: list[str] = []
    for item in ledger.items:
        body = item.text
        matched = False
        if re.search(
            r"\b(?:bachelor|b\.?\s*(?:tech|com|sc|a))\b",
            body,
            re.IGNORECASE,
        ):
            levels.add("bachelor")
            matched = True
        if re.search(
            r"\b(?:master|m\.?\s*(?:ba|com|sc|a)|mba)\b",
            body,
            re.IGNORECASE,
        ):
            levels.add("master")
            matched = True
        if matched:
            evidence_ids.append(item.id)
    return levels, evidence_ids


def _authorization_status(
    requirement: dict,
    ledger: EvidenceLedger,
) -> tuple[str, list[str]]:
    country = str(requirement.get("country") or "").strip()
    positive: list[str] = []
    negative: list[str] = []
    for item in ledger.items:
        body = item.text.lower()
        country_ok = not country or country.lower() in body
        if country_ok and re.search(
            r"\b(?:authori[sz]ed|eligible) to work|right to work|"
            r"work authori[sz]ation|permission to work\b",
            body,
        ):
            if re.search(
                r"\b(?:not|no)\s+(?:authori[sz]ed|eligible)\b",
                body,
            ):
                negative.append(item.id)
            else:
                positive.append(item.id)
    if positive:
        return "met", positive
    if negative:
        return "unmet", negative
    return "unknown", []


def _sponsorship_status(ledger: EvidenceLedger) -> tuple[str, list[str]]:
    no_need: list[str] = []
    needs: list[str] = []
    for item in ledger.items:
        body = item.text.lower()
        if re.search(
            r"\b(?:without sponsorship|do not require (?:visa )?sponsorship|"
            r"does not require (?:visa )?sponsorship|no sponsorship required)\b",
            body,
        ):
            no_need.append(item.id)
        if re.search(
            r"\b(?:require|requires|need|needs) (?:visa )?sponsorship\b",
            body,
        ):
            needs.append(item.id)
    if needs:
        return "unmet", needs
    if no_need:
        return "met", no_need
    return "unknown", []


def _work_mode_status(
    requirement: dict,
    ledger: EvidenceLedger,
) -> tuple[str, list[str]]:
    required_modes = set(
        str(mode) for mode in requirement.get("allowed_values", [])
    ) or {str(requirement.get("value") or "")}
    candidate_modes: set[str] = set()
    evidence_ids: list[str] = []
    for item in ledger.items:
        body = item.text.lower()
        if not re.search(
            r"\b(?:available|willing|open|able|can work|only)\b",
            body,
        ):
            continue
        modes = _work_modes(item.text)
        if modes:
            candidate_modes.update(modes)
            evidence_ids.append(item.id)
    if required_modes & candidate_modes:
        return "met", evidence_ids
    if candidate_modes:
        return "unmet", evidence_ids
    return "unknown", []


def _travel_status(
    requirement: dict,
    ledger: EvidenceLedger,
) -> tuple[str, list[str]]:
    required = int(requirement["percentage"])
    capacities: list[int] = []
    evidence_ids: list[str] = []
    for item in ledger.items:
        if not re.search(
            r"\b(?:travel|travelling|traveling)\b",
            item.text,
            re.IGNORECASE,
        ):
            continue
        percentage = _travel_percentage(item.text)
        if percentage is not None:
            capacities.append(percentage)
            evidence_ids.append(item.id)
    if not capacities:
        return "unknown", []
    return ("met" if max(capacities) >= required else "unmet"), evidence_ids


def _grade_status(
    requirement: dict,
    ledger: EvidenceLedger,
) -> tuple[str, list[str]]:
    minimum = float(requirement["minimum"])
    required_kind = str(requirement.get("grade_kind") or "").lower()
    grades: list[float] = []
    evidence_ids: list[str] = []
    for item in ledger.items:
        for match in _GRADE_RE.finditer(item.text):
            kind = match.group("kind").lower()
            if required_kind and kind != required_kind:
                continue
            grades.append(float(match.group("value")))
            evidence_ids.append(item.id)
    if not grades:
        return "unknown", []
    return ("met" if max(grades) >= minimum else "unmet"), evidence_ids


def evaluate_hard_gates(
    requirements: Iterable[dict],
    ledger: EvidenceLedger,
) -> list[dict]:
    candidate_months, experience_ids = _candidate_experience(ledger)
    graduation_years, graduation_ids = _graduation_evidence(ledger)
    degree_levels, degree_ids = _degree_evidence(ledger)
    degree_rank = {"bachelor": 1, "master": 2}

    results: list[dict] = []
    for requirement in requirements:
        if (
            requirement.get("importance") != "mandatory"
            or requirement.get("kind") == "skill"
        ):
            continue
        kind = requirement["kind"]
        status = "unknown"
        evidence_ids: list[str] = []
        if kind == "experience_years":
            required_months = int(
                requirement.get("minimum_months")
                or round(float(requirement["minimum_years"]) * 12)
            )
            if candidate_months is not None:
                status = "met" if candidate_months >= required_months else "unmet"
                evidence_ids = experience_ids
        elif kind == "graduation_year":
            required_year = int(requirement["year"])
            if graduation_years:
                status = "met" if required_year in graduation_years else "unmet"
                evidence_ids = graduation_ids
        elif kind == "degree":
            required = str(requirement["normalized_terms"][0])
            if degree_levels:
                required_rank = degree_rank.get(required, 99)
                highest = max(
                    degree_rank.get(level, 0) for level in degree_levels
                )
                status = "met" if highest >= required_rank else "unmet"
                evidence_ids = degree_ids
        elif kind == "work_authorization":
            status, evidence_ids = _authorization_status(requirement, ledger)
        elif kind == "sponsorship":
            status, evidence_ids = _sponsorship_status(ledger)
        elif kind == "work_mode":
            status, evidence_ids = _work_mode_status(requirement, ledger)
        elif kind == "travel":
            status, evidence_ids = _travel_status(requirement, ledger)
        elif kind == "minimum_grade":
            status, evidence_ids = _grade_status(requirement, ledger)
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
