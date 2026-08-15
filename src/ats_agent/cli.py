"""Command-line interface for evidence-grounded CV tailoring."""
from __future__ import annotations

import argparse
import json
import sys
from importlib.util import find_spec
from pathlib import Path

from .benchmark import run as run_benchmark
from .formatting import audit_file
from .ingestion import load
from .reporting import write_review_artifacts
from .reports import render_html, render_markdown
from .workflow import apply_manifest, build_proposal


def _existing(path: str) -> str:
    candidate = Path(path)
    if not candidate.is_file():
        raise argparse.ArgumentTypeError(f"file not found: {candidate}")
    return str(candidate)


def _add_analysis_inputs(command: argparse.ArgumentParser) -> None:
    command.add_argument("resume", type=_existing)
    command.add_argument("job_description", type=_existing)
    command.add_argument("--evidence", action="append", default=[], type=_existing, help="additional candidate evidence file; repeatable")
    command.add_argument("--company-context", type=_existing, help="optional user-supplied official company context")
    command.add_argument("--candidate-id", required=False, default="candidate", help="stable candidate identifier used to isolate evidence")


def _proposal_from_args(args: argparse.Namespace) -> dict:
    return build_proposal(
        Path(args.resume),
        Path(args.job_description),
        evidence_paths=[Path(path) for path in args.evidence],
        candidate_id=args.candidate_id,
        company_context=Path(args.company_context) if args.company_context else None,
    )


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _doctor() -> dict:
    return {
        "python": sys.version.split()[0],
        "optional_dependencies": {
            "pypdf": bool(find_spec("pypdf")),
        },
        "capabilities": {
            "txt_markdown_html_rtf": True,
            "docx_input": True,
            "docx_preserve_output": True,
            "pdf_input": bool(find_spec("pypdf")),
            "pdf_output": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ats-agent")
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="validate inputs and emit analysis JSON")
    _add_analysis_inputs(audit)

    propose = sub.add_parser("propose", help="create an evidence-grounded proposal without editing")
    _add_analysis_inputs(propose)
    propose.add_argument("--output", help="proposal JSON output path")

    prepare = sub.add_parser("prepare", help="create proposal JSON, Markdown, and local review HTML")
    _add_analysis_inputs(prepare)
    prepare.add_argument("--out", required=True, help="run directory")

    formatting = sub.add_parser("format", help="audit ATS-friendly formatting")
    formatting.add_argument("resume", type=_existing)

    apply = sub.add_parser("apply", help="apply explicitly approved supported changes")
    apply.add_argument("approval_manifest", type=_existing)

    validate = sub.add_parser("validate", help="re-parse and audit an output document")
    validate.add_argument("document", type=_existing)

    benchmark = sub.add_parser("benchmark", help="run the offline benchmark")
    benchmark.add_argument("--dataset", required=True, type=_existing)

    review = sub.add_parser("review", help="render Markdown and self-contained HTML from a proposal")
    review.add_argument("proposal", type=_existing)
    review.add_argument("--markdown", required=True, help="Markdown review output path")
    review.add_argument("--html", required=True, help="HTML review output path")
    review.add_argument("--output-document", default="tailored-resume.docx")

    sub.add_parser("doctor", help="show local capabilities and optional dependencies")
    args = parser.parse_args(argv)

    try:
        if args.command == "doctor":
            payload = _doctor()
        elif args.command == "benchmark":
            payload = run_benchmark(Path(args.dataset))
        elif args.command == "format":
            payload = audit_file(args.resume)
        elif args.command == "validate":
            loaded = load(Path(args.document))
            payload = {"status": "valid", "document": loaded, "formatting": audit_file(args.document)}
        elif args.command in {"audit", "propose"}:
            payload = _proposal_from_args(args)
            if args.command == "audit" and payload.get("status") == "draft":
                payload["status"] = "ready"
            if args.command == "propose" and args.output:
                _write_json(Path(args.output), payload)
        elif args.command == "review":
            proposal_path = Path(args.proposal).expanduser().resolve()
            proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
            markdown_path = Path(args.markdown).expanduser().resolve()
            html_path = Path(args.html).expanduser().resolve()
            markdown_path.parent.mkdir(parents=True, exist_ok=True)
            html_path.parent.mkdir(parents=True, exist_ok=True)
            markdown_path.write_text(render_markdown(proposal), encoding="utf-8")
            html_path.write_text(
                render_html(
                    proposal,
                    proposal_filename=proposal_path.name,
                    default_output=args.output_document,
                ),
                encoding="utf-8",
            )
            payload = {
                "status": "written",
                "markdown": str(markdown_path),
                "html": str(html_path),
            }
        elif args.command == "prepare":
            proposal = _proposal_from_args(args)
            out = Path(args.out).expanduser().resolve()
            proposal_path = out / "proposal.json"
            _write_json(proposal_path, proposal)
            artifacts = write_review_artifacts(proposal, out)
            payload = {
                "status": proposal.get("status"),
                "proposal": str(proposal_path),
                "proposal_markdown": artifacts["markdown"],
                "review_html": artifacts["html"],
            }
        else:
            payload = apply_manifest(Path(args.approval_manifest))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, indent=2), file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
