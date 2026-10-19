"""Resumable CV-first orchestration over search and the existing ATS engine."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .formatting import audit_file
from .hashing import sha256_path
from .ingestion import load
from .job_research import research_jobs
from .job_search import IntakeAnswers, intake_questions, search_public_jobs

ROLE_HINTS = (
    ("AI product", ("artificial intelligence", " ai ", "llm", "agent")),
    ("product operations", ("product", "operations", "roadmap", "stakeholder")),
    ("business analyst", ("business analysis", "data analysis", "analytics", "excel")),
    ("strategy analyst", ("strategy", "market research", "financial analysis")),
    ("business development", ("business development", "partnership", "sales")),
)


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _suggested_roles(text: str) -> list[str]:
    searchable = f" {text.casefold()} "
    matches = [role for role, terms in ROLE_HINTS if any(term in searchable for term in terms)]
    return matches[:3] or ["role aligned with demonstrated experience"]


def _new_state(resume: Path, out: Path, candidate_id: str) -> dict[str, object]:
    loaded = load(resume)
    roles = _suggested_roles(str(loaded["body_text"]))
    return {
        "schema_version": 1,
        "run_id": out.name,
        "candidate_id": candidate_id,
        "status": "needs_input",
        "resume": str(resume),
        "source_sha256": loaded["sha256"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "candidate_summary": {
            "word_count": loaded["word_count"],
            "extraction_status": loaded["quality"]["status"],
            "suggested_role_queries": roles,
            "formatting": audit_file(str(resume)),
        },
        "questions": intake_questions(roles),
        "approval_boundary": "explicit_role_and_change_selection_required",
    }


def _job_id(job: dict[str, object], used: set[str]) -> str:
    base = re.sub(
        r"[^a-z0-9]+",
        "-",
        f"{job.get('company', '')}-{job.get('title', '')}".casefold(),
    ).strip("-")[:60] or "job"
    candidate, index = base, 2
    while candidate in used:
        candidate, index = f"{base}-{index}", index + 1
    used.add(candidate)
    return candidate


def _handoff(search: dict[str, object], answers: IntakeAnswers) -> dict[str, object]:
    used: set[str] = set()
    jobs: list[dict[str, object]] = []
    raw_jobs = search.get("jobs", [])
    assert isinstance(raw_jobs, list)
    for raw in raw_jobs:
        assert isinstance(raw, dict)
        haystack = " ".join(
            str(raw.get(key) or "")
            for key in ("title", "company", "location", "description")
        ).casefold()
        # ponytail: exact text only; add structured classification after precision is measured.
        possible_deal_breakers = [
            value for value in answers.deal_breakers if value.casefold() in haystack
        ]
        item: dict[str, object] = {
            "id": _job_id(raw, used),
            "company": raw["company"],
            "role": raw["title"],
            "job_url": raw["job_url"],
            "discovery": {
                key: raw.get(key)
                for key in ("source", "location", "work_mode", "posted_at", "eligibility_note")
            },
        }
        assert isinstance(item["discovery"], dict)
        item["discovery"]["possible_deal_breaker_matches"] = possible_deal_breakers
        description = raw.get("description")
        if isinstance(description, str) and description.strip():
            item["fallback"] = {
                "description": description,
                "source_url": raw["provider_url"],
                "provider": str(raw["source"]),
                "fetched_at": search["captured_at"],
            }
        jobs.append(item)
    return {"jobs": jobs}


def _intake_evidence(answers: IntakeAnswers) -> str:
    modes = ["on-site" if mode == "in-person" else mode for mode in answers.work_modes]
    lines = [
        "# Candidate-confirmed search and eligibility facts",
        f"- Authorized to work in {answers.work_authorization}.",
        f"- Acceptable work modes: {', '.join(modes)}.",
        f"- Relocation preference: {answers.relocation}.",
        f"- Candidate availability: {answers.availability}.",
    ]
    if answers.sponsorship == "required":
        lines.append("- I require visa sponsorship.")
    elif answers.sponsorship == "not-required":
        lines.append("- I do not require visa sponsorship.")
    return "\n".join(lines) + "\n"


def _ranking(
    research: dict[str, object],
    handoff: dict[str, object],
    answers: IntakeAnswers,
) -> list[dict[str, object]]:
    ranking: list[dict[str, object]] = []
    handoff_jobs = handoff.get("jobs", [])
    assert isinstance(handoff_jobs, list)
    discovery_by_id = {
        str(job["id"]): job.get("discovery", {})
        for job in handoff_jobs
        if isinstance(job, dict) and "id" in job
    }
    raw_jobs = research.get("jobs", [])
    assert isinstance(raw_jobs, list)
    for job in raw_jobs:
        assert isinstance(job, dict)
        coverage = job.get("keyword_coverage", [])
        if not isinstance(coverage, list) or not coverage:
            score = 0
        else:
            points = {"direct": 3, "transferable": 2, "unsupported": 0}
            score = round(
                100
                * sum(points.get(str(item.get("coverage")), 0) for item in coverage if isinstance(item, dict))
                / (3 * len(coverage))
            )
        ranking.append(
            {
                "id": job.get("id"),
                "company": job.get("company"),
                "role": job.get("role"),
                "status": job.get("status"),
                "supported_requirement_coverage": score,
                "discovery": discovery_by_id.get(str(job.get("id")), {}),
                "candidate_deal_breakers": answers.deal_breakers,
                "eligibility_warnings": job.get("eligibility_warnings", []),
                "proposal": job.get("proposal"),
                "review_html": job.get("review_html"),
            }
        )
    def key(item: dict[str, object]) -> tuple[bool, int, str]:
        discovery = item.get("discovery")
        matches = discovery.get("possible_deal_breaker_matches", []) if isinstance(discovery, dict) else []
        return (
            bool(matches),
            -int(str(item["supported_requirement_coverage"])),
            str(item.get("company")),
        )

    return sorted(ranking, key=key)


def run_journey(
    resume: Path,
    out: Path,
    *,
    candidate_id: str = "candidate",
    answers_path: Path | None = None,
) -> dict[str, object]:
    """Start or resume one CV-first run; never approve or edit a CV."""

    resume = resume.expanduser().resolve()
    out = out.expanduser().resolve()
    state_path = out / "journey.json"
    if not state_path.exists():
        if out.exists():
            raise ValueError("journey output directory already exists without journey state")
        out.mkdir(parents=True)
        state = _new_state(resume, out, candidate_id)
        _write(state_path, state)
    else:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("resume") != str(resume) or state.get("candidate_id") != candidate_id:
            raise ValueError("journey resume or candidate ID does not match the existing run")
        if state.get("source_sha256") != sha256_path(resume):
            raise ValueError("source CV changed; start a new journey run")
        if state.get("status") == "research_complete":
            return state

    if answers_path is None:
        return state
    answers = IntakeAnswers.model_validate_json(
        answers_path.expanduser().resolve().read_text(encoding="utf-8")
    )
    answers_artifact = out / "intake.json"
    _write(answers_artifact, answers.model_dump(mode="json"))
    evidence_artifact = out / "intake-evidence.md"
    evidence_artifact.write_text(_intake_evidence(answers), encoding="utf-8")
    state.update(
        {
            "status": "searching",
            "answers": str(answers_artifact),
            "intake_evidence": str(evidence_artifact),
        }
    )
    _write(state_path, state)

    jobs_path = out / "jobs.json"
    raw_path = out / "jobs.raw.json"
    if not jobs_path.exists():
        search = search_public_jobs(answers)
        _write(raw_path, search)
        if not search.get("jobs"):
            state.update(
                {
                    "status": "blocked",
                    "reason": "No retrievable jobs were returned by the bounded public sources.",
                    "search_failures": search.get("failures", []),
                }
            )
            _write(state_path, state)
            return state
        _write(jobs_path, _handoff(search, answers))
    handoff = json.loads(jobs_path.read_text(encoding="utf-8"))
    state.update({"status": "search_complete", "jobs": str(jobs_path), "raw_jobs": str(raw_path)})
    _write(state_path, state)

    research_out = out / f"research-{uuid4().hex[:8]}"
    research = research_jobs(
        resume,
        jobs_path,
        research_out,
        candidate_id=candidate_id,
        evidence_paths=[evidence_artifact],
    )
    ranking_path = out / "ranking.json"
    ranking = _ranking(research, handoff, answers)
    _write(ranking_path, {"jobs": ranking})
    if sha256_path(resume) != state["source_sha256"]:
        raise ValueError("source CV changed during journey execution")
    state.update(
        {
            "status": "research_complete",
            "research_manifest": research["manifest"],
            "ranking": str(ranking_path),
            "ranked_jobs": ranking,
            "approval_boundary": "explicit_role_and_change_selection_required",
        }
    )
    _write(state_path, state)
    return state
