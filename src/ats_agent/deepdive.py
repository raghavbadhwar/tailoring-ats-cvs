"""Company deep-dive: hiring-momentum intelligence from public signals.

Answers two questions for an aspirant:

1. Companies posting today — which roles match my aspiration, how strongly?
2. Companies NOT posting my role — do public signals say they might soon?

Sources are strictly public and structured where possible: ATS syndication
feeds (Greenhouse/Lever/Ashby) first, Scrapling capture of ordinary careers
pages as a labelled fallback. Every claim carries its source and timestamp.
Verdicts are transparent momentum scorings of captured facts, never promises.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
import re
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .boards import BoardError, detect_board
from .boards import fetch_ashby, fetch_greenhouse, fetch_lever
from .capture import CaptureError, capture_url
from .requirements import TERM_ALIASES, _contains_alias

WATCHLIST_SCHEMA = 1
DEFAULT_WATCHLIST_PATH = Path(
    "~/.local/state/tailoring-ats-cvs/watchlist.json"
).expanduser()

INTERN_PATTERN = re.compile(r"\bintern(?:ship|s)?\b", re.IGNORECASE)
PROVIDER_URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true",
    "lever": "https://api.lever.co/v0/postings/{token}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{token}",
}
_FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
}


# --------------------------------------------------------------------------
# aspiration vocabulary


def expand_aspiration(aspire_text: str) -> list[str]:
    """Expand an aspiration phrase into canonical + alias vocabulary.

    A multi-word phrase keeps itself as the strong matching unit; its bare
    sub-tokens ("data" out of "data analyst") are suppressed as too generic
    to drive direct matches.
    """
    phrase = aspire_text.strip().lower()
    words = re.findall(r"[a-z0-9+#./]+", phrase)
    vocab: list[str] = [phrase] if phrase else []
    for token in words:
        if len(words) > 1 and token in phrase:
            continue
        vocab.extend(TERM_ALIASES.get(token, [token]))
    seen: set[str] = set()
    ordered: list[str] = []
    for term in vocab:
        key = term.lower()
        if key and key not in seen:
            seen.add(key)
            ordered.append(term)
    return ordered


def _match_terms(text: str, vocab: list[str]) -> list[str]:
    """Alias matches plus simple plural tolerance ("analysts" ~ "analyst")."""

    body = text.lower()
    hits: list[str] = []
    for term in vocab:
        if _contains_alias(body, term):
            hits.append(term)
            continue
        if re.search(
            rf"(?<![a-z0-9]){re.escape(term.lower())}s(?![a-z0-9])", body
        ):
            hits.append(term)
    return hits


def _days_since(iso_text: str) -> float | None:
    try:
        moment = datetime.fromisoformat(str(iso_text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0.0, (datetime.now(timezone.utc) - moment).total_seconds() / 86400)


# --------------------------------------------------------------------------
# analysis


def analyze_roles(jobs: list[dict[str, Any]], vocab: list[str]) -> dict[str, Any]:
    direct: list[dict[str, Any]] = []
    adjacent: list[dict[str, Any]] = []
    intern_open: list[dict[str, Any]] = []
    newest_days: float | None = None

    for job in jobs:
        haystack = f"{job.get('role') or ''} {job.get('description') or ''}"
        hits = _match_terms(haystack, vocab)
        title_hits = _match_terms(str(job.get("role") or ""), vocab)
        age = _days_since(job.get("updated_at") or job.get("fetched_at") or "")
        if age is not None:
            newest_days = age if newest_days is None else min(newest_days, age)
        entry = {
            "role": job.get("role"),
            "url": job.get("job_url") or job.get("hostedUrl"),
            "description": str(job.get("description") or ""),
            "company": str(job.get("company") or ""),
            "matched_terms": hits[:8],
            "title_match": bool(title_hits),
            "age_days": round(age) if age is not None else None,
        }
        if INTERN_PATTERN.search(str(job.get("role") or "")):
            intern_open.append(entry)
        strong = len(hits) >= 2 or bool(title_hits)
        if strong:
            direct.append(entry)
        elif hits:
            adjacent.append(entry)

    return {
        "total_postings": len(jobs),
        "direct_matches": direct,
        "adjacent_matches": adjacent,
        "intern_openings_now": intern_open,
        "newest_posting_age_days": (
            round(newest_days) if newest_days is not None else None
        ),
    }


def internship_program_signal(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    """Intern titles among *currently published* postings (feeds expose no
    closed history), so this reflects a live program, not past cohorts."""
    intern_titles = [
        str(j.get("role") or "")
        for j in jobs
        if INTERN_PATTERN.search(str(j.get("role") or ""))
    ]
    departments = sorted({
        str((j.get("categories") or {}).get("department")
            or j.get("department") or "")
        for j in jobs
        if INTERN_PATTERN.search(str(j.get("role") or ""))
    } - {""})
    return {
        "intern_open_now": len(intern_titles),
        "intern_titles_seen": intern_titles[:10],
        "departments": departments[:6],
        "program_evidence": bool(intern_titles),
    }


def verdict(analysis: dict[str, Any], program: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    direct_n = len(analysis["direct_matches"])
    adjacent_n = len(analysis["adjacent_matches"])
    fresh = (
        analysis["newest_posting_age_days"] is not None
        and analysis["newest_posting_age_days"] <= 30
    )
    if direct_n >= 1:
        reasons.append(f"{direct_n} opening(s) directly match the aspiration")
        if fresh:
            reasons.append("board activity within the last month")
        return "ACT NOW", reasons
    if adjacent_n >= 2 or (adjacent_n == 1 and fresh):
        reasons.append(
            f"{adjacent_n} adjacent opening(s) share the aspiration's vocabulary"
        )
        reasons.append("teams hiring adjacents often expand into the aspired role")
        return "WATCH CLOSELY", reasons
    if analysis["total_postings"]:
        notes = (
            f"{analysis['total_postings']} postings open, none near the "
            "aspiration yet"
        )
        if program["intern_open_now"]:
            notes += (
                f"; {program['intern_open_now']} intern title(s) suggest a "
                "running internship program"
            )
        return "ON RADAR", [notes,
                            "re-run weekly; new postings flip this to ACT NOW"]
    return "NO_SIGNAL", ["no structured postings found for this source"]


def analyze_careers_page_text(text: str, vocab: list[str]) -> dict[str, Any]:
    lowered = text.lower()
    markers = {
        marker: (marker in lowered)
        for marker in (
            "we're hiring", "we are hiring", "join our team",
            "open positions", "current openings", "now hiring",
            "grow our team",
        )
    }
    return {
        "method": "careers_page_capture",
        "hiring_markers": [k for k, v in markers.items() if v],
        "marker_hits": sum(markers.values()),
        "vocabulary_on_page": _match_terms(text, vocab)[:10],
    }


# --------------------------------------------------------------------------
# watchlist


class Watchlist:
    def __init__(self, path: Path = DEFAULT_WATCHLIST_PATH):
        self.path = path
        self.data: dict[str, Any] = {
            "schema_version": WATCHLIST_SCHEMA,
            "companies": {},
        }
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                loaded = None
            if isinstance(loaded, dict) and loaded.get("schema_version") == WATCHLIST_SCHEMA:
                self.data = loaded

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)

    def record(self, key: str, fingerprint: dict[str, Any]) -> dict[str, Any] | None:
        previous = self.data["companies"].get(key)
        entry = dict(fingerprint)
        entry["checked_at"] = datetime.now(timezone.utc).isoformat()
        self.data["companies"][key] = entry
        self.save()
        return previous

    @staticmethod
    def fingerprint(jobs: list[dict[str, Any]]) -> dict[str, Any]:
        ids = sorted({str(j.get("id") or j.get("job_url")) for j in jobs})
        digest = hashlib.sha256("|".join(ids).encode("utf-8")).hexdigest()[:16]
        newest = max((str(j.get("updated_at") or "") for j in jobs), default="")
        return {"posting_count": len(jobs), "content_digest": digest,
                "newest_updated_at": newest}

    @staticmethod
    def delta(previous: dict[str, Any] | None,
              current: dict[str, Any]) -> list[str]:
        if not previous:
            return ["first snapshot taken"]
        deltas: list[str] = []
        prev_n = previous.get("posting_count") or 0
        cur_n = current.get("posting_count") or 0
        if prev_n != cur_n:
            deltas.append(
                f"postings {'grew' if cur_n > prev_n else 'shrank'}: {prev_n} → {cur_n}"
            )
        if previous.get("content_digest") != current.get("content_digest"):
            deltas.append("board content changed since last check")
        if current.get("newest_updated_at") and \
                current["newest_updated_at"] != previous.get("newest_updated_at"):
            deltas.append(f"newest posting updated: {str(current['newest_updated_at'])[:10]}")
        return deltas or ["no change since last check"]


# --------------------------------------------------------------------------
# orchestration


def _provider_url(provider: str, token: str) -> str:
    return PROVIDER_URLS[provider].format(token=token)


def _clean_lines(text: str) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line or line.lower() in seen:
            continue
        seen.add(line.lower())
        lines.append(line)
    return "\n".join(lines)


def _slug(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug[:40] or "role"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _probe_board(target: tuple[str, str], aspire_vocab: list[str]) -> dict[str, Any]:
    provider, token = target
    jobs = _FETCHERS[provider](token)
    analysis = analyze_roles(jobs, aspire_vocab) if aspire_vocab else {
        "total_postings": len(jobs),
        "direct_matches": [],
        "adjacent_matches": [],
        "intern_openings_now": [],
        "newest_posting_age_days": None,
    }
    program = internship_program_signal(jobs)
    state, reasons = verdict(analysis, program)
    fingerprint = Watchlist.fingerprint(jobs)
    return {
        "source": f"{provider}:{token}",
        "verdict": state,
        "reasons": reasons,
        "analysis": analysis,
        "internship_program": program,
        "fingerprint": fingerprint,
        "jobs": jobs,
    }


def deep_dive(
    source: str,
    *,
    aspire: str = "",
    watch: bool = False,
    watchlist_path: Path = DEFAULT_WATCHLIST_PATH,
    max_boards: int = 10,
    save_matches: Path | None = None,
    quiet: bool = False,
    writer: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    writer = (lambda _text: None) if quiet else (
        writer or (lambda text: print(text, file=sys.stderr))
    )
    vocab = expand_aspiration(aspire) if aspire else []
    stripped = source.strip()

    # 1 · decide probe set -------------------------------------------------
    targets: list[tuple[str, str]] = []
    page_fallback: dict[str, Any] | None = None

    if "\n" in stripped:
        for line in stripped.splitlines():
            detected = detect_board(line.strip())
            if detected:
                targets.append(detected)
    else:
        detected = detect_board(stripped)
        if detected:
            targets.append(detected)

    if not targets:
        if stripped.startswith(("http://", "https://")):
            page_fallback = {"url": stripped}
        elif "/" not in stripped and "." not in stripped:
            targets = [
                ("greenhouse", stripped),
                ("lever", stripped),
                ("ashby", stripped),
            ][:max(1, max_boards)]
        else:
            page_fallback = {"url": f"https://{stripped}/careers"}

    # 2 · structured probes ------------------------------------------------
    probes: list[dict[str, Any]] = []
    if targets:
        def safe_probe(target: tuple[str, str]) -> dict[str, Any]:
            try:
                return _probe_board(target, vocab)
            except BoardError as exc:
                provider, token = target
                return {
                    "source": f"{provider}:{token}",
                    "verdict": "NO_SIGNAL",
                    "reasons": [f"feed unavailable: {exc}"],
                    "analysis": {"total_postings": 0, "direct_matches": [],
                                 "adjacent_matches": [],
                                 "intern_openings_now": [],
                                 "newest_posting_age_days": None},
                    "internship_program": {"program_evidence": False,
                                           "intern_open_now": 0,
                                           "intern_titles_seen": [],
                                           "departments": []},
                    "fingerprint": Watchlist.fingerprint([]),
                }

        with ThreadPoolExecutor(max_workers=3) as pool:
            probes = [
                p for p in pool.map(safe_probe, targets[:max_boards])
            ]

    # 3 · careers-page fallback when nothing structured --------------------
    if not probes and page_fallback is not None:
        destination = Path(tempfile.mkdtemp(prefix="deep-dive-")) / "careers.txt"
        try:
            provenance = capture_url(page_fallback["url"], destination,
                                     source_type="careers_page")
            page = analyze_careers_page_text(
                _clean_lines(destination.read_text(encoding="utf-8")), vocab
            )
            page_fallback.update({
                "method": provenance["method"],
                "captured_at": provenance["captured_at"],
            })
        except CaptureError as exc:
            raise BoardError(
                f"no ATS feed found for {stripped!r} and the careers-page "
                f"capture failed: {exc}"
            ) from exc
        card = _card_fallback(stripped, page_fallback, page)
        print(card, file=sys.stderr)
        return {"status": "completed", "mode": "careers_page",
                "analysis": page, "card": card, "changed": False,
                "matches_file": None, "match_count": 0, "next_hint": ""}

    if not probes:
        raise BoardError(f"could not resolve a probe target from {stripped!r}")

    # 4 · watchlist ---------------------------------------------------------
    watchlist = Watchlist(watchlist_path) if watch else None
    for result in probes:
        result.pop("jobs", None)
        key = result["source"]
        if watchlist:
            previous = watchlist.record(key, result["fingerprint"])
            result["deltas"] = Watchlist.delta(previous, result["fingerprint"])
        else:
            result["deltas"] = []

    export_jobs: list[dict[str, Any]] = []
    for result in probes:
        company = result["source"].split(":", 1)[1]
        for match in result["analysis"].get("direct_matches", []):
            if not match.get("url"):
                continue
            export_jobs.append({
                "id": f"{result['source']}-{_slug(match['role'] or 'role')}",
                "company": match.get("company") or company,
                "role": match["role"],
                "job_url": match["url"],
                "description": match.get("description", ""),
                "source": "deep_dive",
            })
    IGNORED_DELTAS = ("no change", "first snapshot")
    changed = any(
        any(not d.startswith(IGNORED_DELTAS) for d in r.get("deltas", []))
        for r in probes
    )
    matches_path = save_matches or Path("deep-dive-matches.json")
    next_hint = ""
    if export_jobs:
        matches_path.write_text(
            json.dumps({"jobs": export_jobs}, indent=1) + "\n", encoding="utf-8"
        )
        next_hint = (
            'next → ats-agent tailor <your-cv> "'
            + str(matches_path)
            + '" --run-dir runs/deep-dive --approve-from approvals.json'
        )
    card = _card(probes, aspire)
    if not quiet:
        print(card, file=sys.stderr)
        if next_hint:
            print(next_hint, file=sys.stderr)
    return {"status": "completed", "mode": "boards",
            "aspire": aspire, "results": probes, "card": card,
            "matches_file": str(matches_path) if export_jobs else None,
            "match_count": len(export_jobs),
            "changed": changed, "next_hint": next_hint}


# --------------------------------------------------------------------------
# presentation


_VERDICT_ICON = {
    "ACT NOW": "🟢 ACT NOW",
    "WATCH CLOSELY": "🟡 WATCH CLOSELY",
    "ON RADAR": "🟠 ON RADAR",
    "COLD": "⚪ COLD",
    "NO_SIGNAL": "⚪ NO SIGNAL",
}


def _card(results: list[dict[str, Any]], aspire: str) -> str:
    lines = ["════ Company deep-dive ════"]
    if aspire:
        lines.append(f"aspiration : {aspire}")
    for result in results:
        lines.append(
            f"{_VERDICT_ICON.get(result['verdict'], result['verdict'])}"
            f"  {result['source']}"
        )
        for reason in result["reasons"]:
            lines.append(f"   · {reason}")
        for delta in result.get("deltas", []):
            if delta:
                lines.append(f"   Δ {delta}")
        for match in result["analysis"].get("direct_matches", [])[:5]:
            age = match.get("age_days")
            suffix = f" ({age}d)" if age is not None else ""
            lines.append(f"   → {match['role']}{suffix}")
            if match["url"]:
                lines.append(f"     {match['url']}")
        program = result.get("internship_program") or {}
        if program.get("program_evidence"):
            titles = ", ".join(program["intern_titles_seen"][:3]) or "—"
            lines.append(
                f"   ℹ internship program: {program['intern_open_now']} open now"
                f" · titles seen: {titles}"
            )
    lines.append(
        "signals: public ATS feeds only — momentum scores, never predictions."
    )
    return "\n".join(lines)


def _card_fallback(source: str, meta: dict[str, Any],
                   page: dict[str, Any]) -> str:
    lines = ["════ Company deep-dive (careers page) ════"]
    lines.append(
        f"source : {source} — {meta.get('method')}, "
        f"captured {str(meta.get('captured_at', ''))[:10]}"
    )
    if page["marker_hits"]:
        lines.append(f"🟡 hiring language found: {', '.join(page['hiring_markers'])}")
    else:
        lines.append("⚪ no hiring language on the captured page")
    if page["vocabulary_on_page"]:
        lines.append(
            "aspiration vocabulary present: "
            + ", ".join(page["vocabulary_on_page"])
        )
    lines.append(
        "weak signal: careers pages lag reality; pair with an ATS board "
        "check once the company publishes one."
    )
    return "\n".join(lines)


__all__ = [
    "BoardError",
    "Watchlist",
    "analyze_careers_page_text",
    "analyze_roles",
    "deep_dive",
    "expand_aspiration",
    "internship_program_signal",
    "verdict",
]
