"""Bounded public job discovery adapted from AI Job Search's MIT tools."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from html import unescape
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, field_validator

FREEHIRE_SEARCH = "https://freehire.me/api/v1/agent/jobs/search"
LINKEDIN_SEARCH = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
MAX_SEARCH_REQUESTS = 8
MAX_RESULTS = 20


class IntakeAnswers(BaseModel):
    """Search facts supplied by the candidate, never inferred from silence."""

    model_config = ConfigDict(extra="forbid")

    role_queries: list[str] = Field(min_length=1, max_length=3)
    locations: list[str] = Field(min_length=1, max_length=3)
    work_modes: list[Literal["remote", "hybrid", "in-person"]] = Field(
        min_length=1, max_length=3
    )
    work_authorization: str = Field(min_length=1, max_length=300)
    sponsorship: Literal["required", "not-required", "unknown"]
    relocation: Literal["yes", "no", "case-by-case"]
    availability: str = Field(min_length=1, max_length=200)
    deal_breakers: list[str] = Field(default_factory=list, max_length=10)
    use_linkedin_public_jobs: bool
    job_age_days: int = Field(default=14, ge=1, le=30)

    @field_validator("role_queries", "locations", "deal_breakers")
    @classmethod
    def clean_values(cls, values: list[str]) -> list[str]:
        cleaned = [re.sub(r"\s+", " ", value).strip() for value in values]
        if any(not value or len(value) > 120 for value in cleaned):
            raise ValueError("intake list values must contain 1-120 characters")
        if len({value.casefold() for value in cleaned}) != len(cleaned):
            raise ValueError("intake list values must be unique")
        return cleaned


def intake_questions(suggested_roles: list[str]) -> list[dict[str, object]]:
    """Return the stable conversational intake contract."""

    return [
        {
            "id": "role_queries",
            "question": "Which role families should I prioritize?",
            "type": "list",
            "suggestions": suggested_roles,
        },
        {
            "id": "locations",
            "question": "Which cities, countries, regions, or worldwide scope are acceptable?",
            "type": "list",
        },
        {
            "id": "work_modes",
            "question": "Which work modes are acceptable?",
            "type": "multi_select",
            "options": ["remote", "hybrid", "in-person"],
        },
        {
            "id": "work_authorization",
            "question": "Where are you authorized to work?",
            "type": "text",
        },
        {
            "id": "sponsorship",
            "question": "Do you require employer sponsorship?",
            "type": "select",
            "options": ["required", "not-required", "unknown"],
        },
        {
            "id": "relocation",
            "question": "Are you willing to relocate?",
            "type": "select",
            "options": ["yes", "no", "case-by-case"],
        },
        {
            "id": "availability",
            "question": "When are you available, including graduation timing if relevant?",
            "type": "text",
        },
        {
            "id": "deal_breakers",
            "question": "What deal-breakers should be visible when ranking?",
            "type": "list",
            "optional": True,
        },
        {
            "id": "use_linkedin_public_jobs",
            "question": (
                "Include low-volume LinkedIn public-job search for personal use? "
                "Its terms restrict automated access."
            ),
            "type": "boolean",
        },
    ]


def _request(url: str, *, accept: str, retries: int = 2) -> bytes:
    headers = {
        "User-Agent": "tailoring-ats-cvs/1.0 (+https://github.com/raghavbadhwar/tailoring-ats-cvs)",
        "Accept": accept,
    }
    for attempt in range(retries + 1):
        try:
            with urlopen(Request(url, headers=headers), timeout=15) as response:
                return response.read()
        except HTTPError as exc:
            if exc.code != 429 and exc.code < 500:
                raise ValueError(f"public job source returned HTTP {exc.code}") from exc
            if attempt == retries:
                raise ValueError(f"public job source remained unavailable: HTTP {exc.code}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            if attempt == retries:
                raise ValueError(f"public job source could not be reached: {exc}") from exc
        time.sleep(0.2 * (attempt + 1))
    raise AssertionError("bounded retry loop must return or raise")


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = re.sub(r"\s+", " ", unescape(value)).strip()
    return cleaned or None


def _freehire(query: str, mode: str, days: int, limit: int) -> list[dict[str, object]]:
    params = {
        "q": query,
        "limit": str(limit),
        "offset": "0",
        "semantic_ratio": "0",
        "include_description": "true",
        "description_format": "text",
        "posted_within_days": str(days),
        "work_mode": "onsite" if mode == "in-person" else mode,
    }
    payload = json.loads(_request(f"{FREEHIRE_SEARCH}?{urlencode(params)}", accept="application/json"))
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("freehire returned an invalid response")
    results: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        slug, title, url = _text(row.get("public_slug")), _text(row.get("title")), _text(row.get("url"))
        if not slug or not title or not url or urlsplit(url).scheme != "https":
            continue
        results.append(
            {
                "source": "freehire",
                "external_id": slug,
                "title": title,
                "company": _text(row.get("company")) or "Unknown company",
                "location": _text(row.get("location")),
                "work_mode": _text(row.get("work_mode")) or mode,
                "posted_at": _text(row.get("posted_at")),
                "job_url": url,
                "description": _text(row.get("description")),
                "provider_url": f"https://freehire.me/jobs/{slug}",
            }
        )
    return results


def _clean_html(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def _linkedin_cards(html: str, mode: str) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for chunk in re.split(r'data-entity-urn="urn:li:jobPosting:', html)[1:]:
        id_match = re.match(r"(\d+)", chunk)
        title_match = re.search(
            r'class="base-search-card__title"[^>]*>([\s\S]*?)</h3>', chunk, re.I
        )
        if not id_match or not title_match:
            continue
        external_id = id_match.group(1)
        company_match = re.search(
            r'class="base-search-card__subtitle"[^>]*>([\s\S]*?)</h4>', chunk, re.I
        )
        location_match = re.search(
            r'class="job-search-card__location"[^>]*>([\s\S]*?)</span>', chunk, re.I
        )
        date_match = re.search(
            r'class="job-search-card__listdate[^"]*"[^>]*datetime="([^"]+)"', chunk, re.I
        )
        results.append(
            {
                "source": "linkedin-public",
                "external_id": external_id,
                "title": _clean_html(title_match.group(1)),
                "company": _clean_html(company_match.group(1)) if company_match else "Unknown company",
                "location": _clean_html(location_match.group(1)) if location_match else None,
                "work_mode": mode,
                "posted_at": date_match.group(1) if date_match else None,
                "job_url": f"https://www.linkedin.com/jobs/view/{external_id}",
                "description": None,
                "provider_url": f"https://www.linkedin.com/jobs/view/{external_id}",
            }
        )
    return results


def _linkedin(query: str, location: str, mode: str, days: int) -> list[dict[str, object]]:
    work_type = {"in-person": "1", "remote": "2", "hybrid": "3"}[mode]
    params = {
        "keywords": query,
        "location": "Remote" if location.casefold() == "worldwide" and mode == "remote" else location,
        "f_TPR": f"r{days * 86400}",
        "f_WT": work_type,
        "start": "0",
    }
    html = _request(f"{LINKEDIN_SEARCH}?{urlencode(params)}", accept="text/html").decode(
        "utf-8", errors="replace"
    )
    return _linkedin_cards(html, mode)


def _location_matches(job: dict[str, object], answers: IntakeAnswers) -> bool:
    locations = [value.casefold() for value in answers.locations]
    if any(value in {"worldwide", "global", "anywhere"} for value in locations):
        return True
    if job.get("work_mode") == "remote":
        return True  # Jurisdiction remains an eligibility warning until the posting is captured.
    actual = str(job.get("location") or "").casefold()
    return not actual or any(value in actual or actual in value for value in locations)


def search_public_jobs(
    answers: IntakeAnswers,
    *,
    max_results: int = MAX_RESULTS,
) -> dict[str, object]:
    """Search bounded public sources and return normalized, deduplicated jobs."""

    jobs: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    requests_used = 0
    per_request = max(1, min(10, max_results))
    for query in answers.role_queries:
        for mode in answers.work_modes:
            if requests_used >= MAX_SEARCH_REQUESTS:
                break
            try:
                jobs.extend(_freehire(query, mode, answers.job_age_days, per_request))
            except ValueError as exc:
                failures.append({"source": "freehire", "query": query, "reason": str(exc)})
            requests_used += 1
            if not answers.use_linkedin_public_jobs:
                continue
            for location in answers.locations:
                if requests_used >= MAX_SEARCH_REQUESTS:
                    break
                try:
                    jobs.extend(_linkedin(query, location, mode, answers.job_age_days))
                except ValueError as exc:
                    failures.append({"source": "linkedin-public", "query": query, "reason": str(exc)})
                requests_used += 1

    deduplicated: list[dict[str, object]] = []
    seen: set[str] = set()
    for job in jobs:
        key = str(job["job_url"]).split("?", 1)[0].rstrip("/").casefold()
        if key in seen or not _location_matches(job, answers):
            continue
        seen.add(key)
        if job.get("work_mode") == "remote":
            job["eligibility_note"] = "Remote jurisdiction must be verified from the captured posting."
        deduplicated.append(job)
        if len(deduplicated) >= max_results:
            break
    return {
        "status": "search_complete" if deduplicated else "blocked",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "request_count": requests_used,
        "jobs": deduplicated,
        "failures": failures,
    }
