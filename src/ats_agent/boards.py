"""Structured readers for public ATS job-board syndication APIs.

These vendors publish unauthenticated, read-only job feeds precisely so
listings can be syndicated; reading them is the ToS-clean alternative to
scraping rendered pages. Every posting is normalized into the same shape the
public job-list research export expects:

    {"id", "company", "role", "job_url", "description",
     "source": "ats_board", "provider", "fetched_at"}

Only public HTTPS GET endpoints are used. No credentials, no proxies, no
browser automation. Per-host pacing and ``Retry-After`` are honored.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any

USER_AGENT = "tailoring-ats-cvs (+https://github.com/raghavbadhwar/tailoring-ats-cvs)"
MIN_HOST_INTERVAL_SECONDS = 1.0
DEFAULT_TIMEOUT = 30.0
MAX_ATTEMPTS = 3

_last_request_at: dict[str, float] = {}


class BoardError(RuntimeError):
    """A structured board feed could not be read."""


class _TextExtractor(HTMLParser):
    _BLOCK = {"script", "style"}

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in self._BLOCK:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._BLOCK and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "tr"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data.strip():
            self._chunks.append(data)

    def text(self) -> str:
        raw = "".join(self._chunks)
        lines = [line.strip() for line in raw.splitlines()]
        return "\n".join(line for line in lines if line)


def html_to_text(html: str) -> str:
    extractor = _TextExtractor()
    try:
        extractor.feed(html)
    except Exception as exc:  # pragma: no cover - malformed HTML guard
        raise BoardError(f"unreadable HTML payload: {exc}") from exc
    return extractor.text()


def _polite_get_json(url: str) -> dict[str, Any]:
    host = re.sub(r"^https?://", "", url).split("/", 1)[0]
    for attempt in range(1, MAX_ATTEMPTS + 1):
        elapsed = time.monotonic() - _last_request_at.get(host, 0.0)
        wait = MIN_HOST_INTERVAL_SECONDS - elapsed
        if wait > 0:
            time.sleep(wait)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            _last_request_at[host] = time.monotonic()
            with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
                if response.status == 429:  # pragma: no cover - urllib raises on 429
                    raise urllib.error.HTTPError(url, 429, "rate limited", response.headers, None)
                body = response.read()
        except urllib.error.HTTPError as exc:
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            if attempt < MAX_ATTEMPTS and (exc.code == 429 or exc.code >= 500):
                delay = float(retry_after) if retry_after and retry_after.isdigit() else 2.0 * attempt
                time.sleep(delay)
                continue
            raise BoardError(f"{url} returned HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt < MAX_ATTEMPTS:
                time.sleep(2.0 * attempt)
                continue
            raise BoardError(f"{url} unreachable: {exc}") from exc
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BoardError(f"{url} returned non-JSON payload") from exc
    raise BoardError(f"{url}: retries exhausted")  # pragma: no cover


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_greenhouse(board_token: str) -> list[dict[str, Any]]:
    """Read a Greenhouse board: https://boards-api.greenhouse.io/v1/boards/{token}/jobs."""
    payload = _polite_get_json(
        f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
    )
    jobs: list[dict[str, Any]] = []
    raw_jobs: list[Any] = list(payload.get("jobs") or [])
    for item in raw_jobs:
        if not isinstance(item, dict):
            continue
        content_html = str(item.get("content") or "")
        description = html_to_text(content_html)
        if len(re.findall(r"[A-Za-z0-9]+", description)) < 20:
            description = ""
        jobs.append({
            "id": f"greenhouse-{board_token}-{item.get('id')}",
            "company": board_token,
            "role": str(item.get("title") or ""),
            "job_url": str(item.get("absolute_url") or ""),
            "location": (item.get("location") or {}).get("name", ""),
            "description": description,
            "source": "ats_board",
            "provider": "greenhouse",
            "fetched_at": _now(),
        })
    return jobs


def fetch_lever(company: str) -> list[dict[str, Any]]:
    """Read a Lever board: https://api.lever.co/v0/postings/{company}?mode=json."""
    payload = _polite_get_json(f"https://api.lever.co/v0/postings/{company}?mode=json")
    jobs: list[dict[str, Any]] = []
    raw_items: list[Any] = list(payload) if isinstance(payload, list) else []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        description = html_to_text(str(item.get("descriptionPlain") or item.get("description") or ""))
        if len(re.findall(r"[A-Za-z0-9]+", description)) < 20:
            description = ""
        categories = item.get("categories") or {}
        jobs.append({
            "id": f"lever-{company}-{item.get('id')}",
            "company": company,
            "role": str(item.get("text") or ""),
            "job_url": str(item.get("hostedUrl") or item.get("applyUrl") or ""),
            "location": str(categories.get("location") or ""),
            "description": description,
            "source": "ats_board",
            "provider": "lever",
            "fetched_at": _now(),
        })
    return jobs


def fetch_ashby(org: str) -> list[dict[str, Any]]:
    """Read an Ashby board via its public posting API."""
    payload = _polite_get_json(f"https://api.ashbyhq.com/posting-api/job-board/{org}")
    jobs: list[dict[str, Any]] = []
    ashby_jobs: list[Any] = list(payload.get("jobs") or [])
    for item in ashby_jobs:
        if not isinstance(item, dict):
            continue
        description = html_to_text(
            str(item.get("descriptionPlain") or item.get("descriptionHtml") or "")
        )
        if len(re.findall(r"[A-Za-z0-9]+", description)) < 20:
            description = ""
        jobs.append({
            "id": f"ashby-{org}-{item.get('id')}",
            "company": org,
            "role": str(item.get("title") or ""),
            "job_url": str(item.get("jobUrl") or item.get("applyUrl") or ""),
            "location": str(item.get("location") or ""),
            "description": description,
            "source": "ats_board",
            "provider": "ashby",
            "fetched_at": _now(),
        })
    return jobs


BOARD_PATTERNS = {
    re.compile(r"boards\.greenhouse\.io/([^/?#]+)", re.IGNORECASE): ("greenhouse", "board"),
    re.compile(r"job-boards\.greenhouse\.io/([^/?#]+)", re.IGNORECASE): ("greenhouse", "board"),
    re.compile(r"jobs\.lever\.co/([^/?#]+)", re.IGNORECASE): ("lever", "company"),
    re.compile(r"jobs\.eu\.lever\.co/([^/?#]+)", re.IGNORECASE): ("lever", "company"),
    re.compile(r"jobs\.ashbyhq\.com/([^/?#]+)", re.IGNORECASE): ("ashby", "org"),
}


def detect_board(url: str) -> tuple[str, str] | None:
    """Map a careers-page URL to ``(provider, token)`` when recognizable."""
    for pattern, (provider, _key) in BOARD_PATTERNS.items():
        match = pattern.search(url)
        if match:
            return provider, match.group(1)
    return None


def fetch_board_url(url: str) -> list[dict[str, Any]]:
    detected = detect_board(url)
    if detected is None:
        raise BoardError(f"not a recognized ATS board URL: {url}")
    provider, token = detected
    fetcher = {"greenhouse": fetch_greenhouse, "lever": fetch_lever, "ashby": fetch_ashby}[provider]
    return fetcher(token)
