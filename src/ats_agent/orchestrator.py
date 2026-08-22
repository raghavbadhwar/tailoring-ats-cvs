"""The one-door orchestrator: ``ats-agent tailor``.

Drives ingest → propose → explicit approval → apply → validate for one or
many roles inside a single session, with a crash-safe run journal,
digest-based idempotency, and tiered liveness verification for URL-sourced
drafts.

Modes are explicit (never auto-detected):

* ``--approve-from <file>`` — agent skin; selections come from a JSON file
  mapping ``{"<role-id>|*": ["C1:variant", ...]}``.
* ``--interactive`` — human conversation on stdin/stderr; tokens per role:
  ``C1`` ``C1:variant`` … , ``defaults``, ``skip``, ``quit``.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .boards import detect_board, fetch_board_url
from .capture import CaptureError, capture_url
from .doctor import _doctor
from .formatting import audit_file
from .ingestion import load
from .intake import jobs_from_json_export, resolve_source
from .review import write_review_bundle
from .summary import render_proposal_summary
from .review import build_approval_manifest
from .workflow import apply_manifest, build_proposal

JOURNAL_SCHEMA_VERSION = 1


class TailorBlocked(RuntimeError):
    """The requested tailoring session cannot proceed."""


@dataclass
class RoleSource:
    role_id: str
    company: str
    title: str
    job_url: str
    jd_text: str
    capture: dict[str, Any] | None = None


@dataclass
class RoleOutcome:
    role_id: str
    status: str
    title: str = ""
    company: str = ""
    message: str = ""
    output_document: str | None = None
    proposal_path: str | None = None
    warnings: list[str] = field(default_factory=list)


def _slug(text: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return (slug or fallback)[:40]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Journal:
    """Crash-safe, versioned run journal enabling resume and idempotency."""

    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, Any] = {
            "schema_version": JOURNAL_SCHEMA_VERSION,
            "roles": {},
        }
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                loaded = None
            if isinstance(loaded, dict) and loaded.get("schema_version") == JOURNAL_SCHEMA_VERSION:
                self.data = loaded

    def get(self, role_id: str) -> dict[str, Any]:
        return self.data["roles"].setdefault(role_id, {})

    def update(self, role_id: str, **fields: Any) -> None:
        entry = self.get(role_id)
        entry.update(fields)
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)


def _collect_roles(resolved: dict[str, Any], run_dir: Path, max_urls: int) -> list[RoleSource]:
    kind = resolved["kind"]
    roles: list[RoleSource] = []

    def add(company: str, title: str, url: str, jd_text: str,
            capture: dict[str, Any] | None = None) -> None:
        base = f"{company}-{title}" if (company or title) else url or title
        slug = _slug(base, f"role-{len(roles) + 1}")
        suffix = 2
        while any(r.role_id == slug for r in roles):
            slug = f"{slug}-{suffix}"
            suffix += 1
        roles.append(RoleSource(role_id=slug, company=company, title=title,
                                job_url=url, jd_text=jd_text, capture=capture))

    if kind == "jd_text":
        add("", "target-role", "", resolved["text"])
    elif kind == "json_export":
        for index, job in enumerate(jobs_from_json_export(resolved["payload"]), 1):
            add(job["company"], job["role"] or f"role-{index}",
                job["job_url"], job["description"])
    elif kind == "board_url":
        provider_token = resolved["board"]
        wanted = resolved["url"]
        fetched = fetch_board_url(resolved["url"])
        match = next((j for j in fetched if j["job_url"].rstrip("/") == wanted.rstrip("/")), None)
        chosen = match or (fetched[0] if fetched else None)
        if chosen is None:
            raise TailorBlocked(f"board feed for {provider_token[0]} returned no postings")
        provenance = {
            "method": f"ats_syndication_api:{chosen['provider']}",
            "fetched_at": chosen["fetched_at"],
            "sha256": _sha256_text(chosen["description"]),
            "url": wanted,
        }
        add(chosen["company"], chosen["role"], chosen["job_url"],
            chosen["description"], provenance)
    elif kind == "posting_url":
        destination = run_dir / "captures" / "posting-01.txt"
        provenance = capture_url(resolved["url"], destination, source_type="job_posting")
        add("", "captured-posting", resolved["url"],
            destination.read_text(encoding="utf-8"), provenance)
    elif kind == "url_list":
        entries = resolved["entries"][:max_urls]
        captures_dir = run_dir / "captures"
        for index, (url, company, role_name) in enumerate(entries, 1):
            detected = detect_board(url)
            if detected is not None:
                fetched = fetch_board_url(url)
                chosen = fetched[0] if fetched else None
                if chosen is None:
                    continue
                provenance = {
                    "method": f"ats_syndication_api:{chosen['provider']}",
                    "fetched_at": chosen["fetched_at"],
                    "sha256": _sha256_text(chosen["description"]),
                    "url": url,
                }
                add(company or chosen["company"], role_name or chosen["role"],
                    chosen["job_url"], chosen["description"], provenance)
            else:
                destination = captures_dir / f"posting-{index:02d}.txt"
                provenance = capture_url(url, destination, source_type="job_posting")
                add(company, role_name or "captured-posting", url,
                    destination.read_text(encoding="utf-8"), provenance)
    else:
        raise TailorBlocked(
            f"unsupported intake kind {kind!r}; use ats-agent research-jobs for "
            "Career-Ops lists"
        )
    return roles


def _normalize_selections(
    tokens: list[str],
    proposal: dict[str, Any],
    writer: Callable[[str], None],
) -> tuple[list[str], bool]:
    """Return ``(select_args, approved_anything)`` from raw user tokens."""

    changes = {c["id"]: c for c in proposal.get("changes", [])}
    selections: list[str] = []
    if "*" in [token.strip() for token in tokens]:
        tokens = [c["id"] for c in proposal.get("changes", [])
                  if c.get("kind") == "surface-evidence"]
    for token in tokens:
        token = token.strip().rstrip(",")
        if not token:
            continue
        if ":" in token:
            change_id, variant = token.split(":", 1)
        else:
            change_id, variant = token, ""
        change = changes.get(change_id)
        if change is None or change.get("kind") != "surface-evidence":
            writer(f"  ignoring {token}: not a supported change")
            continue
        variants = {v["id"] for v in change.get("variants", [])}
        if not variant:
            variant = str(change.get("default_variant")
                          or (change.get("variants") or [{}])[0].get("id") or "")
        elif variant not in variants:
            writer(f"  ignoring {token}: unknown variant '{variant}'")
            continue
        entry = f"{change_id}:{variant}"
        if entry not in selections:
            selections.append(entry)
    return selections, bool(selections)


def _approval_map(approve_from: Path) -> dict[str, Any]:
    payload = json.loads(approve_from.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TailorBlocked("--approve-from must contain a JSON object")
    return payload


def _selections_for_role(
    mapping: dict[str, Any],
    role_id: str,
    proposal: dict[str, Any],
    writer: Callable[[str], None],
) -> tuple[list[str], bool]:
    tokens: list[str] | None = None
    if "*" in mapping:
        tokens = list(mapping["*"])
    elif role_id in mapping:
        tokens = list(mapping[role_id])
    if tokens is None:
        return [], False
    return _normalize_selections([str(t) for t in tokens], proposal, writer)


def _liveness_check(
    capture: dict[str, Any],
    check_dir: Path,
) -> str:
    """Classify a captured posting as ``same``/``changed``/``dead``/``infra``."""

    try:
        fresh = capture_url(capture["url"], check_dir / "liveness.txt",
                            source_type="liveness")
    except CaptureError as exc:
        message = str(exc)
        if "HTTP 404" in message or "410" in message or "insufficient" in message:
            return "dead"
        return "infra"
    original_words = set(re.findall(r"[a-z0-9]+", Path(str(capture["path"])).read_text(encoding="utf-8").lower()))
    fresh_text = Path(str(fresh["path"])).read_text(encoding="utf-8")
    fresh_words = set(re.findall(r"[a-z0-9]+", fresh_text.lower()))
    overlap = len(original_words & fresh_words) / max(1, len(original_words))
    if fresh.get("sha256") == capture.get("sha256"):
        return "same"
    return "changed" if overlap >= 0.9 else "dead"


def _delivery_card(outcomes: list[RoleOutcome]) -> str:
    lines = ["════ Tailoring results ════"]
    ready = [o for o in outcomes if o.status == "tailored"]
    already = [o for o in outcomes if o.status == "already_tailored"]
    problems = [o for o in outcomes if o.status not in {"tailored", "already_tailored"}]

    for o in ready + already:
        label = "ready" if o.status == "tailored" else "already tailored"
        target = o.output_document or "(no output)"
        lines.append(f"✔ {o.title or o.role_id} — {label}: {target}")
    for o in problems:
        lines.append(f"✖ {o.title or o.role_id} — {o.status}: {o.message}")

    warnings = [w for o in outcomes for w in o.warnings]
    for warning in warnings:
        lines.append(f"⚠ {warning}")
    if ready:
        lines.append("Your original CV was never modified.")
        lines.append("Made a mistake? Delete an output above and re-run tailor.")
    return "\n".join(lines)


def tailor(
    cv_path: Path,
    source: str,
    *,
    candidate_id: str,
    run_dir: Path,
    evidence_paths: list[Path] | None = None,
    context_paths: list[Path] | None = None,
    approve_from: Path | None = None,
    interactive: bool = False,
    verify_live: bool = True,
    max_urls: int = 25,
    force: bool = False,
    rewrite_provider: Any = None,
    reader: Callable[[str], str] = input,
    writer: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    writer = writer or (lambda text: print(text, file=sys.stderr))

    doctor = _doctor(strict=True)
    if doctor.get("status") != "ready":
        raise TailorBlocked(str(doctor.get("message") or "engine failed its readiness check"))
    package_info = _doctor(strict=False).get("package")
    engine_version = str(package_info.get("version")) if isinstance(package_info, dict) else ""

    if interactive and approve_from is not None:
        raise TailorBlocked("choose either --interactive or --approve-from, not both")

    run_dir = run_dir.expanduser().resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    journal = Journal(run_dir / "journal.json")

    resolved = resolve_source(source)
    roles = _collect_roles(resolved, run_dir, max_urls)
    if not roles:
        raise TailorBlocked("source produced no roles to tailor against")

    approval_map = _approval_map(approve_from.resolve()) if approve_from else {}

    outcomes: list[RoleOutcome] = []
    for index, role in enumerate(roles, 1):
        writer(f"[{index}/{len(roles)}] {role.company} {role.title}".strip())
        role_dir = run_dir / role.role_id
        proposal_path = role_dir / "proposal.json"
        output_name = f"tailored-resume-{role.role_id}.docx"

        intake_digest = _sha256_text(
            json.dumps({
                "cv": _sha256_text(Path(cv_path).read_bytes().hex()),
                "jd": _sha256_text(role.jd_text),
                "evidence": [_sha256_text(p.read_bytes().hex()) for p in (evidence_paths or [])],
                "engine": engine_version,
            }, sort_keys=True),
        )

        prior = journal.get(role.role_id)
        already_done = False
        if (
            not force
            and not interactive
            and prior.get("stage") == "validated"
            and prior.get("intake_digest") == intake_digest
            and prior.get("output_document")
            and Path(prior["output_document"]).exists()
        ):
            if approve_from is not None:
                prior_proposal_path = Path(str(prior.get("proposal") or ""))
                try:
                    prior_proposal = json.loads(prior_proposal_path.read_text(encoding="utf-8"))
                    raw_tokens = [str(tok) for tok in
                                  approval_map.get(role.role_id, approval_map.get("*", []))]
                    requested, _ = _normalize_selections(raw_tokens, prior_proposal, writer)
                    already_done = sorted(requested) == sorted(prior.get("selections", []))
                except (OSError, json.JSONDecodeError):
                    already_done = False
        if (
            already_done
        ):
            outcomes.append(RoleOutcome(
                role.role_id,
                "already_tailored",
                title=role.title, company=role.company,
                output_document=prior["output_document"],
                message="identical inputs were already tailored in this run directory",
            ))
            continue

        jd_path = role_dir / "job-description.md"
        jd_path.parent.mkdir(parents=True, exist_ok=True)
        jd_path.write_text(role.jd_text, encoding="utf-8")

        proposal = build_proposal(
            Path(cv_path),
            jd_path,
            evidence_paths=[Path(p) for p in (context_paths or [])] + [Path(p) for p in (evidence_paths or [])],
            candidate_id=candidate_id,
            provider=rewrite_provider,
        )
        proposal_path.write_text(json.dumps(proposal, indent=2) + "\n", encoding="utf-8")
        write_review_bundle(proposal, role_dir, redacted=False)
        journal.update(role.role_id, stage="proposed", intake_digest=intake_digest,
                       proposal=str(proposal_path),
                       title=role.title, company=role.company)
        writer(render_proposal_summary(proposal))

        if approve_from is not None:
            selections, _any = _selections_for_role(approval_map, role.role_id, proposal, writer)
        else:
            selections = []
            while True:
                writer("  selections (e.g. C1:balanced C3 | defaults | skip | quit):")
                writer("  > ")
                raw = reader("")
                tokens = raw.strip().split()
                if tokens and tokens[0].lower() == "quit":
                    outcomes.append(RoleOutcome(role.role_id, "skipped",
                                                title=role.title, company=role.company,
                                                message="session ended by user"))
                    return _finish(outcomes, journal)
                if tokens and tokens[0].lower() == "skip":
                    break
                if tokens and tokens[0].lower() in {"defaults", "d"}:
                    supported = [c for c in proposal.get("changes", [])
                                 if c.get("kind") == "surface-evidence"]
                    tokens = [c["id"] for c in supported]
                selections, _any = _normalize_selections(tokens, proposal, writer)
                if selections or tokens:
                    break
        if not selections:
            outcomes.append(RoleOutcome(role.role_id, "skipped",
                                        title=role.title, company=role.company,
                                        message="no changes approved"))
            journal.update(role.role_id, stage="skipped")
            continue

        warnings: list[str] = []
        if role.capture and verify_live:
            verdict = _liveness_check(role.capture, role_dir)
            if verdict == "dead":
                outcomes.append(RoleOutcome(role.role_id, "blocked_liveness",
                                            title=role.title, company=role.company,
                                            message="the posting appears gone or fully rewritten; nothing was applied"))
                journal.update(role.role_id, stage="blocked_liveness")
                continue
            if verdict == "changed":
                if interactive:
                    writer("  ⚠ the posting changed since the draft was captured.")
                    writer("  continue applying? [y/N]")
                    answer = reader("").strip().lower()
                    if answer not in {"y", "yes"}:
                        outcomes.append(RoleOutcome(role.role_id, "skipped",
                                                    title=role.title, company=role.company,
                                                    message="user declined after posting changed"))
                        journal.update(role.role_id, stage="skipped_changed_posting")
                        continue
                warnings.append("posting changed since the draft was captured")
            elif verdict == "infra":
                warnings.append("could not re-check the live posting; continuing with the draft")

        selection_tuples: list[tuple[str, str | None]] = []
        for entry in selections:
            change_id, _, variant = entry.partition(":")
            selection_tuples.append((change_id, variant or None))
        manifest = build_approval_manifest(
            proposal,
            proposal_filename="proposal.json",
            selections=selection_tuples,
            output_document=output_name,
            document_mode="preserve",
            force=bool(force),
            max_character_growth=120,
        )
        approval_path = role_dir / "approval.json"
        approval_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        journal.update(role.role_id, stage="approved",
                       manifest=json.dumps(manifest, sort_keys=True),
                       selections=selections)

        applied: dict[str, Any] = apply_manifest(approval_path)
        journal.update(role.role_id, stage="applied",
                       output_document=str(applied.get("validation", {}).get("path") or (role_dir / output_name)))

        output_path = Path(str(applied.get("validation", {}).get("path") or (role_dir / output_name)))
        _ = load(output_path)
        audit_summary = audit_file(str(output_path))
        finding_count = len(audit_summary.get("findings", [])) if isinstance(audit_summary, dict) else 0
        journal.update(role.role_id, stage="validated",
                       output_document=str(output_path),
                       manifest_digest=_sha256_text(json.dumps(manifest, sort_keys=True)),
                       intake_digest=intake_digest,
                       completed_at=_now())
        outcomes.append(RoleOutcome(
            role.role_id, "tailored", title=role.title, company=role.company,
            output_document=str(output_path),
            proposal_path=str(proposal_path),
            warnings=warnings,
            message=f"valid output; {finding_count} layout note(s)",
        ))

    return _finish(outcomes, journal)


def _finish(outcomes: list[RoleOutcome], journal: Journal) -> dict[str, Any]:
    card = _delivery_card(outcomes)
    print(card, file=sys.stderr)
    return {
        "status": "completed" if outcomes else "no_roles",
        "card": card,
        "outcomes": [
            {
                "role_id": o.role_id,
                "status": o.status,
                "title": o.title,
                "company": o.company,
                "message": o.message,
                "output_document": o.output_document,
                "proposal_path": o.proposal_path,
                "warnings": o.warnings,
            }
            for o in outcomes
        ],
        "journal": str(journal.path),
    }
