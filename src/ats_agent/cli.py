"""Command-line interface for evidence-grounded CV tailoring."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from importlib.util import find_spec
from pathlib import Path

from . import __version__
from .benchmark import (
    BenchmarkGateError,
    SUITE_FILENAMES,
    run as run_benchmark,
    run_suite,
)
from .formatting import audit_file
from .ingestion import load
from .review import (
    build_approval_manifest,
    render_html,
    render_markdown,
    write_review_bundle,
)
from .workflow import apply_manifest, build_proposal


def _existing(path: str) -> str:
    candidate = Path(path)
    if not candidate.is_file():
        raise argparse.ArgumentTypeError(f"file not found: {candidate}")
    return str(candidate)


def _selection(value: str) -> tuple[str, str | None]:
    change_id, separator, variant_id = value.partition(":")
    if not change_id.strip():
        raise argparse.ArgumentTypeError(
            "selection must use CHANGE_ID or CHANGE_ID:VARIANT_ID"
        )
    return (
        change_id.strip(),
        variant_id.strip() if separator and variant_id.strip() else None,
    )


def _add_analysis_inputs(command: argparse.ArgumentParser) -> None:
    command.add_argument("resume", type=_existing)
    command.add_argument("job_description", type=_existing)
    command.add_argument(
        "--evidence",
        action="append",
        default=[],
        type=_existing,
        help="additional candidate evidence file; repeatable",
    )
    command.add_argument(
        "--company-context",
        type=_existing,
        help="optional user-supplied official company context",
    )
    command.add_argument(
        "--candidate-id",
        required=False,
        default="candidate",
        help="stable candidate identifier used to isolate evidence",
    )


def _proposal_from_args(args: argparse.Namespace) -> dict:
    return build_proposal(
        Path(args.resume),
        Path(args.job_description),
        evidence_paths=[Path(path) for path in args.evidence],
        candidate_id=args.candidate_id,
        company_context=(
            Path(args.company_context) if args.company_context else None
        ),
    )


def _write_json(path: Path, payload: object) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_review(
    proposal_path: Path,
    markdown_path: Path,
    html_path: Path,
    output_document: str,
    *,
    redacted: bool,
) -> dict:
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        render_markdown(proposal, redacted=redacted),
        encoding="utf-8",
    )
    html_path.write_text(
        render_html(
            proposal,
            proposal_filename=proposal_path.name,
            default_output=output_document,
            redacted=redacted,
        ),
        encoding="utf-8",
    )
    return {
        "status": "written",
        "proposal": str(proposal_path),
        "markdown": str(markdown_path),
        "html": str(html_path),
        "output_document": output_document,
        "review_mode": "redacted" if redacted else "full",
    }


def _write_approval(args: argparse.Namespace) -> dict:
    proposal_path = Path(args.proposal).expanduser().resolve()
    manifest_path = Path(args.output).expanduser().resolve()
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    relative_proposal = os.path.relpath(proposal_path, manifest_path.parent)
    manifest = build_approval_manifest(
        proposal,
        proposal_filename=relative_proposal,
        selections=args.select,
        output_document=args.output_document,
        document_mode=args.document_mode,
        force=args.force,
    )
    _write_json(manifest_path, manifest)
    return {
        "status": "written",
        "approval_manifest": str(manifest_path),
        "proposal": str(proposal_path),
        "proposal_digest": manifest["proposal_digest"],
        "approved_change_ids": manifest["approved_change_ids"],
        "output_document": args.output_document,
    }


def _run_benchmark(
    dataset: str | None,
    suite: str,
    report: str | None,
) -> dict:
    report_path = Path(report) if report else None
    if dataset:
        if suite != "smoke":
            raise BenchmarkGateError(
                "--dataset cannot be combined with a non-default --suite"
            )
        result = run_benchmark(Path(dataset))
        if report_path is not None:
            _write_json(report_path, result)
        return result
    return run_suite(suite, report_path=report_path)


def _strict_doctor_check() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="ats-agent-doctor-") as directory:
        root = Path(directory)
        resume = root / "resume.txt"
        job = root / "job.md"
        proposal_path = root / "proposal.json"
        approval_path = root / "approval.json"
        output_path = root / "tailored.txt"
        resume.write_text("PROJECTS\n- Helped build automated workflows with 42 tests.\n", encoding="utf-8")
        job.write_text("Workflow automation is required.\n", encoding="utf-8")
        proposal = build_proposal(resume, job, candidate_id="doctor-candidate")
        supported = next(change for change in proposal["changes"] if change.get("supported"))
        _write_json(proposal_path, proposal)
        manifest = build_approval_manifest(
            proposal,
            proposal_filename=proposal_path.name,
            selections=[(supported["id"], supported.get("default_variant") or supported["variants"][0]["id"])],
            output_document=output_path.name,
            document_mode="preserve",
        )
        _write_json(approval_path, manifest)
        receipt = apply_manifest(approval_path)
        loaded = load(output_path)
        return {
            "status": "passed",
            "proposal_created": proposal_path.is_file(),
            "approval_created": approval_path.is_file(),
            "output_validated": bool(loaded.get("body_text")),
            "receipt_status": receipt.get("status"),
        }


def _doctor(*, strict: bool = False) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "status": "ready",
        "package": {"name": "tailoring-ats-cvs", "version": __version__, "executable": "ats-agent"},
        "python": sys.version.split()[0],
        "optional_dependencies": {
            "pypdf": bool(find_spec("pypdf")),
            "python_docx": bool(find_spec("docx")),
        },
        "capabilities": {
            "txt_markdown_html_rtf": True,
            "docx_input": True,
            "docx_preserve_output": bool(find_spec("docx")),
            "pdf_input": bool(find_spec("pypdf")),
            "pdf_output": False,
            "redacted_review": True,
            "digest_bound_approval": True,
            "transactional_apply": True,
            "benchmark_v3": True,
            "agent_adapter_contract": 1,
        },
    }
    if strict:
        payload["strict_check"] = _strict_doctor_check()
    return payload


def _error_exit_code(exc: Exception) -> int:
    if isinstance(exc, BenchmarkGateError):
        return 7
    message = str(exc).lower()
    if any(
        marker in message
        for marker in (
            "stale proposal",
            "stale artifact",
            "proposal digest",
            "digest-bound approval",
            "does not match proposal content",
        )
    ):
        return 3
    if any(
        marker in message
        for marker in (
            "ownership escalation",
            "metric binding",
            "unsupported numeric",
            "protected status",
            "candidate identity",
            "has no evidence",
            "is unsupported",
            "unknown approved change",
        )
    ):
        return 4
    if any(
        marker in message
        for marker in (
            "output",
            "document anchor",
            "docx",
            "pdf output",
            "unsupported output format",
            "verification failed",
        )
    ):
        return 5
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ats-agent")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser(
        "audit",
        help="validate inputs and emit analysis JSON",
    )
    _add_analysis_inputs(audit)

    propose = sub.add_parser(
        "propose",
        help="create an evidence-grounded proposal without editing",
    )
    _add_analysis_inputs(propose)
    propose.add_argument("--output", help="proposal JSON output path")

    prepare = sub.add_parser(
        "prepare",
        help="create proposal JSON, Markdown, and local review HTML",
    )
    _add_analysis_inputs(prepare)
    prepare.add_argument("--out", required=True, help="run directory")
    prepare.add_argument(
        "--redacted",
        action="store_true",
        help="write a shareable review with candidate content removed",
    )

    review = sub.add_parser(
        "review",
        help="render Markdown and local HTML from an existing proposal",
    )
    review.add_argument("proposal", type=_existing)
    review.add_argument("--markdown", required=True)
    review.add_argument("--html", required=True)
    review.add_argument(
        "--output-document",
        default="tailored-resume.docx",
    )
    review.add_argument(
        "--redacted",
        action="store_true",
        help="remove candidate content and disable approvals",
    )

    approve = sub.add_parser(
        "approve",
        help="create a digest-bound approval manifest without editing",
    )
    approve.add_argument("proposal", type=_existing)
    approve.add_argument(
        "--select",
        action="append",
        required=True,
        type=_selection,
        help="CHANGE_ID or CHANGE_ID:VARIANT_ID; repeatable",
    )
    approve.add_argument(
        "--output",
        required=True,
        help="approval manifest path",
    )
    approve.add_argument(
        "--output-document",
        default="tailored-resume.docx",
    )
    approve.add_argument(
        "--document-mode",
        choices=("preserve", "rebuild"),
        default="preserve",
    )
    approve.add_argument(
        "--force",
        action="store_true",
        help="allow replacement of an existing final output at apply time",
    )

    formatting = sub.add_parser(
        "format",
        help="audit ATS-friendly formatting",
    )
    formatting.add_argument("resume", type=_existing)

    apply_command = sub.add_parser(
        "apply",
        help="apply explicitly approved supported changes",
    )
    apply_command.add_argument("approval_manifest", type=_existing)

    validate = sub.add_parser(
        "validate",
        help="re-parse and audit an output document",
    )
    validate.add_argument("document", type=_existing)

    benchmark = sub.add_parser(
        "benchmark",
        help="run a frozen Benchmark v3 suite",
    )
    benchmark.add_argument(
        "--suite",
        choices=tuple(sorted(SUITE_FILENAMES)),
        default="smoke",
    )
    benchmark.add_argument(
        "--dataset",
        type=_existing,
        help="custom JSONL dataset using the legacy or v3 schema",
    )
    benchmark.add_argument(
        "--report",
        help="write the complete machine-readable report to this path",
    )

    doctor = sub.add_parser(
        "doctor",
        help="show local capabilities and optionally run a functional self-test",
    )
    doctor.add_argument("--strict", action="store_true", help="run a temporary propose-approve-apply-validate smoke check")
    args = parser.parse_args(argv)

    try:
        if args.command == "doctor":
            payload = _doctor(strict=args.strict)
        elif args.command == "benchmark":
            payload = _run_benchmark(
                args.dataset,
                args.suite,
                args.report,
            )
        elif args.command == "format":
            payload = audit_file(args.resume)
        elif args.command == "validate":
            loaded = load(Path(args.document))
            payload = {
                "status": "valid",
                "document": loaded,
                "formatting": audit_file(args.document),
            }
        elif args.command == "review":
            payload = _write_review(
                Path(args.proposal),
                Path(args.markdown),
                Path(args.html),
                args.output_document,
                redacted=args.redacted,
            )
        elif args.command == "approve":
            payload = _write_approval(args)
        elif args.command in {"audit", "propose"}:
            payload = _proposal_from_args(args)
            if args.command == "audit" and payload.get("status") == "draft":
                payload["status"] = "ready"
            if args.command == "propose" and args.output:
                _write_json(Path(args.output), payload)
        elif args.command == "prepare":
            proposal = _proposal_from_args(args)
            out = Path(args.out).expanduser().resolve()
            artifacts = write_review_bundle(
                proposal,
                out,
                redacted=args.redacted,
            )
            payload = {
                "status": proposal.get("status"),
                "proposal": artifacts["proposal"],
                "proposal_markdown": artifacts["markdown"],
                "review_html": artifacts["html"],
                "review_mode": "redacted" if args.redacted else "full",
            }
        else:
            payload = apply_manifest(Path(args.approval_manifest))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {"status": "blocked", "error": str(exc)},
                indent=2,
            ),
            file=sys.stderr,
        )
        return _error_exit_code(exc)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
