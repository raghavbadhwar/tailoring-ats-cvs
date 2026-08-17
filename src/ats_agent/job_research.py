"""Public-job capture and proposal batches backed by the local Scrapling CLI."""
from __future__ import annotations

import ipaddress
import json
import re
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit

from .hashing import sha256_path
from .review import write_review_bundle
from .providers import RewriteProvider
from .workflow import build_proposal, finalize_proposal

MAX_JOBS = 20
MAX_CONTEXT_URLS = 4


def _clean_capture(text: str) -> str:
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


def _validate_role_dossier(
    raw: object,
    captured_text: str,
    source: dict[str, object],
) -> list[dict[str, object]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("role_dossier must be a list of sourced requirements")
    validated: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("role_dossier requirements must be objects")
        text = item.get("text")
        span = item.get("source_span")
        if not isinstance(text, str) or not text.strip() or not isinstance(span, dict):
            raise ValueError("role_dossier requirements need text and source_span")
        start, end = span.get("start"), span.get("end")
        if not isinstance(start, int) or not isinstance(end, int) or captured_text[start:end] != text:
            raise ValueError("role_dossier requirement must match captured source text")
        terms = item.get("normalized_terms", [])
        if not isinstance(terms, list) or not all(isinstance(term, str) and term for term in terms):
            raise ValueError("role_dossier normalized_terms must be non-empty strings")
        validated.append(
            {
                "kind": str(item.get("kind") or "role_dossier"),
                "text": text,
                "normalized_terms": terms,
                "category": str(item.get("category") or "skill_tool"),
                "importance": str(item.get("importance") or "preferred"),
                "source_span": {"start": start, "end": end},
                "confidence": "source_verified",
                "source_url": str(source["url"]),
                "capture_sha256": str(source["sha256"]),
                "source_type": str(source["source_type"]),
                "source_excerpt": text,
                "dossier_source": "ai_job_search",
            }
        )
    return validated


def _public_url(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("research URLs must be strings")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("research URLs must be public HTTPS URLs without credentials")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError(f"research URL host cannot be resolved: {parsed.hostname}") from exc
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError("research URL host must resolve only to public IP addresses")
    return value


def _job_list(path: Path) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".md", ".markdown"}:
        jobs: object = [
            {
                "job_url": parts[0],
                **({"company": parts[1]} if len(parts) > 1 and parts[1] else {}),
                **({"role": parts[2]} if len(parts) > 2 and parts[2] else {}),
            }
            for line in text.splitlines()
            if line.strip().startswith("- [ ] ")
            for parts in [[part.strip() for part in line.strip()[6:].split("|")]]
        ]
    else:
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("job list must be valid JSON or Career-Ops Markdown") from exc
        jobs = raw.get("jobs") if isinstance(raw, dict) else raw
    if not isinstance(jobs, list) or not jobs or len(jobs) > MAX_JOBS:
        raise ValueError(f"job list must contain between 1 and {MAX_JOBS} jobs")
    normalized: list[dict[str, object]] = []
    ids: set[str] = set()
    for index, item in enumerate(jobs, 1):
        if not isinstance(item, dict):
            raise ValueError("each job list item must be an object")
        job_id = str(item.get("id") or f"job-{index}")
        if not job_id.replace("-", "").replace("_", "").isalnum() or job_id in ids:
            raise ValueError("job IDs must be unique letters, numbers, hyphens, or underscores")
        context_urls = item.get(
            "official_context_urls", item.get("context_urls", [])
        )
        if not isinstance(context_urls, list) or len(context_urls) > MAX_CONTEXT_URLS:
            raise ValueError(f"context_urls must contain at most {MAX_CONTEXT_URLS} URLs")
        normalized_job: dict[str, object] = {
                "id": job_id,
                "job_url": _public_url(item.get("job_url")),
                "context_urls": [_public_url(url) for url in context_urls],
                **{
                    key: value.strip()
                    for key in ("company", "role")
                    if isinstance((value := item.get(key)), str) and value.strip()
                },
            }
        source_status = item.get("status", "draft")
        if source_status not in {"draft", "expired"}:
            raise ValueError("job status must be draft or expired")
        normalized_job["source_status"] = source_status
        fallback = item.get("fallback")
        if fallback is not None:
            if not isinstance(fallback, dict) or not isinstance(
                fallback.get("description"), str
            ):
                raise ValueError("fallback must include a string description")
            required = ("source_url", "provider", "fetched_at")
            if any(not isinstance(fallback.get(key), str) or not fallback[key].strip() for key in required):
                raise ValueError("fallback must record source_url, provider, and fetched_at")
            normalized_job["fallback"] = {
                "description": fallback["description"].strip(),
                "source_url": _public_url(fallback["source_url"]),
                "provider": fallback["provider"].strip(),
                "fetched_at": fallback["fetched_at"].strip(),
                "source_type": "aggregator_fallback",
            }
        if "role_dossier" in item:
            normalized_job["role_dossier"] = item["role_dossier"]
        normalized.append(normalized_job)
        ids.add(job_id)
    return normalized


def _capture(url: str, destination: Path, *, source_type: str) -> dict[str, object]:
    executable = shutil.which("scrapling")
    if executable is None:
        raise ValueError(
            "Scrapling is required for job research; install it separately with "
            "uv tool install 'scrapling==0.4.12'"
        )
    completed = subprocess.run(
        [
            executable,
            "extract",
            "get",
            url,
            str(destination),
            "--timeout",
            "30",
            "--no-follow-redirects",
            "--no-stealthy-headers",
            "--ai-targeted",
        ],
        capture_output=True,
        text=True,
        shell=False,
        timeout=45,
    )
    if completed.returncode or not destination.is_file():
        detail = (completed.stderr or completed.stdout).strip()[-1000:]
        raise ValueError(f"Scrapling capture failed for {url}: {detail or 'no output'}")
    captured = destination.read_text(encoding="utf-8")
    cleaned = _clean_capture(captured)
    if len(re.findall(r"[A-Za-z0-9]+", cleaned)) < 8:
        raise ValueError(f"Scrapling capture was empty or insufficient for {url}")
    destination.write_text(cleaned, encoding="utf-8")
    return {
        "url": url,
        "path": str(destination),
        "sha256": sha256_path(destination),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "method": "scrapling_public_https",
        "source_type": source_type,
        "extraction_status": "captured",
    }


def _keyword_coverage(proposal: dict) -> list[dict[str, object]]:
    mappings = {item["requirement_id"]: item for item in proposal["requirement_evidence"]}
    return [
        {
            "requirement_id": requirement["id"],
            "keywords": requirement["normalized_terms"],
            "importance": requirement["importance"],
            "coverage": mappings[requirement["id"]]["coverage"],
            "evidence_ids": mappings[requirement["id"]]["evidence_ids"],
            "source_quality": {
                "source_type": requirement.get("source_type", "job_description"),
                "capture_sha256": requirement.get("capture_sha256"),
                "source_url": requirement.get("source_url"),
            },
        }
        for requirement in proposal["requirements"]
    ]


def _gap_recommendations(coverage: list[dict[str, object]]) -> list[dict[str, object]]:
    gaps = [
        {
            "requirement_id": item["requirement_id"],
            "keywords": item["keywords"],
            "importance": item["importance"],
            "recommendation": (
                "Build and document genuine candidate evidence for these keywords "
                "before adding them to the CV."
            ),
            "source_quality": item["source_quality"],
        }
        for item in coverage
        if item["coverage"] == "unsupported"
    ]
    return sorted(
        gaps,
        key=lambda item: (item["importance"] != "mandatory", item["requirement_id"]),
    )


def research_jobs(
    resume: Path,
    job_list: Path,
    out: Path,
    *,
    candidate_id: str = "candidate",
    evidence_paths: Iterable[Path] | None = None,
    context_urls: Iterable[str] | None = None,
    provider: RewriteProvider | None = None,
) -> dict[str, object]:
    """Capture public job pages, then create one approval-gated proposal per job."""

    jobs = _job_list(job_list.expanduser().resolve())
    evidence_paths = list(evidence_paths or [])
    batch_context_urls = [_public_url(url) for url in (context_urls or [])]
    if len(batch_context_urls) > MAX_CONTEXT_URLS:
        raise ValueError(f"context_urls must contain at most {MAX_CONTEXT_URLS} URLs")
    out = out.expanduser().resolve()
    if out.exists():
        raise ValueError("job research output directory must not already exist")
    out.mkdir(parents=True)
    results: list[dict[str, object]] = []
    for job in jobs:
        job_id = str(job["id"])
        identity: dict[str, object] = {
            key: job[key] for key in ("company", "role") if key in job
        }
        job_dir = out / "jobs" / job_id
        job_dir.mkdir(parents=True)
        if job.get("source_status") == "expired":
            results.append(
                {
                    "id": job_id,
                    **identity,
                    "status": "expired",
                    "job_url": job["job_url"],
                    "reason": "Marked expired in the read-only job export.",
                }
            )
            continue
        try:
            research: list[dict[str, object]] = []
            job_description = job_dir / "job-description.txt"
            try:
                research.append(
                    _capture(
                        str(job["job_url"]),
                        job_description,
                        source_type="official_job_page",
                    )
                )
            except ValueError as exc:
                fallback = job.get("fallback")
                if not isinstance(fallback, dict):
                    raise
                job_description.write_text(
                    str(fallback["description"]), encoding="utf-8"
                )
                research.append(
                    {
                        "url": str(job["job_url"]),
                        "method": "scrapling_public_https",
                        "source_type": "official_job_page",
                        "extraction_status": "failed",
                        "captured_at": datetime.now(timezone.utc).isoformat(),
                        "sha256": None,
                        "reason": str(exc),
                    }
                )
                research.append(
                    {
                        "url": str(fallback["source_url"]),
                        "path": str(job_description),
                        "sha256": sha256_path(job_description),
                        "captured_at": str(fallback["fetched_at"]),
                        "method": "ai_job_search_fallback",
                        "source_type": "aggregator_fallback",
                        "provider": str(fallback["provider"]),
                        "extraction_status": "fallback_used",
                    }
                )
            context_paths: list[Path] = []
            job_context_urls = job["context_urls"]
            assert isinstance(job_context_urls, list)
            merged_context_urls = list(dict.fromkeys([*job_context_urls, *batch_context_urls]))
            if len(merged_context_urls) > MAX_CONTEXT_URLS:
                raise ValueError(f"context_urls must contain at most {MAX_CONTEXT_URLS} URLs")
            for index, url in enumerate(merged_context_urls, 1):
                path = job_dir / f"context-{index}.txt"
                try:
                    research.append(
                        _capture(
                            str(url), path, source_type="official_company_context"
                        )
                    )
                    context_paths.append(path)
                except ValueError as exc:
                    research.append(
                        {
                            "url": str(url),
                            "method": "scrapling_public_https",
                            "source_type": "official_company_context",
                            "extraction_status": "failed",
                            "captured_at": datetime.now(timezone.utc).isoformat(),
                            "sha256": None,
                            "reason": str(exc),
                        }
                    )
            context_path = None
            if context_paths:
                context_path = job_dir / "company-context.md"
                context_path.write_text(
                    "\n\n".join(
                        f"Source: {item['url']}\n\n{Path(str(item['path'])).read_text(encoding='utf-8')}"
                        for item in research
                        if item.get("source_type") == "official_company_context"
                        and item.get("extraction_status") == "captured"
                    ),
                    encoding="utf-8",
                )
            requirement_source = next(
                item for item in research if item.get("path") == str(job_description)
            )
            proposal = build_proposal(
                resume,
                job_description,
                evidence_paths=evidence_paths,
                candidate_id=candidate_id,
                company_context=context_path,
                provider=provider,
                additional_requirements=_validate_role_dossier(
                    job.get("role_dossier"),
                    job_description.read_text(encoding="utf-8"),
                    requirement_source,
                ),
            )
            if proposal.get("status") != "draft":
                raise ValueError(str(proposal.get("reason") or "proposal was blocked"))
            job_text = job_description.read_text(encoding="utf-8")
            for requirement in proposal["requirements"]:
                span = requirement.get("source_span", {})
                start, end = span.get("start"), span.get("end")
                requirement["source_url"] = requirement_source["url"]
                requirement["capture_sha256"] = requirement_source["sha256"]
                requirement["source_type"] = requirement_source["source_type"]
                requirement["source_excerpt"] = (
                    job_text[start:end]
                    if isinstance(start, int) and isinstance(end, int)
                    else requirement["text"]
                )
            coverage = _keyword_coverage(proposal)
            proposal["research"] = {
                "mode": "public_scrapling",
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "sources": research,
            }
            proposal["screening_keyword_coverage"] = coverage
            proposal["gap_recommendations"] = _gap_recommendations(coverage)
            proposal = finalize_proposal(proposal)
            artifacts = write_review_bundle(proposal, job_dir)
            capture_manifest = job_dir / "capture-manifest.json"
            capture_manifest.write_text(
                json.dumps({"sources": research}, indent=2) + "\n",
                encoding="utf-8",
            )
            eligibility = [
                gate
                for gate in proposal.get("hard_gates", [])
                if gate.get("status") in {"unknown", "unmet"}
            ]
            results.append(
                {
                    "id": job_id,
                    **identity,
                    "status": "eligibility_warning" if eligibility else "draft",
                    "workflow_status": "draft",
                    "job_url": job["job_url"],
                    "proposal": artifacts["proposal"],
                    "review_html": artifacts["html"],
                    "capture_manifest": str(capture_manifest),
                    "keyword_coverage": coverage,
                    "gap_recommendations": proposal["gap_recommendations"],
                    "eligibility_warnings": eligibility,
                }
            )
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            results.append(
                {
                    "id": job_id,
                    **identity,
                    "status": "blocked_capture",
                    "reason": str(exc),
                }
            )
    payload = {"status": "draft", "job_count": len(results), "jobs": results}
    (out / "manifest.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {**payload, "manifest": str(out / "manifest.json")}
