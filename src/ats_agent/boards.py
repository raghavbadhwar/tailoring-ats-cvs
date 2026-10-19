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

import http.client
import json
import re
import socket
import ssl
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from threading import Lock, local
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any
from .capture import MAX_CAPTURE_BYTES, resolve_public_https_url

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


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise BoardError("board redirects are not permitted")


_transport_state = local()


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connect only to the public IPs checked for this exact request."""

    def __init__(self, host: str, *, addresses: tuple[tuple, ...], **kwargs: Any) -> None:
        super().__init__(host, **kwargs)
        self._addresses = addresses

    def connect(self) -> None:
        if getattr(self, "_tunnel_host", None):  # Proxy tunnelling would defeat request-local pinning.
            raise OSError("board proxy tunnelling is not permitted")
        context = getattr(self, "_context", None) or ssl.create_default_context()
        last_error: OSError | None = None
        for family, socktype, protocol, _canonical_name, address in self._addresses:
            sock = socket.socket(family, socktype, protocol)
            try:
                sock.settimeout(self.timeout)
                sock.connect(address)
                self.sock = context.wrap_socket(sock, server_hostname=self.host)
                return
            except OSError as exc:
                last_error = exc
                sock.close()
        raise OSError("board connection to validated public IPs failed") from last_error


class _PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    """Install a request-local connection factory without proxy fallback."""

    def https_open(self, request: urllib.request.Request):  # noqa: ANN201
        state = getattr(_transport_state, "resolution", None)
        if state is None or state[0] != request.full_url:
            try:
                _, addresses = resolve_public_https_url(request.full_url)
            except ValueError as exc:
                raise BoardError(str(exc)) from exc
        else:
            _, addresses = state

        def connection(host: str, **kwargs: Any) -> _PinnedHTTPSConnection:
            return _PinnedHTTPSConnection(host, addresses=addresses, **kwargs)

        return self.do_open(connection, request, context=getattr(self, "_context", None))


_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}), _NoRedirect(), _PinnedHTTPSHandler()
)
_request_lock = Lock()


def _open_pinned(
    request: urllib.request.Request,
    *,
    timeout: float,
    url: str,
    addresses: tuple[tuple, ...],
):  # noqa: ANN201
    previous = getattr(_transport_state, "resolution", None)
    _transport_state.resolution = (url, addresses)
    try:
        return _OPENER.open(request, timeout=timeout)
    finally:
        if previous is None:
            del _transport_state.resolution
        else:
            _transport_state.resolution = previous


def _response_socket(response: Any) -> socket.socket | None:
    raw = getattr(getattr(response, "fp", None), "raw", None)
    candidate = getattr(raw, "_sock", None)
    return candidate if isinstance(candidate, socket.socket) else None


def _read_limited(response: Any, deadline: float) -> bytes:
    """Bound total response time and bytes, including trickling responses."""

    limit = MAX_CAPTURE_BYTES
    chunks: list[bytes] = []
    total = 0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("board capture deadline expired while reading response")
        peer = _response_socket(response)
        if peer is not None:
            peer.settimeout(max(0.001, min(DEFAULT_TIMEOUT, remaining)))
        chunk = response.read(min(64 * 1024, limit + 1 - total))
        if time.monotonic() > deadline:
            raise TimeoutError("board capture deadline expired while reading response")
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > limit:
            raise BoardError("board response exceeds the 4 MiB limit")
        chunks.append(chunk)


def _polite_get_json(url: str) -> dict[str, Any]:
    deadline = time.monotonic() + 45.0
    try:
        url, _ = resolve_public_https_url(url, deadline=deadline)
    except ValueError as exc:
        raise BoardError(str(exc)) from exc
    host = urlsplit(url).netloc.lower()
    for attempt in range(1, MAX_ATTEMPTS + 1):
        with _request_lock:
            now = time.monotonic()
            next_allowed = max(now, _last_request_at.get(host, 0.0) + MIN_HOST_INTERVAL_SECONDS)
            _last_request_at[host] = next_allowed
        wait = next_allowed - now
        if wait >= deadline - time.monotonic():
            raise BoardError("board capture deadline expired during pacing")
        if wait > 0:
            time.sleep(wait)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        delay = 2.0 * attempt
        try:
            _, addresses = resolve_public_https_url(url, deadline=deadline)
            with _open_pinned(
                request,
                timeout=min(DEFAULT_TIMEOUT, max(0.001, deadline - time.monotonic())),
                url=url,
                addresses=addresses,
            ) as response:
                body = _read_limited(response, deadline)
        except urllib.error.HTTPError as exc:
            if exc.code != 429 and exc.code < 500:
                raise BoardError(f"{url} returned HTTP {exc.code}") from exc
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            if retry_after:
                try:
                    delay = float(retry_after) if retry_after.isdigit() else max(
                        0.0, parsedate_to_datetime(retry_after).timestamp() - time.time())
                except (TypeError, ValueError, OverflowError):
                    pass
            failure: Exception = exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            failure = exc
        else:
            try:
                return json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise BoardError(f"{url} returned non-JSON payload") from exc
        if attempt == MAX_ATTEMPTS or delay >= deadline - time.monotonic():
            raise BoardError(f"{url}: retry budget exhausted: {failure}") from failure
        time.sleep(delay)
    raise BoardError(f"{url}: retries exhausted")

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
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.port not in {None, 443}):
            return None
    except ValueError:
        return None
    for pattern, (provider, _key) in BOARD_PATTERNS.items():
        match = pattern.match(parsed.hostname + parsed.path)
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
