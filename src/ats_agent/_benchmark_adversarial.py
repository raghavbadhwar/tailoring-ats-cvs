"""Execute Benchmark v3 adversarial safety scenarios."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from ._benchmark_validate import (
    _expected_requirement_key,
    _normalize_match_status,
    _requirement_key,
)


def _write_approval_fixture(
    root: Path,
    resume_text: str,
    job_text: str,
) -> tuple[Path, Path, dict[str, Any]]:
    from .review import build_approval_manifest
    from .workflow import build_proposal

    resume = root / "resume.txt"
    job = root / "job.txt"
    resume.write_text(resume_text, encoding="utf-8")
    job.write_text(job_text, encoding="utf-8")
    proposal = build_proposal(
        resume,
        job,
        candidate_id="benchmark-adversarial",
    )
    proposal_path = root / "proposal.json"
    proposal_path.write_text(
        json.dumps(proposal, indent=2) + "\n",
        encoding="utf-8",
    )
    supported = next(
        change for change in proposal.get("changes", []) if change.get("supported")
    )
    manifest = build_approval_manifest(
        proposal,
        proposal_filename=proposal_path.name,
        selections=[
            (
                str(supported["id"]),
                str(
                    supported.get("default_variant")
                    or supported["variants"][0]["id"]
                ),
            )
        ],
        output_document="tailored.txt",
        document_mode="preserve",
    )
    manifest_path = root / "approval.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return proposal_path, manifest_path, proposal


def _evaluate_adversarial_case(case: dict[str, Any]) -> dict[str, Any]:
    from .documents import patch_document
    from .evidence import (
        EvidenceItem,
        EvidenceLedger,
        EvidenceSource,
        build_evidence_ledger,
    )
    from .ingestion import ExtractionError, load
    from .requirements import (
        evaluate_hard_gates,
        extract_requirements,
        map_requirements,
    )
    from .rewriting import propose_supported_changes
    from .validation import validate_change
    from .workflow import apply_manifest, build_proposal

    scenario = str(case.get("scenario") or "")
    passed = False
    detail = ""
    try:
        if scenario == "cross_candidate_evidence":
            item = EvidenceItem(
                id="E-CROSS",
                candidate_id="other-candidate",
                text=str(case.get("attack_payload") or ""),
                source="supporting",
                source_file="other.txt",
                source_span="line 1",
                line_number=1,
                paragraph_index=None,
                part="text",
                ownership="direct",
            )
            try:
                EvidenceLedger("expected-candidate", (item,))
            except ValueError as exc:
                passed = "candidate identity" in str(exc).casefold()
        elif scenario in {
            "employer_substitution",
            "ownership_escalation",
            "metric_unit_reassignment",
        }:
            ledger = build_evidence_ledger(
                "candidate",
                [
                    EvidenceSource(
                        source="resume",
                        source_file="resume.txt",
                        text=str(case.get("resume") or ""),
                        candidate_id="candidate",
                    )
                ],
            )
            evidence = ledger.items[0]
            change = {
                "id": "C-ATTACK",
                "operation": "replace_span",
                "supported": True,
                "evidence_ids": [evidence.id],
                "expected_text": evidence.text,
                "replacement_text": str(case.get("malicious_replacement") or ""),
            }
            try:
                validate_change(change, ledger)
            except ValueError:
                passed = True
        elif scenario in {
            "jd_prompt_injection",
            "repeated_boilerplate",
            "false_alias",
            "ambiguous_acronym",
            "negation",
        }:
            ledger = build_evidence_ledger(
                "candidate",
                [
                    EvidenceSource(
                        source="resume",
                        source_file="resume.txt",
                        text=str(case.get("resume") or ""),
                        candidate_id="candidate",
                    )
                ],
            )
            requirements = extract_requirements(
                str(case.get("job_description") or "")
            )
            mappings = map_requirements(requirements, ledger)
            changes = propose_supported_changes(
                str(case.get("resume") or ""),
                requirements,
                mappings,
                ledger,
            )
            generated = " ".join(
                str(variant.get("text") or "")
                for change in changes
                if change.get("supported")
                for variant in change.get("variants") or []
            ).casefold()
            forbidden = {
                str(term).casefold()
                for term in case.get("forbidden_rewrite_terms") or []
            }
            no_forbidden = all(term not in generated for term in forbidden)
            expected_matches = {
                str(item.get("term") or "").casefold(): _normalize_match_status(
                    item.get("status")
                )
                for item in case.get("expected_matches") or []
            }
            predicted = {
                str(term).casefold(): _normalize_match_status(
                    mapping.get("coverage")
                )
                for mapping in mappings
                if mapping.get("kind") == "skill"
                for term in mapping.get("normalized_terms") or []
            }
            statuses_ok = all(
                predicted.get(term, "unsupported") == status
                for term, status in expected_matches.items()
            )
            duplicate_limit = int(
                case.get("expected_max_duplicate_changes")
                or len(changes)
            )
            passed = (
                no_forbidden
                and statuses_ok
                and len(
                    [change for change in changes if change.get("supported")]
                )
                <= duplicate_limit
            )
        elif scenario == "company_context_prompt_injection":
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                resume = root / "resume.txt"
                job = root / "job.txt"
                company = root / "company.txt"
                resume.write_text(str(case["resume"]), encoding="utf-8")
                job.write_text(
                    str(case["job_description"]), encoding="utf-8"
                )
                company.write_text(
                    str(case.get("company_context") or ""),
                    encoding="utf-8",
                )
                proposal = build_proposal(
                    resume,
                    job,
                    company_context=company,
                    candidate_id="candidate",
                )
                evidence_files = {
                    str(item.get("source_file"))
                    for item in proposal.get("evidence_ledger", [])
                }
                generated = " ".join(
                    str(variant.get("text") or "")
                    for change in proposal.get("changes", [])
                    if change.get("supported")
                    for variant in change.get("variants") or []
                ).casefold()
                passed = (
                    str(company.resolve()) not in evidence_files
                    and all(
                        str(term).casefold() not in generated
                        for term in case.get("forbidden_rewrite_terms") or []
                    )
                )
        elif scenario in {
            "year_confusion",
            "academic_experience_confusion",
            "conflicting_evidence",
        }:
            ledger = build_evidence_ledger(
                "candidate",
                [
                    EvidenceSource(
                        source="resume",
                        source_file="resume.txt",
                        text=str(case.get("resume") or ""),
                        candidate_id="candidate",
                    )
                ],
            )
            requirements = extract_requirements(
                str(case.get("job_description") or "")
            )
            gates = {
                str(item["kind"]): str(item["status"])
                for item in evaluate_hard_gates(requirements, ledger)
            }
            expected_gates = {
                str(item["kind"]): str(item["status"])
                for item in case.get("expected_hard_gates") or []
            }
            passed = all(
                gates.get(kind) == status
                for kind, status in expected_gates.items()
            )
        elif scenario == "mixed_importance":
            requirements = extract_requirements(
                str(case.get("job_description") or "")
            )
            actual = {
                _requirement_key(requirement)
                for requirement in requirements
                if requirement.get("kind") == "skill"
            }
            expected_requirements = {
                _expected_requirement_key(requirement)
                for requirement in case.get("expected_requirements") or []
            }
            passed = expected_requirements <= actual
        elif scenario in {"stale_resume", "proposal_tampering"}:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                proposal_path, manifest_path, proposal = _write_approval_fixture(
                    root,
                    str(case["resume"]),
                    str(case["job_description"]),
                )
                if scenario == "stale_resume":
                    (root / "resume.txt").write_text(
                        str(case["resume"]) + str(case.get("mutation") or ""),
                        encoding="utf-8",
                    )
                else:
                    proposal["changes"][0]["variants"][0]["text"] = str(
                        case.get("tampered_replacement") or ""
                    )
                    proposal_path.write_text(
                        json.dumps(proposal, indent=2) + "\n",
                        encoding="utf-8",
                    )
                try:
                    apply_manifest(manifest_path)
                except ValueError:
                    passed = True
        elif scenario == "ambiguous_anchor":
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "resume.txt"
                output = root / "output.txt"
                source.write_text(str(case["resume"]), encoding="utf-8")
                expected_text = str(case.get("expected_text") or "")
                try:
                    patch_document(
                        source,
                        output,
                        [
                            {
                                "id": "C1",
                                "operation": "replace_span",
                                "expected_text": expected_text,
                                "replacement_text": "Supported safe checks.",
                                "anchor": {},
                            }
                        ],
                    )
                except ValueError:
                    passed = True
        elif scenario == "unsupported_output":
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "resume.txt"
                source.write_text(str(case["resume"]), encoding="utf-8")
                output = root / ("output" + str(case["output_extension"]))
                try:
                    patch_document(
                        source,
                        output,
                        [
                            {
                                "id": "C1",
                                "operation": "replace_span",
                                "expected_text": "Supported Python checks",
                                "replacement_text": "Supported Python validation",
                                "anchor": {},
                            }
                        ],
                    )
                except ValueError:
                    passed = True
        elif scenario == "malformed_docx":
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "bad.docx"
                kind = str(case.get("malformed_kind") or "")
                if kind == "missing-document":
                    import zipfile

                    with zipfile.ZipFile(path, "w") as archive:
                        archive.writestr("[Content_Types].xml", "<Types/>")
                elif kind == "truncated":
                    path.write_bytes(b"PK\x03\x04truncated")
                else:
                    path.write_bytes(b"not a zip")
                try:
                    load(path)
                except (ExtractionError, OSError, ValueError):
                    passed = True
        elif scenario == "hidden_text":
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "resume.html"
                path.write_text(str(case["resume"]), encoding="utf-8")
                document = load(path)
                text = str(document.get("text") or "")
                passed = (
                    str(case.get("expected_visible") or "") in text
                    and "led production" not in text.casefold()
                )
        else:
            detail = f"unsupported adversarial scenario: {scenario}"
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}"
        passed = False
    return {
        "id": str(case["id"]),
        "scenario": scenario,
        "passed": passed,
        "detail": detail,
    }
