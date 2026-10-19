"""Public-page capture via the local pinned Scrapling runtime.

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
import ipaddress
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import tempfile
import time
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, Thread
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

from .artifacts import atomic_copyfile, atomic_write_text

SCRAPLING_PIN = "0.4.12"
CACHE_TTL_SECONDS = 24 * 3600
MIN_HOST_INTERVAL_SECONDS = 1.0
MAX_ATTEMPTS = 3
CAPTURE_DEADLINE_SECONDS = 45.0
MAX_CAPTURE_BYTES = 4 * 1024 * 1024

# This runs inside the separately installed, pinned Scrapling runtime. Its
# Fetcher forwards request keywords to ``curl_cffi.Session.request``, whose
# per-request API does not accept ``curl_options``. Use that runtime's bundled
# Session at its supported construction boundary, then keep Scrapling's
# converter for the ordinary capture output.
_PINNED_SCRAPLING_CAPTURE = f"""\
import sys
from curl_cffi import CurlOpt
from curl_cffi.requests import Session
from scrapling import __version__
from scrapling.core.shell import Convertor
from scrapling.engines.toolbelt.convertor import ResponseFactory

url, output_path, timeout_seconds, ai_targeted, resolve_entry = sys.argv[1:]
if __version__ != {SCRAPLING_PIN!r}:
    raise SystemExit("Scrapling version does not match the required pinned runtime")
MAX_BODY_BYTES = {MAX_CAPTURE_BYTES}
body = bytearray()

class _ResponseTooLarge(RuntimeError):
    pass

def _bounded_content(chunk):
    # ``curl_cffi`` invokes this as body chunks arrive. Raising aborts the
    # transfer before an unbounded response can be buffered by the child.
    if len(body) + len(chunk) > MAX_BODY_BYTES:
        raise _ResponseTooLarge("response exceeds the maximum capture size")
    body.extend(chunk)
    return len(chunk)

try:
    with Session(curl_options={{
        CurlOpt.RESOLVE: [resolve_entry],
        CurlOpt.MAXFILESIZE_LARGE: MAX_BODY_BYTES,
    }}) as session:
        raw_response = session.get(
            url,
            timeout=float(timeout_seconds),
            allow_redirects=False,
            verify=True,
            impersonate=None,
            proxies=None,
            proxy=None,
            content_callback=_bounded_content,
        )
except _ResponseTooLarge as exc:
    raise SystemExit(str(exc)) from exc
except Exception as exc:
    # libcurl can reject a declared Content-Length through MAXFILESIZE before
    # it reaches the write callback. Keep that equivalent limit failure clear
    # and avoid publishing the dependency's traceback as capture content.
    if "maximum allowed file size" in str(exc).lower():
        raise SystemExit("response exceeds the maximum capture size") from None
    raise
if not 200 <= raw_response.status_code < 300:
    raise SystemExit(f"HTTP {{raw_response.status_code}}")
raw_response.content = bytes(body)
response = ResponseFactory.from_http_request(raw_response, {{}})
Convertor.write_content_to_file(
    response,
    output_path,
    None,
    main_content_only=ai_targeted == "1",
)
"""

_last_scrape_at: dict[str, float] = {}
_pacing_lock = Lock()
# ponytail: 64 cache-lock stripes bound memory; collisions only serialize unrelated misses.
_cache_locks = [Lock() for _ in range(64)]


def _sleep(seconds: float) -> None:
    """Honor pacing unless the fast-pace test knob disables it."""

    if seconds <= 0 or os.environ.get("ATS_CAPTURE_FAST_PACE") == "1":
        return
    time.sleep(seconds)

class CaptureError(RuntimeError):
    """A public page could not be captured through Scrapling."""


def _public_https_parts(value: object) -> tuple[str, int, str]:
    """Return one canonical, unambiguous HTTPS DNS target before resolving it."""

    if not isinstance(value, str):
        raise ValueError("capture URLs must be public HTTPS URLs without credentials")
    # ``urlsplit`` deliberately strips some control characters. Reject them
    # before parsing so the hostname checked and the hostname requested cannot
    # differ. A trailing DNS root dot is also rejected rather than relying on
    # curl's host-key normalization for ``CURLOPT_RESOLVE``.
    if any(character.isspace() or ord(character) < 32 for character in value):
        raise ValueError("capture URLs must be public HTTPS URLs without credentials")
    try:
        parsed = urlsplit(value)
        port = parsed.port if parsed.port is not None else 443
    except ValueError as exc:
        raise ValueError("capture URLs must be public HTTPS URLs without credentials") from exc
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port <= 0
    ):
        raise ValueError("capture URLs must be public HTTPS URLs without credentials")

    raw_host = parsed.hostname
    if raw_host.endswith(".") or "%" in raw_host:
        raise ValueError("capture URLs must use an unambiguous public HTTPS DNS hostname")
    try:
        host = raw_host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("capture URLs must use an IDNA-valid public HTTPS DNS hostname") from exc
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("capture URLs must use a public HTTPS DNS hostname, not a public IP literal")
    # ``:443`` is the default HTTPS authority and is not part of the effective
    # request target.  Elide it so cache and batch keys coalesce the standard
    # explicit/implicit-port spellings; retain every non-default port.
    netloc = host if port == 443 else f"{host}:{port}"
    canonical_url = urlunsplit(("https", netloc, parsed.path, parsed.query, parsed.fragment))
    return host, port, canonical_url


def validate_public_https_url(
    value: object,
    *,
    resolver: Callable[..., list[tuple]] | None = None,
    deadline: float | None = None,
) -> str:
    """Accept only credential-free HTTPS URLs resolving entirely to public IPs."""

    return resolve_public_https_url(value, resolver=resolver, deadline=deadline)[0]


def resolve_public_https_url(
    value: object,
    *,
    resolver: Callable[..., list[tuple]] | None = None,
    deadline: float | None = None,
) -> tuple[str, tuple[tuple, ...]]:
    """Validate a URL and return its current public DNS answers for pinning."""

    host, port, canonical_url = _public_https_parts(value)
    lookup = resolver or socket.getaddrinfo
    if deadline is None:
        deadline = time.monotonic() + CAPTURE_DEADLINE_SECONDS
    try:
        answers: Queue = Queue(maxsize=1)

        def resolve() -> None:
            try:
                answers.put(lookup(host, port, type=socket.SOCK_STREAM))
            except Exception as exc:
                answers.put(exc)

        # DNS cannot be cancelled portably; the daemon may finish after the caller's deadline.
        Thread(target=resolve, daemon=True).start()
        try:
            addresses = answers.get(timeout=max(0, deadline - time.monotonic()))
        except Empty as exc:
            raise ValueError("capture deadline expired during DNS resolution") from exc
        if isinstance(addresses, Exception):
            raise ValueError(f"capture URL host cannot be resolved: {host}") from addresses
    except OSError as exc:
        raise ValueError(f"capture URL host cannot be resolved: {host}") from exc
    try:
        resolved = [ipaddress.ip_address(item[4][0]) for item in addresses]
    except (IndexError, TypeError, ValueError) as exc:
        raise ValueError("capture URL host returned an invalid DNS address") from exc
    if not resolved or any(not address.is_global for address in resolved):
        raise ValueError("capture URL host must resolve only to public IP addresses")
    return canonical_url, tuple(addresses)


def clean_capture(text: str) -> str:
    """Remove obvious page chrome while retaining complete content clauses."""

    ignored = re.compile(
        r"^(?:cookie|privacy|accept all|manage preferences|"
        r"skip to (?:main )?content|"
        r"sign in|create account|share this job)$",
        re.IGNORECASE,
    )
    trailing_chrome = re.compile(
        r"^(?:similar jobs|referrals increase your chances|"
        r"get notified about new)",
        re.IGNORECASE,
    )
    lines: list[str] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if trailing_chrome.match(line):
            break
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


def _scrapling_interpreter(executable: str) -> str:
    """Find the Python runtime behind a Scrapling console script.

    A real console-script path is required in production so the pinning runner
    uses the same Scrapling installation that ``scrapling`` resolves to.  The
    missing-path fallback exists only for injected subprocess test doubles.
    """

    path = Path(executable)
    if not path.exists():
        return executable
    candidates = (
        path,
        path.with_suffix(".py"),
        path.with_name(f"{path.stem}-script.py"),
    )
    for candidate in candidates:
        try:
            with candidate.open(encoding="utf-8") as script:
                first_line = script.readline().strip()
        except (OSError, UnicodeDecodeError):
            continue
        if not first_line.startswith("#!"):
            continue
        try:
            command = shlex.split(first_line[2:], posix=os.name != "nt")
        except ValueError:
            continue
        if not command:
            continue
        if Path(command[0]).name.casefold() in {"env", "env.exe"}:
            program = next((part for part in reversed(command[1:]) if not part.startswith("-")), "")
            resolved = shutil.which(program) if program else None
            if resolved:
                return resolved
            continue
        return command[0]
    raise CaptureError("Scrapling must be installed as a Python console script to pin DNS")


def _pinned_resolve_entry(url: str, addresses: tuple[tuple, ...]) -> str:
    """Return one curl resolve mapping for the already-validated DNS answers."""

    host, port, _ = _public_https_parts(url)
    try:
        normalized_host = host.rstrip(".").encode("idna").decode("ascii")
    except UnicodeError as exc:  # pragma: no cover - URL parsing normally rejects this first.
        raise CaptureError("capture URL host cannot be IDNA-normalized") from exc
    resolved = sorted({str(ipaddress.ip_address(item[4][0])) for item in addresses})
    if not resolved:  # pragma: no cover - enforced by resolve_public_https_url.
        raise CaptureError("capture URL host returned no public DNS addresses")
    curl_addresses = [f"[{address}]" if ":" in address else address for address in resolved]
    return f"{normalized_host}:{port}:{','.join(curl_addresses)}"


def _scrape_once(
    executable: str,
    url: str,
    destination: Path,
    *,
    ai_targeted: bool,
    timeout_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    host = re.sub(r"^https?://", "", url).split("/", 1)[0]
    with _pacing_lock:
        now = time.monotonic()
        next_allowed = max(now, _last_scrape_at.get(host, 0.0) + MIN_HOST_INTERVAL_SECONDS)
        if os.environ.get("ATS_CAPTURE_FAST_PACE") == "1":
            next_allowed = now
        _last_scrape_at[host] = next_allowed
    wait = next_allowed - now
    if wait >= deadline - time.monotonic():
        raise CaptureError("capture deadline expired waiting for host pacing")
    if wait > 0:
        _sleep(wait)
    try:
        _, before_addresses = resolve_public_https_url(url, deadline=deadline)
    except ValueError as exc:
        raise CaptureError(str(exc)) from exc
    resolve_entry = _pinned_resolve_entry(url, before_addresses)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise CaptureError("capture deadline expired before fetch")
    completed = subprocess.run(
        [
            _scrapling_interpreter(executable),
            "-c",
            _PINNED_SCRAPLING_CAPTURE,
            url,
            str(destination),
            str(max(1, int(timeout_seconds))),
            "1" if ai_targeted else "0",
            resolve_entry,
        ],
        capture_output=True,
        text=True,
        shell=False,
        timeout=remaining,
        env=_capture_environment(),
    )
    if completed.returncode or not destination.is_file():
        detail = (completed.stderr or completed.stdout).strip()[-1000:]
        raise CaptureError(
            f"Scrapling capture failed for {url}: {detail or 'no output'}"
        )


def _capture_environment() -> dict[str, str]:
    """Keep public capture independent of ambient proxy, TLS, and Python overrides."""

    environment = os.environ.copy()
    for name in (
        "ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
        "all_proxy", "http_proxy", "https_proxy", "no_proxy",
        "SSL_CERT_FILE", "SSL_CERT_DIR", "CURL_CA_BUNDLE", "REQUESTS_CA_BUNDLE",
        "PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP", "PYTHONUSERBASE",
    ):
        environment.pop(name, None)
    environment["PYTHONNOUSERSITE"] = "1"
    return environment


def capture_url(
    url: str,
    destination: Path,
    *,
    source_type: str,
    attempts: int = MAX_ATTEMPTS,
) -> dict[str, object]:
    """Capture one ordinary public HTTPS page within a bounded retry deadline."""

    deadline = time.monotonic() + CAPTURE_DEADLINE_SECONDS
    try:
        url = validate_public_https_url(url, deadline=deadline)
    except ValueError as exc:
        raise CaptureError(str(exc)) from exc
    executable = require_scrapling()
    destination.parent.mkdir(parents=True, exist_ok=True)
    suffix = destination.suffix.lower()
    if suffix not in {".html", ".md", ".txt"}:
        suffix = ".txt"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=suffix, dir=destination.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    last_error: Exception | None = None
    try:
        for attempt in range(1, max(1, attempts) + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            ai_targeted = attempt != 2
            try:
                _scrape_once(
                    executable,
                    url,
                    temporary,
                    ai_targeted=ai_targeted,
                    timeout_seconds=min(30.0, remaining),
                )
                if temporary.stat().st_size > MAX_CAPTURE_BYTES:
                    raise CaptureError(
                        f"Scrapling capture exceeds the {MAX_CAPTURE_BYTES // (1024 * 1024)} MiB limit"
                    )
                captured = temporary.read_text(encoding="utf-8")
                cleaned = clean_capture(captured)
                if _word_count(cleaned) >= 8:
                    temporary.write_text(cleaned, encoding="utf-8")
                    os.replace(temporary, destination)
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
                if re.search(
                    r"(?:HTTP\s*|status\s*[:=]?\s*)(?:400|401|403|404|410)\b|"
                    r"(?:response exceeds the maximum capture size|"
                    r"Scrapling capture exceeds the \d+ MiB limit)",
                    str(exc),
                    re.I,
                ):
                    break
            delay = 2.0 * attempt
            if attempt < attempts and delay < deadline - time.monotonic():
                _sleep(delay)
        if last_error is None:
            last_error = CaptureError(f"capture deadline expired for {url}")
        raise last_error
    finally:
        temporary.unlink(missing_ok=True)


def _cache_key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]


def capture_cached(
    url: str,
    cache_dir: Path,
    *,
    source_type: str,
    destination: Path | None = None,
    ttl_seconds: int = CACHE_TTL_SECONDS,
) -> dict[str, object]:
    """Capture with a 24-hour content cache; fresh entries skip the network."""

    try:
        _, _, canonical_url = _public_https_parts(url)
    except ValueError as exc:
        raise CaptureError(str(exc)) from exc
    key = _cache_key(str(cache_dir.resolve()) + canonical_url)
    with _cache_locks[int(key, 16) % len(_cache_locks)]:
        return _capture_cached(canonical_url, cache_dir, source_type=source_type,
                               destination=destination, ttl_seconds=ttl_seconds)


def _capture_cached(
    url: str, cache_dir: Path, *, source_type: str,
    destination: Path | None, ttl_seconds: int,
) -> dict[str, object]:
    try:
        _, _, url = _public_https_parts(url)
    except ValueError as exc:
        raise CaptureError(str(exc)) from exc
    entry_path = cache_dir / f"{_cache_key(url)}.json"
    body_path = cache_dir / f"{_cache_key(url)}.txt"
    if entry_path.exists() and body_path.exists():
        try:
            entry = json.loads(entry_path.read_text(encoding="utf-8"))
            fetched_at = datetime.fromisoformat(entry["captured_at"])
            age = datetime.now(timezone.utc).timestamp() - fetched_at.timestamp()
            body = body_path.read_bytes()
            if (
                fetched_at.tzinfo is not None
                and 0 <= age <= ttl_seconds
                and entry.get("url") == url
                and entry.get("sha256") == hashlib.sha256(body).hexdigest()
            ):
                target = destination or body_path
                target.parent.mkdir(parents=True, exist_ok=True)
                if target != body_path:
                    atomic_copyfile(body_path, target)
                return {
                    **entry,
                    "path": str(target),
                    "source_type": source_type,
                    "cache": "hit",
                }
        except (OSError, ValueError, KeyError, TypeError, AttributeError, json.JSONDecodeError):
            pass
    try:
        validate_public_https_url(url)
    except ValueError as exc:
        raise CaptureError(str(exc)) from exc
    cache_dir.mkdir(parents=True, exist_ok=True)
    temporary_body = body_path.with_suffix(".tmp")
    try:
        result = capture_url(url, temporary_body, source_type=source_type)
        os.replace(temporary_body, body_path)
    except Exception:
        temporary_body.unlink(missing_ok=True)
        raise
    cached = {**result, "path": str(body_path), "source_type": source_type}
    atomic_write_text(entry_path, json.dumps(cached, sort_keys=True))
    target = destination or body_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if target != body_path:
        atomic_copyfile(body_path, target)
    return {**cached, "path": str(target), "cache": "miss"}


def fetch_many(
    urls: list[tuple[str, Path]],
    *,
    source_type: str,
    workers: int = 4,
    use_cache: bool = True,
    cache_dir: Path | None = None,
) -> list[dict[str, object] | CaptureError]:
    """Capture several URLs with bounded concurrency, preserving order."""

    unique: dict[str, tuple[str, Path]] = {}
    request_keys: list[str] = []
    for url, destination in urls:
        try:
            _, _, canonical_url = _public_https_parts(url)
        except ValueError:
            # Let the ordinary capture path turn an unsafe input into its
            # visible CaptureError instead of raising from batch setup.
            canonical_url = url
        unique.setdefault(canonical_url, (canonical_url, destination))
        request_keys.append(canonical_url)

    def run(item: tuple[str, Path]) -> dict[str, object] | CaptureError:
        url, destination = item
        try:
            if use_cache and cache_dir is not None:
                return capture_cached(
                    url,
                    cache_dir,
                    source_type=source_type,
                    destination=destination,
                )
            return capture_url(url, destination, source_type=source_type)
        except CaptureError as exc:
            return exc

    workers = max(1, min(workers, 4))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        unique_results = dict(zip(unique, pool.map(run, unique.values()), strict=True))
    normalized: list[dict[str, object] | CaptureError] = []
    for item, request_key in zip(urls, request_keys, strict=True):
        result = unique_results[request_key]
        if isinstance(result, CaptureError):
            normalized.append(result)
        elif isinstance(result, dict):
            destination = item[1]
            cached_path = Path(str(result["path"]))
            destination.parent.mkdir(parents=True, exist_ok=True)
            if cached_path != destination:
                atomic_copyfile(cached_path, destination)
            normalized.append({**result, "path": str(destination)})
        else:  # pragma: no cover - defensive
            normalized.append(CaptureError(f"unexpected capture result for {request_key}"))
    return normalized
