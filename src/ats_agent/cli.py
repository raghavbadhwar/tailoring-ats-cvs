from __future__ import annotations

import argparse
import json
from importlib.resources import as_file, files
from pathlib import Path

from .benchmark import run as run_benchmark
from .formatting import audit_file
from .workflow import apply_manifest, build_proposal


def _existing(path: str) -> str:
    candidate = Path(path)
    if not candidate.is_file():
        raise SystemExit(f"file not found: {candidate}")
    return str(candidate)


def _add_analysis_inputs(command: argparse.ArgumentParser) -> None:
    command.add_argument("resume", type=_existing)
    command.add_argument("job_description", type=_existing)
    command.add_argument(
        "--evidence",
        action="append",
        default=[],
        type=_existing,
        help="additional candidate evidence file; may be supplied more than once",
    )
    command.add_argument(
        "--candidate-id",
        default="candidate",
        help="stable candidate identifier used to isolate evidence records",
    )


def _proposal_from_args(args: argparse.Namespace) -> dict:
    return build_proposal(
        Path(args.resume),
        Path(args.job_description),
        evidence_paths=[Path(path) for path in args.evidence],
        candidate_id=args.candidate_id,
    )


def _benchmark_result(dataset: str | None) -> dict:
    if dataset:
        return run_benchmark(Path(dataset))
    resource = files("ats_agent.data").joinpath("cases.jsonl")
    with as_file(resource) as packaged_dataset:
        return run_benchmark(packaged_dataset)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ats-agent")
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="validate inputs and emit an analysis report")
    _add_analysis_inputs(audit)

    formatting = sub.add_parser(
        "format",
        help="audit ATS-friendly formatting in an extractable resume",
    )
    formatting.add_argument("resume", type=_existing)
    formatting.add_argument("--json", action="store_true", help="emit machine-readable findings")

    propose = sub.add_parser("propose", help="analyze a CV and JD without editing either")
    _add_analysis_inputs(propose)
    propose.add_argument("--output", help="write the proposal JSON to this path")

    apply = sub.add_parser("apply", help="apply explicitly approved supported changes")
    apply.add_argument("approved_changes", type=_existing)

    benchmark = sub.add_parser("benchmark", help="run the offline synthetic benchmark")
    benchmark.add_argument(
        "--dataset",
        type=_existing,
        help="optional JSONL dataset; defaults to packaged smoke fixtures",
    )
    args = parser.parse_args(argv)

    if args.command == "benchmark":
        print(json.dumps(_benchmark_result(args.dataset), indent=2))
    elif args.command == "format":
        result = audit_file(args.resume)
        print(json.dumps(result, indent=2 if args.json else None))
    elif args.command == "audit":
        proposal = _proposal_from_args(args)
        if proposal.get("status") == "draft":
            proposal["status"] = "ready"
        print(json.dumps(proposal, indent=2))
    elif args.command == "propose":
        proposal = _proposal_from_args(args)
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(proposal, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(proposal, indent=2))
    else:
        manifest_path = Path(args.approved_changes)
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        approved = data.get("approved_change_ids") if isinstance(data, dict) else None
        if not isinstance(approved, list) or not all(isinstance(item, str) for item in approved):
            raise SystemExit("approved_changes.json must contain approved_change_ids: [string, ...]")
        if isinstance(data, dict) and (data.get("proposal") or data.get("source")):
            try:
                print(json.dumps(apply_manifest(manifest_path, approved), indent=2))
            except ValueError as exc:
                raise SystemExit(f"apply blocked: {exc}") from exc
        else:
            print(
                json.dumps(
                    {
                        "status": "validated",
                        "approved_change_ids": approved,
                        "source_overwrite": False,
                    }
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
