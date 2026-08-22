"""Public-page capture via the local Scrapling CLI.

Extracted from ``job_research`` so the ``tailor`` orchestrator and batch
research share one capture path with identical provenance. Additions over
the original single-shot helper:

- retry with backoff and a fallback extraction mode
- bounded-concurrency pool with per-host pacing
- 24-hour content cache keyed by URL digest

Provenance schema is unchanged: ``url, path, sha256, captured_at, method,
source_type, extraction_status``.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

SCRAPLING_PIN = "0.4.12"
CACHE_TTL_SECONDS = 24 * 3600
MIN_HOST_INTERVAL_SECONDS = 1.0
MAX_ATTEMPTS = 3

_last_scrape_at: dict[str, float] = {}


def _sleep(seconds: float) -> None:
    """Honor pacing unless the fast-pace test knob disables it."""

    if seconds <= 0 or os.environ.get("ATS_CAPTURE_FAST_PACE") == "1":
        return
    time.sleep(seconds)

_BASE_ARGS_TEMPLATE = [
    "extract",
    "get",
    "{url}",
    "{destination}",
    "--timeout",
    "30",
]


class CaptureError(RuntimeError):
    """A public page could not be captured through Scrapling."""


def clean_capture(text: str) -> str:
    """Remove obvious page chrome while retaining complete content clauses."""

    ignored = re.compile(
        r"^(?:cookie|privacy|accept all|manage preferences|skip to content|"
        r"sign in|create account|share this job)$",
        re.IGNORECASE,
    )
    lines: list[str] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line or ignored.match(line) or line.lower() in seen:
            continue
        seen.add(line.lower())
        lines.append(line)
    return "\n".join(lines) + ("\n" if lines else "")


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+", text))


def scrapling_executable() -> str | None:
    return shutil.which("scrapling")


def require_scrapling() -> str:
    executable = scrapling_executable()
    if executable is None:
        raise CaptureError(
            "Scrapling is required for URL capture; install it separately with "
            f"uv tool install 'scrapling=={SCRAPLING_PIN}'"
        )
    return executable


def _scrape_once(
    executable: str,
    url: str,
    destination: Path,
    *,
    ai_targeted: bool,
) -> None:
    args = [part for arg in _BASE_ARGS_TEMPLATE for part in (
        arg.replace("{url}", url).replace("{destination}", str(destination)),
    )]
    args += ["--no-follow-redirects", "--no-stealthy-headers"]
    if ai_targeted:
        args += ["--ai-targeted"]

    host = re.sub(r"^https?://", "", url).split("/", 1)[0]
    elapsed = time.monotonic() - _last_scrape_at.get(host, 0.0)
    wait = MIN_HOST_INTERVAL_SECONDS - elapsed
    if wait > 0:
        _sleep(wait)
    completed = subprocess.run(
        [executable, *args],
        capture_output=True,
        text=True,
        shell=False,
        timeout=45 + (15 if not ai_targeted else 0),
    )
    _last_scrape_at[host] = time.monotonic()
    if completed.returncode or not destination.is_file():
        detail = (completed.stderr or completed.stdout).strip()[-1000:]
        raise CaptureError(
            f"Scrapling capture failed for {url}: {detail or 'no output'}"
        )


def capture_url(
    url: str,
    destination: Path,
    *,
    source_type: str,
    attempts: int = MAX_ATTEMPTS,
) -> dict[str, object]:
    """Capture one public page with retry and extraction-mode fallback."""

    executable = require_scrapling()
    last_error: Exception | None = None
    for attempt in range(1, max(1, attempts) + 1):
        ai_targeted = attempt % 2 == 1  # alternate focused/default extraction
        try:
            _scrape_once(executable, url, destination, ai_targeted=ai_targeted)
            captured = destination.read_text(encoding="utf-8")
            cleaned = clean_capture(captured)
            if _word_count(cleaned) >= 8:
                destination.write_text(cleaned, encoding="utf-8")
                return {
                    "url": url,
                    "path": str(destination),
                    "sha256": hashlib.sha256(cleaned.encode("utf-8")).hexdigest(),
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "method": "scrapling_public_https",
                    "source_type": source_type,
                    "extraction_status": "captured",
                }
            last_error = CaptureError(
                f"Scrapling capture was empty or insufficient for {url}"
            )
        except (CaptureError, subprocess.TimeoutExpired, OSError) as exc:
            last_error = exc if isinstance(exc, CaptureError) else CaptureError(str(exc))
        if attempt < attempts:
            _sleep(2.0 * attempt)
    assert last_error is not None
    raise last_error


def _cache_key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]


def capture_cached(
    url: str,
    cache_dir: Path,
    *,
    source_type: str,
    ttl_seconds: int = CACHE_TTL_SECONDS,
) -> dict[str, object]:
    """Capture with a 24-hour content cache; fresh entries skip the network."""

    cache_dir.mkdir(parents=True, exist_ok=True)
    entry_path = cache_dir / f"{_cache_key(url)}.json"
    body_path = cache_dir / f"{_cache_key(url)}.txt"
    if entry_path.exists() and body_path.exists():
        try:
            entry = json.loads(entry_path.read_text(encoding="utf-8"))
            fetched_at = datetime.fromisoformat(entry["captured_at"])
            age = datetime.now(timezone.utc).timestamp() - fetched_at.timestamp()
            if age <= ttl_seconds:
                entry["cache"] = "hit"
                return entry
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            pass
    result = capture_url(url, body_path, source_type=source_type)
    entry_path.write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
    result["cache"] = "miss"
    return dict(result)


def fetch_many(
    urls: list[tuple[str, Path]],
    *,
    source_type: str,
    workers: int = 4,
    use_cache: bool = True,
    cache_dir: Path | None = None,
) -> list[dict[str, object] | CaptureError]:
    """Capture several URLs with bounded concurrency, preserving order."""

    def run(item: tuple[str, Path]) -> dict[str, object]:
        url, destination = item
        if use_cache and cache_dir is not None:
            return capture_cached(url, cache_dir, source_type=source_type)
        return capture_url(url, destination, source_type=source_type)

    workers = max(1, min(workers, 4))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(run, urls))
    normalized: list[dict[str, object] | CaptureError] = []
    for item, result in zip(urls, results, strict=True):
        if isinstance(result, CaptureError):
            normalized.append(result)
        elif isinstance(result, dict):
            normalized.append({**result, "path": str(item[1])})
        else:  # pragma: no cover - defensive
            normalized.append(CaptureError(f"unexpected capture result for {item[0]}"))
    return normalized
