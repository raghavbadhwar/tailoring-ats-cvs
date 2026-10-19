"""The one-door orchestrator: ``ats-agent tailor``.

Drives ingest → propose → explicit approval → apply → validate for one or
many roles inside a single session, with a crash-safe run journal,
digest-based idempotency, and tiered liveness verification for URL-sourced
drafts.

Modes are explicit (never auto-detected):

* No approval arguments — persist proposals and return for review.
* ``--approve-from <file>`` — consume a persisted approval manifest or index.
* ``--interactive`` — human conversation on stdin/stderr; tokens per role:
  ``C1:variant`` … , ``skip``, ``quit``.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from .artifacts import assert_run_directory_is_separate, atomic_write_text
from .boards import BoardError, detect_board, fetch_board_url
from . import capture as capture_engine
from .capture import CaptureError, capture_cached
from .doctor import _doctor
from .formatting import audit_file
from .hashing import sha256_path, verify_proposal_digest
from .ingestion import load
from .intake import jobs_from_json_export, resolve_source
from .models import ApprovalManifest
from .providers import RewriteCache, rewrite_provider_identity
from .review import write_review_bundle
from .summary import render_proposal_summary
from .review import build_approval_manifest
from .workflow import ResearchFreshnessError, apply_manifest, build_proposal, finalize_proposal

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
    capture_error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


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


def _engine_identity(doctor: dict[str, Any]) -> dict[str, object]:
    """Return the approval-relevant engine identity without a volatile venv path.

    ``uv run --isolated`` intentionally creates a fresh virtual-environment
    directory for each CLI invocation.  That interpreter pathname is not an
    engine change, while the package identity, Python version, resolved engine
    source path, source digest, and document-capability availability are.  Do
    not fall back to a version string: an incomplete doctor response blocks
    approval/resume rather than weakening its input binding.
    """

    runtime = doctor.get("runtime")
    package = doctor.get("package")
    optional_dependencies = doctor.get("optional_dependencies")
    if not isinstance(runtime, dict) or not isinstance(package, dict) or not isinstance(optional_dependencies, dict):
        raise TailorBlocked("doctor did not report a stable engine identity")
    engine_path = runtime.get("engine_path")
    source_sha256 = runtime.get("source_sha256")
    python_version = doctor.get("python")
    package_name = package.get("name")
    package_version = package.get("version")
    if (
        not isinstance(engine_path, str)
        or not isinstance(source_sha256, str)
        or re.fullmatch(r"[0-9a-fA-F]{64}", source_sha256) is None
        or not isinstance(python_version, str)
        or not python_version
        or not isinstance(package_name, str)
        or not package_name
        or not isinstance(package_version, str)
        or not package_version
        or any(not isinstance(key, str) or not isinstance(value, bool)
               for key, value in optional_dependencies.items())
    ):
        raise TailorBlocked("doctor did not report a stable engine identity")
    try:
        resolved_engine_path = str(Path(engine_path).expanduser().resolve())
    except OSError as exc:
        raise TailorBlocked("doctor engine path cannot be resolved") from exc
    return {
        "package": {"name": package_name, "version": package_version},
        "python": python_version,
        "engine_path": resolved_engine_path,
        "source_sha256": source_sha256.lower(),
        "optional_dependencies": dict(sorted(optional_dependencies.items())),
    }


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
            if (isinstance(loaded, dict) and loaded.get("schema_version") == JOURNAL_SCHEMA_VERSION
                    and isinstance(loaded.get("roles"), dict)):
                self.data = loaded
            else:
                raise TailorBlocked("journal is corrupt or unsupported; use a fresh run directory")

    def get(self, role_id: str) -> dict[str, Any]:
        return self.data["roles"].setdefault(role_id, {})

    def update(self, role_id: str, **fields: Any) -> None:
        entry = self.get(role_id)
        entry.update(fields)
        self.save()

    def save(self) -> None:
        atomic_write_text(
            self.path,
            json.dumps(self.data, indent=1, sort_keys=True),
        )


def _collect_roles(
    resolved: dict[str, Any], run_dir: Path, max_urls: int,
    on_ready: Callable[[RoleSource], None] | None = None,
) -> list[RoleSource]:
    """Collect bounded roles; deliver completed captures without head-of-line blocking."""

    if max_urls < 1:
        raise TailorBlocked("max_urls must be positive")
    roles: list[RoleSource] = []
    pending: list[RoleSource] = []
    feeds: dict[tuple[str, str], list[dict[str, Any]]] = {}
    cache_dir = run_dir / ".capture-cache"

    def add(job: dict[str, Any], *, captured: bool = False) -> None:
        url = str(job.get("job_url") or "")
        identity = str(job.get("id") or ("job-" + _sha256_text(url)[:16] if url else "target-role"))
        role_id = identity if re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", identity) else "job-" + _sha256_text(identity)[:16]
        status = str(job.get("import_status") or job.get("source_status") or "draft")
        error = job.get("reason") if status in {"blocked_import", "excluded_scope"} else None
        if any(role.role_id == role_id for role in roles):
            role_id += f"-duplicate-{len(roles) + 1}"
            status, error = "blocked_import", "duplicate source role identity"
        if status == "expired":
            error = "posting is marked expired in the source export"
        elif len(roles) >= max_urls and status == "draft":
            status, error = "imported", f"outside the explicit {max_urls}-role capture limit"
        role = RoleSource(
            role_id, str(job.get("company") or ""), str(job.get("role") or "target-role"),
            url, str(job.get("description") or "") if captured else "",
            capture_error=str(error) if error else None, metadata=dict(job),
        )
        role.metadata["source_status"] = status
        roles.append(role)
        if role.capture_error:
            if on_ready:
                on_ready(role)
        elif captured:
            if url:
                path = run_dir / "captures" / f"{role_id}.txt"
                atomic_write_text(path, role.jd_text)
                role.capture = {
                    "url": url, "board_url": job.get("board_url"), "path": str(path),
                    "sha256": _sha256_text(role.jd_text), "captured_at": job.get("fetched_at"),
                    "method": f"ats_syndication_api:{job.get('provider')}",
                    "source_type": "job_posting", "extraction_status": "captured",
                }
            if on_ready:
                on_ready(role)
        else:
            pending.append(role)

    def board(url: str, company: str = "", title: str = "") -> None:
        detected = detect_board(url)
        if detected is None:
            add({"job_url": url, "company": company, "role": title})
            return
        try:
            if detected not in feeds:
                feeds[detected] = fetch_board_url(url)
            jobs = feeds[detected]
            exact = [job for job in jobs if str(job.get("job_url", "")).rstrip("/") == url.rstrip("/")]
            root = len(urlsplit(url).path.strip("/").split("/")) == 1
            selected = exact or ([job for job in jobs if not title or str(job.get("role", "")).casefold() == title.casefold()] if root else [])
            if not selected:
                add({"job_url": url, "company": company, "role": title or "requested-posting",
                     "import_status": "blocked_import", "reason": "requested board posting was not found"})
            for job in selected:
                add({**job, "board_url": url}, captured=True)
        except BoardError as exc:
            add({"job_url": url, "company": company, "role": title,
                 "import_status": "blocked_import", "reason": str(exc)})

    kind = resolved["kind"]
    if kind == "jd_text":
        add({"id": "target-role", "description": resolved["text"]}, captured=True)
    elif kind == "json_export":
        for job in jobs_from_json_export(resolved["payload"]):
            add(job)
    elif kind in {"board_url", "posting_url"}:
        board(resolved["url"])
    elif kind == "url_list":
        for url, company, title in resolved["entries"]:
            board(url, company, title)
    else:
        raise TailorBlocked(f"unsupported intake kind {kind!r}")

    def capture(role: RoleSource) -> None:
        destination = run_dir / "captures" / f"{role.role_id}.txt"
        sources: list[dict[str, Any]] = []
        contract = role.metadata.get("official_host_contract")
        source_type = "third_party_job_page"
        if isinstance(contract, dict):
            try:
                verified = capture_cached(
                    str(contract["official_host_verification_url"]), cache_dir,
                    source_type="official_company_context",
                    destination=destination.with_suffix(".verification.txt"),
                )
                sources.append(verified)
                source_type = "official_job_page"
            except CaptureError:
                pass
        try:
            role.capture = capture_cached(role.job_url, cache_dir, source_type=source_type, destination=destination)
        except CaptureError:
            fallback = role.metadata.get("fallback")
            if not isinstance(fallback, dict):
                raise
            destination.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(destination, str(fallback["description"]))
            role.capture = {
                "url": fallback["source_url"], "path": str(destination),
                "sha256": sha256_path(destination), "captured_at": fallback["fetched_at"],
                "method": "ai_job_search_fallback", "source_type": "aggregator_fallback",
                "provider": fallback["provider"], "extraction_status": "fallback_used",
            }
        role.jd_text = destination.read_text(encoding="utf-8")
        sources.append(role.capture)
        for index, url in enumerate(role.metadata.get("context_urls", [])):
            try:
                sources.append(capture_cached(
                    str(url), cache_dir, source_type="official_company_context",
                    destination=destination.with_suffix(f".context-{index}.txt"),
                ))
            except CaptureError as exc:
                sources.append({"url": url, "source_type": "official_company_context",
                                "extraction_status": "failed", "reason": str(exc)})
        role.metadata["sources"] = sources

    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks = {pool.submit(capture, role): role for role in pending}
        for future in as_completed(tasks):
            role = tasks[future]
            try:
                future.result()
            except (CaptureError, OSError, ValueError) as exc:
                role.capture_error = str(exc)
            if on_ready:
                on_ready(role)
    return roles

def _normalize_selections(
    tokens: list[str],
    proposal: dict[str, Any],
    writer: Callable[[str], None],
) -> tuple[list[str], bool]:
    """Return ``(select_args, approved_anything)`` from raw user tokens."""

    changes = {c["id"]: c for c in proposal.get("changes", [])}
    selections: list[str] = []
    for token in tokens:
        token = token.strip().rstrip(",")
        if not token:
            continue
        if token in {"*", "defaults", "d"}:
            raise TailorBlocked(
                "blanket approvals are not supported; name each change and variant"
            )
        if ":" in token:
            change_id, variant = token.split(":", 1)
        else:
            raise TailorBlocked(
                f"{token} needs an explicit variant, for example {token}:balanced"
            )
        change = changes.get(change_id)
        if change is None or not change.get("supported"):
            raise TailorBlocked(f"{token} is not a supported change")
        variants = {v["id"] for v in change.get("variants", [])}
        if not variant or variant not in variants:
            raise TailorBlocked(f"{token} has an unknown variant")
        entry = f"{change_id}:{variant}"
        if entry not in selections:
            selections.append(entry)
    return selections, bool(selections)


def _approval_paths(approve_from: Path | None) -> dict[str | None, Path]:
    """Load one approval manifest or a batch index of manifest paths.

    Selection maps were adapter policy.  They are deliberately rejected: only
    regular digest-bound ApprovalManifest files can authorize an apply.
    """

    if approve_from is None:
        return {}
    path = approve_from.expanduser().resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TailorBlocked("--approve-from must contain an approval manifest or batch index")
    if "proposal" in payload:
        ApprovalManifest.model_validate(payload)
        return {None: path}
    refs = payload.get("approval_manifests")
    if (
        payload.get("schema_version") == 1
        and isinstance(refs, dict)
        and all(isinstance(role_id, str) and isinstance(value, str) for role_id, value in refs.items())
    ):
        return {
            role_id: (path.parent / value).expanduser().resolve()
            for role_id, value in refs.items()
        }
    raise TailorBlocked(
        "legacy token selection maps are not approvals; run ats-agent approve "
        "for each persisted proposal, then pass that manifest or a batch index"
    )


def _approval_for_role(
    approval_paths: dict[str | None, Path],
    role_id: str,
    proposal_path: Path,
    proposal_digest: str,
) -> Path | None:
    manifest_path = approval_paths.get(role_id, approval_paths.get(None))
    if manifest_path is None:
        return None
    try:
        approval = ApprovalManifest.model_validate(
            json.loads(manifest_path.read_text(encoding="utf-8"))
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise TailorBlocked(f"invalid approval manifest for {role_id}: {exc}") from exc
    referenced = (manifest_path.parent / approval.proposal).expanduser().resolve()
    if referenced != proposal_path.resolve():
        raise TailorBlocked(
            f"approval manifest for {role_id} references a different persisted proposal"
        )
    if approval.proposal_digest != proposal_digest:
        raise TailorBlocked(
            f"approval manifest for {role_id} has a different proposal digest; review again"
        )
    return manifest_path


def _verified_delivery(prior: dict[str, Any], intake_digest: str, requested: Path | None = None) -> bool:
    """Return true only when a completed journal entry still has its evidence."""

    if prior.get("stage") != "validated" or prior.get("intake_digest") != intake_digest:
        return False
    paths = {
        key: Path(str(prior.get(key) or ""))
        for key in ("proposal", "approval_manifest", "output_document", "receipt")
    }
    if any(not path.is_file() for path in paths.values()):
        return False
    try:
        proposal = json.loads(paths["proposal"].read_text(encoding="utf-8"))
        verify_proposal_digest(proposal)
        approval = ApprovalManifest.model_validate(
            json.loads(paths["approval_manifest"].read_text(encoding="utf-8"))
        )
        receipt = json.loads(paths["receipt"].read_text(encoding="utf-8"))
        if requested is not None and requested.read_bytes() != paths["approval_manifest"].read_bytes():
            return False
        if requested is not None:
            _approval_for_role({None: requested}, "completed role", paths["proposal"], proposal["proposal_digest"])
            if approval.output and (requested.parent / approval.output).resolve() != paths["output_document"].resolve():
                return False
        if prior.get("approval_sha256") != sha256_path(paths["approval_manifest"]):
            return False
        if prior.get("receipt_sha256") != sha256_path(paths["receipt"]):
            return False
        if (paths["approval_manifest"].parent / approval.proposal).resolve() != paths["proposal"].resolve():
            return False
        for artifact in proposal.get("artifacts", []):
            if sha256_path(Path(artifact["path"])) != artifact["sha256"]:
                return False
        load(paths["output_document"])
    except (OSError, ValueError, KeyError, TypeError, TailorBlocked, json.JSONDecodeError):
        return False
    return (
        approval.proposal_digest == proposal.get("proposal_digest")
        and receipt.get("proposal_digest") == proposal.get("proposal_digest")
        and receipt.get("output_sha256") == sha256_path(paths["output_document"])
    )


def _liveness_check(
    capture: dict[str, Any],
    check_dir: Path,
) -> str:
    """Classify a captured posting as ``same``/``changed``/``dead``/``infra``."""

    if str(capture.get("method") or "").startswith("ats_syndication_api:"):
        board_url = capture.get("board_url")
        if not isinstance(board_url, str):
            return "infra"
        try:
            refreshed = fetch_board_url(board_url)
        except BoardError:
            return "infra"
        current = next(
            (job for job in refreshed if job.get("job_url") == capture.get("url")),
            None,
        )
        if current is None:
            return "dead"
        return "same" if _sha256_text(str(current.get("description") or "")) == capture.get("sha256") else "changed"
    original_path = capture.get("path")
    if not isinstance(original_path, str) or not Path(original_path).is_file():
        return "infra"
    try:
        fresh = capture_engine.capture_url(capture["url"], check_dir / "liveness.txt",
                            source_type="liveness")
    except CaptureError as exc:
        message = str(exc)
        if "HTTP 404" in message or "410" in message or "insufficient" in message:
            return "dead"
        return "infra"
    original_words = set(re.findall(r"[a-z0-9]+", Path(original_path).read_text(encoding="utf-8").lower()))
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
        label = "content validated; layout unverified" if o.status == "tailored" else "already tailored; layout unverified"
        target = o.output_document or "(no output)"
        lines.append(f"✔ {o.title or o.role_id} — {label}: {target}")
    for o in problems:
        lines.append(f"✖ {o.title or o.role_id} — {o.status}: {o.message}")

    warnings = [w for o in outcomes for w in o.warnings]
    for warning in warnings:
        lines.append(f"⚠ {warning}")
    if ready:
        lines.append("Your original CV was never modified.")
        lines.append("Review the document layout before delivery; keep the output and receipt together.")
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
    if interactive and approve_from is not None:
        raise TailorBlocked("choose either --interactive or --approve-from, not both")
    doctor = _doctor(strict=False)
    if doctor.get("status") != "ready":
        raise TailorBlocked(str(doctor.get("message") or "engine failed its readiness check"))
    engine_identity = _engine_identity(doctor)
    evidence_paths = [Path(path) for path in (evidence_paths or [])]
    context_paths = [Path(path) for path in (context_paths or [])]
    if len(context_paths) > 1:
        raise TailorBlocked("tailor accepts at most one company-context file")
    company_context = context_paths[0] if context_paths else None
    run_dir = run_dir.expanduser().resolve()
    try:
        assert_run_directory_is_separate(
            run_dir,
            (Path(cv_path), *evidence_paths, *context_paths),
        )
    except ValueError as exc:
        raise TailorBlocked(str(exc)) from exc
    run_dir.mkdir(parents=True, exist_ok=True)
    journal = Journal(run_dir / "journal.json")
    approval_paths = _approval_paths(approve_from)
    resolved = resolve_source(source)
    provider_identity = None if rewrite_provider is None else rewrite_provider_identity(rewrite_provider)
    source_digest = _sha256_text(json.dumps({
        "source": resolved, "candidate_id": candidate_id, "max_urls": max_urls,
        "inputs": [(str(path.expanduser().resolve()), sha256_path(path))
                   for path in [Path(cv_path), *evidence_paths, *context_paths]],
        "provider": provider_identity, "engine": engine_identity,
    }, sort_keys=True))
    if approval_paths and journal.data.get("source_digest") != source_digest:
        raise TailorBlocked("inputs or engine changed; prepare a fresh review before approving")
    saved = journal.data.get("source_roles", [])
    restore = (journal.data.get("source_digest") == source_digest
               and journal.data.get("collection_complete") is True and isinstance(saved, list))
    if restore and journal.data.get("source_roles_digest") != _sha256_text(json.dumps(saved, sort_keys=True)):
        raise TailorBlocked("persisted role sources are corrupt; prepare a fresh run")
    journal.data.update(source_digest=source_digest, collection_complete=False, source_roles=[])
    outcomes: list[RoleOutcome] = []
    candidate_cache: dict = {}
    rewrite_cache = RewriteCache()

    def process_role(role: RoleSource) -> None:
        writer(f"[{len(outcomes) + 1}] {role.company} {role.title}".strip())
        role_dir = run_dir / role.role_id
        proposal_path = role_dir / "proposal.json"
        if role.capture_error:
            outcomes.append(RoleOutcome(
                role.role_id,
                str(role.metadata.get("source_status")) if role.metadata.get("source_status") in {"blocked_import", "excluded_scope", "expired", "imported"} else "blocked_capture",
                title=role.title,
                company=role.company,
                message=role.capture_error,
            ))
            journal.update(role.role_id, stage="blocked_capture", capture=role.capture)
            return
        intake_digest = _sha256_text(json.dumps({
            "cv": {"path": str(Path(cv_path).expanduser().resolve()), "sha256": sha256_path(Path(cv_path))},
            "jd": _sha256_text(role.jd_text),
            "candidate_id": candidate_id,
            "evidence": [{"path": str(path.expanduser().resolve()), "sha256": sha256_path(path)} for path in evidence_paths],
            "company_context": ({"path": str(company_context.expanduser().resolve()), "sha256": sha256_path(company_context)} if company_context else None),
            "rewrite_provider": provider_identity,
            "engine": engine_identity,
            "job_url": role.job_url,
            "context_sources": [(item.get("url"), item.get("sha256")) for item in role.metadata.get("sources", [])],
        }, sort_keys=True))
        prior = journal.get(role.role_id)
        requested_approval = approval_paths.get(role.role_id, approval_paths.get(None))
        if not force and _verified_delivery(prior, intake_digest, requested_approval):
            outcomes.append(RoleOutcome(
                role.role_id, "already_tailored", title=role.title, company=role.company,
                output_document=str(prior["output_document"]), proposal_path=str(prior["proposal"]),
                message="verified proposal, approval, receipt, and output already exist",
            ))
            return

        if prior.get("stage") == "validated" and prior.get("intake_digest") == intake_digest and not force:
            outcomes.append(RoleOutcome(role.role_id, "blocked_recovery", title=role.title,
                proposal_path=str(proposal_path), message="completed output or approval changed; inspect the receipt and explicitly choose recovery"))
            return

        proposal: dict[str, Any]
        if prior.get("intake_digest") == intake_digest and proposal_path.is_file():
            try:
                proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
                verify_proposal_digest(proposal)
            except (OSError, ValueError, json.JSONDecodeError):
                outcomes.append(RoleOutcome(
                    role.role_id,
                    "blocked_recovery",
                    title=role.title,
                    company=role.company,
                    proposal_path=str(proposal_path),
                    message="the persisted proposal is corrupt; prepare a fresh review before applying",
                ))
                return
        else:
            proposal = {}
        if not proposal:
            jd_path = role_dir / "job-description.md"
            atomic_write_text(jd_path, role.jd_text)
            context_sources = [item for item in role.metadata.get("sources", [])
                               if item.get("source_type") == "official_company_context" and item.get("path")]
            role_context = company_context
            if context_sources:
                role_context = role_dir / "company-context.md"
                atomic_write_text(role_context, "\n\n".join([
                    *([company_context.read_text(encoding="utf-8")] if company_context else []),
                    *(Path(str(item["path"])).read_text(encoding="utf-8") for item in context_sources),
                ]))
            from .job_research import _validate_role_dossier
            proposal = build_proposal(
                Path(cv_path), jd_path, evidence_paths=evidence_paths,
                candidate_id=candidate_id, company_context=role_context,
                provider=rewrite_provider, candidate_cache=candidate_cache,
                rewrite_cache=rewrite_cache,
                additional_requirements=_validate_role_dossier(role.metadata.get("role_dossier"), role.jd_text, role.capture or {}),
            )
            if proposal.get("status") == "draft" and role.capture:
                sources = role.metadata.get("sources") or [role.capture]
                proposal["research"] = {"mode": "public_capture", "captured_at": role.capture["captured_at"], "sources": sources}
                for requirement in proposal["requirements"]:
                    requirement.update(source_url=role.capture["url"], capture_sha256=role.capture["sha256"], source_type=role.capture["source_type"])
                proposal = finalize_proposal(proposal)
                atomic_write_text(
                    role_dir / "capture-manifest.json",
                    json.dumps({"sources": sources}, indent=2),
                )
            if proposal.get("status") == "draft":
                write_review_bundle(
                    proposal,
                    role_dir,
                    redacted=False,
                    protected_inputs=[
                        Path(cv_path),
                        *evidence_paths,
                        *context_paths,
                        jd_path,
                    ],
                )
        if proposal.get("status") != "draft":
            outcomes.append(RoleOutcome(role.role_id, "blocked_proposal", title=role.title, company=role.company, message=str(proposal.get("reason") or "proposal is blocked"), proposal_path=str(proposal_path)))
            journal.update(role.role_id, stage="blocked_proposal", intake_digest=intake_digest, proposal=str(proposal_path))
            return
        proposal_digest = verify_proposal_digest(proposal)
        journal.update(role.role_id, stage="proposed", intake_digest=intake_digest, proposal=str(proposal_path), proposal_digest=proposal_digest, title=role.title, company=role.company, capture=role.capture)
        writer(render_proposal_summary(proposal))
        unmet = [str(gate.get("requirement_id")) for gate in proposal.get("hard_gates", []) if gate.get("status") == "unmet"]
        if unmet:
            outcomes.append(RoleOutcome(role.role_id, "blocked_hard_gate", title=role.title, company=role.company, proposal_path=str(proposal_path), message="mandatory eligibility requirements are unmet: " + ", ".join(unmet)))
            journal.update(role.role_id, stage="blocked_hard_gate")
            return

        approval_path = _approval_for_role(approval_paths, role.role_id, proposal_path, proposal_digest)
        if approval_path is None and not any(change.get("supported") for change in proposal.get("changes", [])):
            outcomes.append(RoleOutcome(role.role_id, "no_changes", title=role.title,
                company=role.company, proposal_path=str(proposal_path), message="no supported edits; review the evidence gaps"))
            journal.update(role.role_id, stage="no_changes")
            return
        if approval_path is None and not interactive:
            outcomes.append(RoleOutcome(role.role_id, "awaiting_approval", title=role.title, company=role.company, proposal_path=str(proposal_path), message="review the persisted proposal and run ats-agent approve with explicit change IDs and variants"))
            return
        if approval_path is None:
            unknown = [str(gate.get("requirement_id")) for gate in proposal.get("hard_gates", []) if gate.get("status") == "unknown"]
            if unknown:
                outcomes.append(RoleOutcome(role.role_id, "blocked_hard_gate", title=role.title, company=role.company, proposal_path=str(proposal_path), message="unknown gates require a persisted approval manifest: " + ", ".join(unknown)))
                return
            writer("  selections (for example C1:balanced C3:compact, or skip):")
            tokens = reader("").strip().split()
            if not tokens or tokens[0].casefold() in {"skip", "quit"}:
                outcomes.append(RoleOutcome(role.role_id, "skipped", title=role.title, company=role.company, proposal_path=str(proposal_path), message="no changes approved"))
                journal.update(role.role_id, stage="skipped")
                return
            selections, _ = _normalize_selections(tokens, proposal, writer)
            selection_tuples: list[tuple[str, str | None]] = []
            for selection in selections:
                change_id, variant_id = selection.split(":", 1)
                selection_tuples.append((change_id, variant_id))
            manifest = build_approval_manifest(
                proposal, proposal_filename="proposal.json",
                selections=selection_tuples,
                output_document=f"tailored-resume-{role.role_id}.docx",
                document_mode=("strict-preserve" if Path(cv_path).suffix.lower() == ".docx" else "preserve"),
                force=bool(force),
            )
            approval_path = role_dir / "approval.json"
            atomic_write_text(
                approval_path,
                json.dumps(manifest, indent=2) + "\n",
            )

        journal.update(role.role_id, stage="approved", approval_manifest=str(approval_path))
        applied = apply_manifest(approval_path)
        output_path = Path(str(applied["output"]))
        receipt = output_path.with_suffix(output_path.suffix + ".applied.json")
        if not receipt.is_file() or sha256_path(output_path) != applied.get("output_sha256"):
            raise TailorBlocked("apply returned without a matching persisted receipt")
        audit_summary = audit_file(str(output_path))
        finding_count = len(audit_summary.get("findings", [])) if isinstance(audit_summary, dict) else 0
        journal.update(role.role_id, stage="validated", output_document=str(output_path), approval_manifest=str(approval_path), receipt=str(receipt), approval_sha256=sha256_path(approval_path), receipt_sha256=sha256_path(receipt), intake_digest=intake_digest, completed_at=_now())
        outcomes.append(RoleOutcome(role.role_id, "tailored", title=role.title, company=role.company, output_document=str(output_path), proposal_path=str(proposal_path), message=f"content validated; {finding_count} format note(s); rendered layout remains unverified"))
    def handle_role(role: RoleSource) -> None:
        journal.data["source_roles"].append(asdict(role))
        journal.save()
        try:
            for item in [*role.metadata.get("sources", []), *([role.capture] if role.capture else [])]:
                if item.get("path") and item.get("sha256") != sha256_path(Path(str(item["path"]))):
                    raise TailorBlocked("captured source changed; prepare a fresh review")
            process_role(role)
        except (OSError, ValueError, TailorBlocked) as exc:
            status = "blocked_liveness" if isinstance(exc, ResearchFreshnessError) else "blocked_recovery"
            outcomes.append(RoleOutcome(role.role_id, status, title=role.title,
                                        company=role.company, message=str(exc)))
            journal.update(role.role_id, stage=status, reason=str(exc))

    if restore:
        roles = [RoleSource(**item) for item in saved]
        for role in roles:
            handle_role(role)
    else:
        roles = _collect_roles(resolved, run_dir, max_urls, on_ready=handle_role)
    if not roles:
        raise TailorBlocked("source produced no roles to tailor against")
    order = {role.role_id: index for index, role in enumerate(roles)}
    outcomes.sort(key=lambda outcome: order[outcome.role_id])
    journal.data["source_roles"] = [asdict(role) for role in roles]
    journal.data["source_roles_digest"] = _sha256_text(json.dumps(journal.data["source_roles"], sort_keys=True))
    journal.data["collection_complete"] = True
    journal.save()

    payload = _finish(outcomes, journal)
    payload["provider_calls"] = rewrite_cache.stats()
    return payload


def _finish(outcomes: list[RoleOutcome], journal: Journal) -> dict[str, Any]:
    card = _delivery_card(outcomes)
    print(card, file=sys.stderr)
    blocked = sum(outcome.status.startswith("blocked_") for outcome in outcomes)
    status = "completed" if outcomes else "no_roles"
    if blocked:
        status = "blocked" if blocked == len(outcomes) else "partial"
    elif any(outcome.status == "awaiting_approval" for outcome in outcomes):
        status = "awaiting_approval"
    elif any(outcome.status == "no_changes" for outcome in outcomes):
        status = "review_complete"
    return {
        "status": status,
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
