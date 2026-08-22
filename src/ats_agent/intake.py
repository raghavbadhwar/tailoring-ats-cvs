"""Invisible intake: classify a tailor source and normalize it to roles.

Accepted shapes, detected automatically:

- JSON export from public job-list research (``{"jobs": [...]}`` or list)
- Career-Ops Markdown with pending ``- [ ] url | Company | Role`` rows
- Plain-text URL list: one https URL per line, optional trailing
  ``| Company | Role``
- ATS board URL (Greenhouse / Lever / Ashby) or raw posting/JD text
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .boards import BoardError, detect_board

URL_LINE = re.compile(r"(https://[^\s|]+)", re.IGNORECASE)
CAREER_OPS_ROW = re.compile(r"^\s*-\s*\[\s*\]\s*(\S+)")


@dataclass
class Role:
    role_id: str
    company: str
    title: str
    job_url: str
    description: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)


def parse_url_lines(text: str) -> list[tuple[str, str, str]]:
    """Return ``(url, company, role)`` triples from a plain-text URL list."""

    entries: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = URL_LINE.search(line)
        if not match:
            continue
        url = match.group(1)
        if url.lower() in seen:
            continue
        seen.add(url.lower())
        remainder = line[match.end():].strip()
        company, role_name = "", ""
        if remainder.startswith("|"):
            parts = [part.strip() for part in remainder.strip("|").split("|")]
            if len(parts) >= 1:
                company = parts[0]
            if len(parts) >= 2:
                role_name = parts[1]
        entries.append((url, company, role_name))
    return entries


def looks_like_career_ops(text: str) -> bool:
    for line in text.splitlines():
        row = CAREER_OPS_ROW.match(line)
        if row and URL_LINE.search(line):
            return True
    return False


def looks_like_url_list(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    if not lines:
        return False
    url_lines = sum(1 for line in lines if URL_LINE.search(line))
    return url_lines == len(lines)


def classify_text(text: str) -> str:
    """Classify raw source text without touching the network."""

    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(payload, dict) and ("jobs" in payload or "seen" in payload):
                return "json_export"
            if isinstance(payload, list):
                return "json_export"
    if looks_like_career_ops(text):
        return "career_ops"
    if looks_like_url_list(text):
        return "url_list"
    return "jd_text"


def jobs_from_json_export(payload: Any) -> list[dict[str, Any]]:
    """Normalize research-export shapes into the standard jobs list."""

    jobs_raw: list[Any] = []
    if isinstance(payload, dict) and isinstance(payload.get("jobs"), list):
        jobs_raw = payload["jobs"]
    elif isinstance(payload, list):
        jobs_raw = payload
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(jobs_raw, 1):
        if not isinstance(item, dict):
            continue
        job_url = str(item.get("job_url") or item.get("url") or item.get("hostedUrl") or "")
        if not job_url:
            continue
        fallback = item.get("fallback") or {}
        description = str(
            item.get("description")
            or fallback.get("description")
            or ""
        )
        normalized.append({
            "id": str(item.get("id") or f"role-{index}"),
            "company": str(item.get("company") or ""),
            "role": str(item.get("role") or item.get("title") or ""),
            "job_url": job_url,
            "description": description,
            "source": "json_export",
            "provider": "",
            "fetched_at": str(fallback.get("fetched_at") or ""),
        })
    return normalized


def resolve_source(source: str) -> dict[str, Any]:
    """Resolve any accepted tailor source into ``{"kind", ...}``.

    Network-touching kinds (``url_list``, ``board_url``) are returned as
    instructions; the orchestrator performs captures/policy checks.
    """

    stripped = source.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            payload = None
        if payload is not None:
            return {"kind": "json_export", "payload": payload}

    single_board = None
    if stripped.startswith("http://") or stripped.startswith("https://"):
        single_board = detect_board(stripped)
        if single_board is not None:
            return {"kind": "board_url", "url": stripped, "board": single_board}
        return {"kind": "posting_url", "url": stripped}

    try:
        text = Path_read(source)
    except OSError:
        return {"kind": "jd_text", "text": source}

    kind = classify_text(text)
    if kind == "json_export":
        return {"kind": "json_export", "payload": json.loads(text)}
    if kind == "url_list":
        entries = parse_url_lines(text)
        plain = [entry for entry in entries if not detect_board(entry[0])]
        if plain:
            raise BoardError(
                "URL list contains non-ATS URLs; only Greenhouse/Lever/Ashby "
                "board URLs are supported for structured intake."
            )
        return {"kind": "url_list", "entries": entries}
    if kind == "career_ops":
        return {"kind": "career_ops", "text": text}
    return {"kind": "jd_text", "text": text}


def Path_read(path_text: str) -> str:
    from pathlib import Path

    path = Path(path_text).expanduser()
    return path.read_text(encoding="utf-8")
