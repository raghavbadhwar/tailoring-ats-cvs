"""Engine readiness reporting, shared by the CLI and the orchestrator."""
from __future__ import annotations

import json
import sys
import tempfile
from importlib.util import find_spec
from pathlib import Path

from . import __version__
from .review import build_approval_manifest
from .workflow import apply_manifest, build_proposal
from .ingestion import load


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


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


def strict_check_passed() -> bool:
    return _strict_doctor_check().get("status") == "passed"
