"""Public-job capture and proposal batches backed by the local Scrapling CLI."""
from __future__ import annotations

import ipaddress
import json
import shutil
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from .hashing import compute_proposal_digest, sha256_path
from .review import write_review_bundle
from .workflow import build_proposal

MAX_JOBS = 20
MAX_CONTEXT_URLS = 4


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
        context_urls = item.get("context_urls", [])
        if not isinstance(context_urls, list) or len(context_urls) > MAX_CONTEXT_URLS:
            raise ValueError(f"context_urls must contain at most {MAX_CONTEXT_URLS} URLs")
        normalized.append(
            {
                "id": job_id,
                "job_url": _public_url(item.get("job_url")),
                "context_urls": [_public_url(url) for url in context_urls],
                **{
                    key: value.strip()
                    for key in ("company", "role")
                    if isinstance((value := item.get(key)), str) and value.strip()
                },
            }
        )
        ids.add(job_id)
    return normalized


def _capture(url: str, destination: Path) -> dict[str, str]:
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
    return {"url": url, "path": str(destination), "sha256": sha256_path(destination)}


def _keyword_coverage(proposal: dict) -> list[dict[str, object]]:
    mappings = {item["requirement_id"]: item for item in proposal["requirement_evidence"]}
    return [
        {
            "requirement_id": requirement["id"],
            "keywords": requirement["normalized_terms"],
            "importance": requirement["importance"],
            "coverage": mappings[requirement["id"]]["coverage"],
            "evidence_ids": mappings[requirement["id"]]["evidence_ids"],
        }
        for requirement in proposal["requirements"]
    ]


def _gap_recommendations(coverage: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "requirement_id": item["requirement_id"],
            "keywords": item["keywords"],
            "importance": item["importance"],
            "recommendation": (
                "Build and document genuine candidate evidence for these keywords "
                "before adding them to the CV."
            ),
        }
        for item in coverage
        if item["coverage"] == "unsupported"
    ]


def research_jobs(
    resume: Path,
    job_list: Path,
    out: Path,
    *,
    candidate_id: str = "candidate",
) -> dict[str, object]:
    """Capture public job pages, then create one approval-gated proposal per job."""

    jobs = _job_list(job_list.expanduser().resolve())
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
        try:
            research = [
                _capture(str(job["job_url"]), job_dir / "job-description.txt")
            ]
            context_paths: list[Path] = []
            context_urls = job["context_urls"]
            assert isinstance(context_urls, list)
            for index, url in enumerate(context_urls, 1):
                path = job_dir / f"context-{index}.txt"
                research.append(_capture(str(url), path))
                context_paths.append(path)
            context_path = None
            if context_paths:
                context_path = job_dir / "company-context.md"
                context_path.write_text(
                    "\n\n".join(
                        f"Source: {item['url']}\n\n{Path(item['path']).read_text(encoding='utf-8')}"
                        for item in research[1:]
                    ),
                    encoding="utf-8",
                )
            proposal = build_proposal(
                resume,
                job_dir / "job-description.txt",
                candidate_id=candidate_id,
                company_context=context_path,
            )
            if proposal.get("status") != "draft":
                raise ValueError(str(proposal.get("reason") or "proposal was blocked"))
            coverage = _keyword_coverage(proposal)
            proposal["research"] = {"mode": "public_scrapling", "sources": research}
            proposal["screening_keyword_coverage"] = coverage
            proposal["gap_recommendations"] = _gap_recommendations(coverage)
            proposal["proposal_digest"] = compute_proposal_digest(proposal)
            artifacts = write_review_bundle(proposal, job_dir)
            results.append(
                {
                    "id": job_id,
                    **identity,
                    "status": "draft",
                    "job_url": job["job_url"],
                    "proposal": artifacts["proposal"],
                    "review_html": artifacts["html"],
                    "keyword_coverage": coverage,
                    "gap_recommendations": proposal["gap_recommendations"],
                }
            )
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            results.append(
                {"id": job_id, **identity, "status": "blocked", "reason": str(exc)}
            )
    payload = {"status": "draft", "job_count": len(results), "jobs": results}
    (out / "manifest.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {**payload, "manifest": str(out / "manifest.json")}
