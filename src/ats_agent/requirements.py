"""Traceable requirement extraction, matching, and hard-gate evaluation."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable

from .evidence import EvidenceItem, EvidenceLedger

_DEGREE_TERMS = frozenset({"bachelor", "master"})

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
    "aws": ("aws", "amazon web services", "redshift"),
    "azure": ("azure", "microsoft azure"),
    "gcp": ("gcp", "google cloud platform", "bigquery"),
    "bachelor": (
        "bachelor",
        "bachelor's",
        "b.com",
        "bcom",
        "b.tech",
        "btech",
        "b.sc",
        "bsc",
        "bba",
        "bbm",
        "undergraduate degree",
    ),
    "master": (
        "master",
        "master's",
        "m.com",
        "mcom",
        "m.tech",
        "mtech",
        "m.sc",
        "msc",
        "mba",
        "postgraduate degree",
    ),
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
    "tool use": ("tool use", "tool-use", "using tools"),
    "knowledge integration": ("knowledge integration", "sop integration", "sops"),
    "conversation strategy": ("conversation strategy", "conversation design"),
    "evaluation design": ("evaluation design", "evaluation framework"),
    "a/b testing": (
        "a/b testing",
        "a/b test",
        "a/b tests",
        "ab testing",
        "a b testing",
        "split testing",
        "split test",
        "experimentation",
    ),
    "user research": ("user research", "usability research"),
    "usability": ("usability", "user experience"),
    "roadmap": ("roadmap", "product roadmap"),
    "backlog": ("backlog", "product backlog"),
    "proof of concept": ("proof of concept", "poc"),
    "prototyping": ("prototyping", "prototype"),
    "scaling": ("scaling", "scale-up", "scale up"),
    "data annotation": ("data annotation", "annotating data"),
    "golden datasets": ("golden datasets", "golden dataset"),
    "ai response quality": ("ai response quality", "response quality"),
    "user feedback": ("user feedback", "customer feedback"),
    "root cause analysis": ("root cause analysis", "rca"),
    "issue tracking": ("issue tracking", "issue tracker"),
    "dashboards": ("dashboards", "dashboard"),
    "audits": ("audits", "audit"),
    "product analytics": ("product analytics",),
    "statistics": ("statistics", "statistical analysis"),
    "fintech": ("fintech", "financial technology"),
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
NEGATED_REQUIREMENT = re.compile(
    r"\b(?:not required|do(?:es)? not need|need not|"
    r"no [^.!?;\n]{0,50} required)\b",
    re.IGNORECASE,
)
MANDATORY_SECTION = re.compile(
    r"^(?:requirements?(?:\s*[(:].*)?|qualifications?|basic qualifications?|"
    r"minimum qualifications?|required qualifications?|must[- ]haves?|"
    r"what (?:you(?:'|’)ll need|we(?:'|’)re looking for))\s*[):]*$",
    re.IGNORECASE,
)
PREFERRED_SECTION = re.compile(
    r"^(?:preferred qualifications?|nice to haves?|bonus points?)\s*:?$",
    re.IGNORECASE,
)
NON_REQUIREMENT_SECTION = re.compile(
    r"^(?:responsibilities|what (?:you(?:'|’)ll do|you will do)|"
    r"about (?:the role|us)|benefits|perks)\s*:?$",
    re.IGNORECASE,
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
    r"(?:\s*\(?\s*(?:/|out\s+of|on\s+(?:a\s+)?(?:scale\s+of\s+)?)\s*"
    r"(?P<scale>\d+(?:\.\d+)?)(?:\s*(?:-?\s*point\s+)?scale)?\s*\)?)?",
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
PROFESSIONAL_CREDENTIAL = re.compile(
    r"\b(?:(?:qualified|inter|final)\s+ca\b|"
    r"ca\s+(?:inter|final|articleship)\b|ipcc\b|"
    r"cfa\b|cpa\b|acca\b|cma\b|"
    r"company\s+secretary\b|chartered\s+accountan(?:t|cy)\b)",
    re.IGNORECASE,
)
EXCLUSION_MARKER = re.compile(
    r"(?:need not apply|needn't apply|not eligible|not be considered|"
    r"should not apply|will not be considered|must not (?:be|apply)|"
    r"are excluded|should not be)\b",
    re.IGNORECASE,
)
ENROLLMENT_TERM = re.compile(
    r"(?:(?:currently\s+)?(?:enrolled|pursuing|studying|registered)|"
    r"full[- ]time\s+(?:education|studies|degree|programme|program|course)|"
    r"return(?:ing)?\s+to\s+(?:school|college|full[- ]time))",
    re.IGNORECASE,
)
CONSTRAINT_REMOTE_ONLY = re.compile(
    r"remote[\s-]*only|only\s+remote|"
    r"\bno\s+(?:on[- ]?site|in[- ]office|relocation)\b|"
    r"\bnot\s+(?:on[- ]?site|willing to relocate)\b",
    re.IGNORECASE,
)


def _segments(text: str) -> Iterable[tuple[str, int, int]]:
    """Yield sentence, bullet, and semicolon clauses with local spans.

    Newlines terminate bullets and headings without requiring punctuation.
    Periods between digits remain part of decimal values such as ``8.5``.
    """

    start_offset = 0
    for index, character in enumerate(text):
        decimal_point = (
            character == "."
            and index > 0
            and index + 1 < len(text)
            and text[index - 1].isdigit()
            and text[index + 1].isdigit()
        )
        if character not in ".!?;\n" or decimal_point:
            continue
        end_offset = index if character == "\n" else index + 1
        raw = text[start_offset:end_offset]
        left_trimmed = raw.lstrip(" \t-*•")
        leading = len(raw) - len(left_trimmed)
        segment = left_trimmed.strip(" \t;*")
        if segment:
            start = start_offset + leading
            yield segment, start, start + len(segment)
        start_offset = index + 1

    raw = text[start_offset:]
    left_trimmed = raw.lstrip(" \t-*•")
    leading = len(raw) - len(left_trimmed)
    segment = left_trimmed.strip(" \t;*")
    if segment:
        start = start_offset + leading
        yield segment, start, start + len(segment)


def _importance(segment: str, default: str = "preferred") -> str:
    body = segment.lower()
    if NEGATED_REQUIREMENT.search(body):
        return "preferred"
    if any(marker in body for marker in PREFERRED_MARKERS):
        return "preferred"
    if any(marker in body for marker in MANDATORY_MARKERS):
        return "mandatory"
    return default


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
    section_importance = "preferred"
    for segment, start, end in _segments(job_description):
        if MANDATORY_SECTION.fullmatch(segment.strip()):
            section_importance = "mandatory"
            continue
        if (
            PREFERRED_SECTION.fullmatch(segment.strip())
            or NON_REQUIREMENT_SECTION.fullmatch(segment.strip())
        ):
            section_importance = "preferred"
            continue
        body = segment.lower()
        importance = _importance(segment, section_importance)

        years = re.search(
            r"(?P<years>\d+)\s*(?:-|–|—|to)\s*\d+\s*"
            r"(?:years?|yrs?)\b",
            body,
        ) or EXPERIENCE_DURATION.search(body) or re.search(
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
                    importance=(
                        "mandatory"
                        if re.match(r"experience\s*:", body)
                        else importance
                    ),
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
            r"\b(bachelor(?:['’]s)?(?:\s+degree)?|"
            r"master(?:['’]s|\s+degree)|undergraduate degree|"
            r"postgraduate degree|b\.?\s*(?:tech|com|sc|a)|bba|bbm|"
            r"m\.?\s*(?:ba|com|sc|tech|a)|mba)\b",
            body,
        )
        if degree and not NEGATED_REQUIREMENT.search(body):
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
                    importance=(
                        "preferred"
                        if any(marker in body for marker in PREFERRED_MARKERS)
                        else "mandatory"
                    ),
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

        if PROFESSIONAL_CREDENTIAL.search(body) and not NEGATED_REQUIREMENT.search(
            body
        ):
            requirements.append(
                _record(
                    kind="professional_credential",
                    text=segment,
                    terms=["professional credential"],
                    category="eligibility",
                    importance=importance,
                    start=start,
                    end=end,
                )
            )

        if EXCLUSION_MARKER.search(segment) and ENROLLMENT_TERM.search(segment):
            requirements.append(
                _record(
                    kind="enrollment",
                    text=segment,
                    terms=["enrollment status"],
                    category="eligibility",
                    importance="mandatory",
                    start=start,
                    end=end,
                )
            )

        duration = re.search(
            r"\b\d+\s*(?:-|to)\s*\d+\s*months?|\b\d+\s*months?",
            segment,
            re.IGNORECASE,
        )
        if duration and re.search(r"\b(?:available|availability)\b", segment, re.IGNORECASE):
            requirements.append(
                _record(
                    kind="availability",
                    text=segment,
                    terms=["availability"],
                    category="availability",
                    importance=importance,
                    start=start,
                    end=end,
                    duration=duration.group(0),
                )
            )

        matched: list[tuple[str, str]] = []
        for canonical, aliases in TERM_ALIASES.items():
            if canonical in _DEGREE_TERMS:
                continue
            for alias in aliases:
                if _contains_alias(body, alias):
                    matched.append((canonical, alias))
                    break
        # Prefer specific aliases ("a/b tests") over generic ones ("tests")
        # when both match the same segment.
        for canonical, alias in matched:
            dominated = any(
                other_canonical != canonical
                and len(other_alias) > len(alias)
                and re.search(
                    rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])",
                    other_alias,
                )
                for other_canonical, other_alias in matched
            )
            if dominated:
                continue
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


def merge_requirements(
    extracted: Iterable[dict],
    sourced_additions: Iterable[dict],
) -> list[dict]:
    """Merge captured-source dossier clauses without inventing requirements."""

    merged = [dict(item) for item in extracted]
    seen = {
        " ".join(re.findall(r"[a-z0-9]+", str(item.get("text", "")).lower())): item
        for item in merged
    }
    for addition in sourced_additions:
        text = str(addition.get("text") or "")
        key = " ".join(re.findall(r"[a-z0-9]+", text.lower()))
        if not key:
            continue
        if key in seen:
            seen[key].update(
                {
                    field: value
                    for field, value in addition.items()
                    if field
                    in {
                        "source_url",
                        "capture_sha256",
                        "source_type",
                        "source_excerpt",
                        "dossier_source",
                    }
                }
            )
            continue
        merged.append(dict(addition))
        seen[key] = merged[-1]
    for index, requirement in enumerate(merged, 1):
        requirement["id"] = f"R{index}"
    return merged


def parse_constraints(text: str) -> list[dict]:
    """Parse candidate-side search constraints into mandatory gate records.

    Constraints flow in the opposite direction of job requirements: they are
    evaluated against the job description itself, not against candidate
    evidence. A remote-only constraint, for example, rejects roles whose own
    mandatory work mode is on-site or hybrid.
    """

    constraints: list[dict] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        stripped = raw.strip().lstrip("-*•").strip()
        if not stripped or stripped.startswith("#"):
            continue
        body = stripped.lower()
        value: str | None = None
        if CONSTRAINT_REMOTE_ONLY.search(body):
            value = "remote"
        elif re.search(r"\bopen to\s+(?:hybrid|on[- ]?site)\b", body):
            value = None
        if value and value not in seen:
            seen.add(value)
            constraints.append(
                _record(
                    kind="work_mode_constraint",
                    text=stripped,
                    terms=["work mode constraint"],
                    category="eligibility",
                    importance="mandatory",
                    start=0,
                    end=len(stripped),
                    value=value,
                )
            )
    return constraints


def _extract_country(segment: str) -> str | None:
    match = re.search(
        r"(?i:authori[sz]ed to work|right to work|work authori[sz]ation)"
        r"(?:\s+in)?\s+"
        r"(?P<country>[A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*){0,3})",
        segment,
    )
    return match.group("country").strip(" .") if match else None


def _normalize_degree(value: str) -> str:
    compact = re.sub(r"[.\s]", "", value.lower())
    if compact.startswith("bachelor") or compact in {
        "btech",
        "bcom",
        "bsc",
        "ba",
        "undergraduatedegree",
    }:
        return "bachelor"
    if compact.startswith("master") or compact in {
        "mba",
        "mcom",
        "msc",
        "ma",
        "postgraduatedegree",
    }:
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
        "kubernetes",
        "aws",
        "azure",
        "gcp",
        "testing",
        "retrieval-augmented generation",
        "a/b testing",
        "data annotation",
        "golden datasets",
        "statistics",
    }
    return "technical" if term in technical else "capability"


def _ambiguous_alias_usage(
    term: str,
    alias: str,
    evidence_text: str,
) -> bool:
    """Reject common-language uses of otherwise valid technical aliases."""

    body = evidence_text.casefold()
    normalized_alias = alias.casefold()
    if term == "react" and normalized_alias == "react":
        return (
            re.search(
                r"\breact(?:ed|ing|s)?\s+"
                r"(?:quickly|rapidly|promptly|appropriately|to|when|under|"
                r"against|on|after|before)\b",
                body,
            )
            is not None
        )
    if (
        term == "retrieval-augmented generation"
        and normalized_alias == "rag"
    ):
        return (
            re.search(r"\bred[- ]amber[- ]green\b", body) is not None
            or re.search(
                r"\brag\s+(?:status|rating|indicator|report|dashboard|"
                r"colour|color|traffic[- ]light)\b",
                body,
            )
            is not None
        )
    return False


_NEGATION_BEFORE = re.compile(
    r"(?:\b(?:no|not|never|without|zero|except|lack(?:ing)?)\b|n't)"
    r"[^.;]{0,32}$",
    re.IGNORECASE,
)


def _unnegated_alias_positions(
    evidence_text: str,
    alias: str,
) -> bool:
    """True when the alias occurs at least once outside a negation scope.

    Disavowal lines such as ``No A/B testing experience`` or
    ``no AWS/GCP/Azure`` mention skills precisely because the candidate
    lacks them; treating those mentions as coverage would fabricate
    qualifications from explicit non-evidence.
    """

    pattern = re.compile(rf"(?<![a-z0-9]){re.escape(alias.lower())}(?![a-z0-9])")
    body = evidence_text.lower()
    for match in pattern.finditer(body):
        window = body[max(0, match.start() - 36):match.start()]
        if not _NEGATION_BEFORE.search(window):
            return True
    return False


def _matches_alias(term: str, alias: str, evidence_text: str) -> bool:
    return _unnegated_alias_positions(evidence_text, alias) and not _ambiguous_alias_usage(
        term,
        alias,
        evidence_text,
    )


def _direct_match(term: str, evidence_text: str) -> bool:
    return _matches_alias(term, term, evidence_text)


def _alias_match(term: str, evidence_text: str) -> bool:
    return any(
        _matches_alias(term, alias, evidence_text)
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
                    else (
                        "Candidate evidence contains a recognized equivalent or "
                        "closely related supported description."
                        if coverage == "transferable"
                        else "No candidate evidence supports this requirement."
                    )
                ),
            }
        )
    return mappings


def _experience_months(item: EvidenceItem) -> float | None:
    match = EXPERIENCE_DURATION.search(item.text)
    if not match:
        if re.search(r"\bno\s+(?:professional\s+)?experience\b", item.text, re.I):
            return 0.0
        return None
    value = _parse_number(match.group("value"))
    unit = match.group("unit").lower()
    return value * 12 if unit.startswith(("year", "yr")) else value


def _graduation_years(item: EvidenceItem) -> set[int]:
    body = item.text
    if not (
        "qualification" in item.fact_types
        or re.search(
            r"\b(?:expected|graduat(?:e|ing)|class of|degree|bachelor|master|"
            r"b\.?com|b\.?tech|mba)\b",
            body,
            re.IGNORECASE,
        )
    ):
        return set()
    return {int(value) for value in re.findall(r"\b(20\d{2})\b", body)}


def _candidate_modes(item: EvidenceItem) -> set[str]:
    modes: set[str] = set()
    body = item.text.lower()
    if re.search(r"\b(?:on[- ]site|in[- ]office)\b", body):
        modes.add("on-site")
    if re.search(r"\bhybrid\b", body):
        modes.add("hybrid")
    if re.search(r"\bremote\b", body):
        modes.add("remote")
    return modes


def _authorization_status(
    requirement: dict,
    ledger: EvidenceLedger,
) -> tuple[str, list[str]]:
    required_country = str(requirement.get("country") or "").casefold()
    relevant: list[EvidenceItem] = []
    for item in ledger.items:
        if re.search(
            r"authori[sz]ed to work|right to work|work authori[sz]ation",
            item.text,
            re.IGNORECASE,
        ):
            relevant.append(item)
    if not relevant:
        return "unknown", []
    if any(
        re.search(r"\bnot\s+authori[sz]ed to work\b", item.text, re.I)
        for item in relevant
    ):
        return "unmet", [item.id for item in relevant]
    if not required_country:
        return "met", [item.id for item in relevant]
    countries = {
        country.casefold()
        for item in relevant
        if (country := _extract_country(item.text)) is not None
    }
    if required_country in countries:
        return "met", [item.id for item in relevant]
    return ("unmet" if countries else "unknown"), [item.id for item in relevant]


def _sponsorship_status(ledger: EvidenceLedger) -> tuple[str, list[str]]:
    no_need: list[EvidenceItem] = []
    needs: list[EvidenceItem] = []
    for item in ledger.items:
        body = item.text.lower()
        if re.search(
            r"without (?:visa )?sponsorship|do(?:es)? not require "
            r"(?:visa )?sponsorship|no (?:visa )?sponsorship required",
            body,
        ):
            no_need.append(item)
        elif re.search(
            r"\brequire(?:s|d)? (?:visa )?sponsorship\b|"
            r"\bneed(?:s|ed)? (?:visa )?sponsorship\b",
            body,
        ):
            needs.append(item)
    if no_need:
        return "met", [item.id for item in no_need]
    if needs:
        return "unmet", [item.id for item in needs]
    return "unknown", []


def _work_mode_status(
    required_mode: str,
    ledger: EvidenceLedger,
) -> tuple[str, list[str]]:
    relevant = [
        (item, _candidate_modes(item))
        for item in ledger.items
        if _candidate_modes(item)
    ]
    if not relevant:
        return "unknown", []
    modes = {mode for _, item_modes in relevant for mode in item_modes}
    status = "met" if required_mode in modes else "unmet"
    return status, [item.id for item, _ in relevant]


def _travel_status(
    required_percentage: int,
    ledger: EvidenceLedger,
) -> tuple[str, list[str]]:
    relevant: list[tuple[EvidenceItem, int]] = []
    for item in ledger.items:
        if "travel" not in item.text.lower():
            continue
        percentage = _travel_percentage(item.text)
        if percentage is not None and 0 <= percentage <= 100:
            relevant.append((item, percentage))
    if not relevant:
        return "unknown", []
    capacity = max(percentage for _, percentage in relevant)
    status = "met" if capacity >= required_percentage else "unmet"
    return status, [item.id for item, _ in relevant]


def _grade_status(
    minimum: float,
    required_scale: float | None,
    ledger: EvidenceLedger,
) -> tuple[str, list[str]]:
    grades: list[tuple[EvidenceItem, float, float | None]] = []
    for item in ledger.items:
        match = GRADE_PATTERN.search(item.text)
        if match:
            scale = match.group("scale")
            grades.append(
                (
                    item,
                    float(match.group("value")),
                    float(scale) if scale else None,
                )
            )
    if not grades:
        return "unknown", []
    comparable = [
        (item, value)
        for item, value, scale in grades
        if required_scale is not None and scale == required_scale
    ]
    if not comparable:
        return "unknown", [item.id for item, _, _ in grades]
    highest = max(value for _, value in comparable)
    status = "met" if highest >= minimum else "unmet"
    return status, [item.id for item, _ in comparable]


def evaluate_hard_gates(
    requirements: Iterable[dict],
    ledger: EvidenceLedger,
) -> list[dict]:
    degree_levels: set[str] = set()
    for item in ledger.items:
        if re.search(
            r"\b(?:bachelor(?:['’]s)?(?:\s+degree)?|undergraduate degree|"
            r"b\.?\s*(?:tech|com|sc|a)|bba|bbm)\b",
            item.text,
            re.IGNORECASE,
        ):
            degree_levels.add("bachelor")
        if re.search(
            r"\b(?:master(?:['’]s|\s+degree)|postgraduate degree|"
            r"m\.?\s*(?:ba|com|sc|tech|a)|mba)\b",
            item.text,
            re.IGNORECASE,
        ):
            degree_levels.add("master")

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
            durations = [
                (item, months)
                for item in ledger.items
                if (months := _experience_months(item)) is not None
            ]
            if durations:
                candidate_months = max(months for _, months in durations)
                required_months = float(requirement["minimum_years"]) * 12
                status = (
                    "met" if candidate_months >= required_months else "unmet"
                )
                evidence_ids = [item.id for item, _ in durations]
        elif kind == "graduation_year":
            graduation_evidence = [
                (item, _graduation_years(item))
                for item in ledger.items
                if _graduation_years(item)
            ]
            years = {
                year
                for _, item_years in graduation_evidence
                for year in item_years
            }
            if years:
                status = (
                    "met" if int(requirement["year"]) in years else "unmet"
                )
                evidence_ids = [item.id for item, _ in graduation_evidence]
        elif kind == "degree":
            required = requirement["normalized_terms"][0]
            if degree_levels:
                status = "met" if required in degree_levels else "unmet"
                evidence_ids = [
                    item.id
                    for item in ledger.items
                    if "qualification" in item.fact_types
                ]
        elif kind == "work_authorization":
            status, evidence_ids = _authorization_status(requirement, ledger)
        elif kind == "sponsorship":
            status, evidence_ids = _sponsorship_status(ledger)
        elif kind == "work_mode":
            status, evidence_ids = _work_mode_status(
                str(requirement["value"]),
                ledger,
            )
        elif kind == "travel":
            status, evidence_ids = _travel_status(
                int(requirement["percentage"]),
                ledger,
            )
        elif kind == "minimum_grade":
            status, evidence_ids = _grade_status(
                float(requirement["minimum"]),
                (
                    float(requirement["scale"])
                    if requirement.get("scale") is not None
                    else None
                ),
                ledger,
            )
        elif kind == "professional_credential":
            credential_evidence = [
                item
                for item in ledger.items
                if PROFESSIONAL_CREDENTIAL.search(item.text)
            ]
            if credential_evidence:
                status = "met"
                evidence_ids = [item.id for item in credential_evidence]
            else:
                status = "unmet"
        elif kind == "enrollment":
            current_year = datetime.now().year
            enrolled_items = [
                item
                for item in ledger.items
                if any(
                    year >= current_year for year in _graduation_years(item)
                )
                or re.search(
                    r"\b(?:currently\s+(?:pursuing|enrolled|studying)|"
                    r"undergraduate|student)\b",
                    item.text,
                    re.IGNORECASE,
                )
            ]
            completed_items = [
                item
                for item in ledger.items
                if "qualification" in item.fact_types
            ]
            if enrolled_items:
                status = "unmet"
                evidence_ids = [item.id for item in enrolled_items]
            elif completed_items:
                status = "met"
                evidence_ids = [item.id for item in completed_items]
        elif kind == "work_mode_constraint":
            jd_modes = [
                str(item.get("value"))
                for item in requirements
                if item.get("kind") == "work_mode"
                and item.get("importance") == "mandatory"
            ]
            value = str(requirement["value"])
            evidence_ids = []
            if value in jd_modes:
                status = "met"
            elif jd_modes:
                status = "unmet"

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


def enforce_hard_gate_policy(
    hard_gates: Iterable[dict],
    acknowledged_hard_gate_ids: Iterable[str] = (),
) -> list[str]:
    """Fail closed on unmet gates and require explicit unknown acknowledgements."""

    gates = list(hard_gates)
    gate_ids = [str(gate.get("requirement_id") or "") for gate in gates]
    if any(not gate_id for gate_id in gate_ids):
        raise ValueError("every hard gate requires a requirement_id")
    if len(gate_ids) != len(set(gate_ids)):
        raise ValueError("hard gate requirement IDs must be unique")
    invalid_statuses = sorted(
        {
            str(gate.get("status") or "")
            for gate in gates
            if gate.get("status") not in {"met", "unmet", "unknown"}
        }
    )
    if invalid_statuses:
        raise ValueError(
            "hard gates contain invalid statuses: " + ", ".join(invalid_statuses)
        )

    unmet = [
        gate_id
        for gate_id, gate in zip(gate_ids, gates, strict=True)
        if gate["status"] == "unmet"
    ]
    if unmet:
        raise ValueError("unmet hard gates block approval: " + ", ".join(unmet))

    acknowledged = list(acknowledged_hard_gate_ids)
    if any(not isinstance(gate_id, str) or not gate_id for gate_id in acknowledged):
        raise ValueError("hard gate acknowledgements must be non-empty strings")
    if len(acknowledged) != len(set(acknowledged)):
        raise ValueError("hard gate acknowledgements must be unique")
    unknown = [
        gate_id
        for gate_id, gate in zip(gate_ids, gates, strict=True)
        if gate["status"] == "unknown"
    ]
    unexpected = sorted(set(acknowledged) - set(unknown))
    if unexpected:
        raise ValueError(
            "acknowledgements do not identify unknown hard gates: "
            + ", ".join(unexpected)
        )
    missing = [gate_id for gate_id in unknown if gate_id not in acknowledged]
    if missing:
        raise ValueError(
            "unknown hard gates require explicit acknowledgement: "
            + ", ".join(missing)
        )
    return [gate_id for gate_id in unknown if gate_id in acknowledged]
