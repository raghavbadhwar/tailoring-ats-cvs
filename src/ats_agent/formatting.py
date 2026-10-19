"""Transparent parser-risk and readability diagnostics."""
from __future__ import annotations

import re
from pathlib import Path

from .ingestion import ExtractionError, load


def audit_text(text: str, diagnostics: dict | None = None) -> dict:
    diagnostics = diagnostics or {}
    lines = text.splitlines()
    findings: list[dict] = []
    if not text.strip():
        findings.append({"id": "F1", "severity": "error", "message": "Resume contains no extractable text."})
    if any(len(line) > 130 for line in lines):
        findings.append({"id": "F2", "severity": "warning", "message": "Long lines may indicate dense layout or poor reading order."})
    if any("\t" in line or re.search(r" {5,}", line) for line in lines):
        findings.append({"id": "F3", "severity": "warning", "message": "Tabular spacing detected; verify reading order."})
    if any(re.match(r"^\s*[●▪◦–—]", line) for line in lines):
        findings.append({"id": "F4", "severity": "info", "message": "Decorative bullets detected; use consistent standard bullets."})
    headings = {line.strip().lower().rstrip(":") for line in lines if len(line.split()) <= 5}
    missing = [name for name in ("education", "experience", "skills") if name not in headings]
    if missing:
        findings.append({"id": "F5", "severity": "info", "message": f"Standard section headings not detected: {', '.join(missing)}."})
    if diagnostics.get("has_tables"):
        findings.append({"id": "F6", "severity": "warning", "message": "DOCX tables detected; confirm ATS reading order or use rebuild mode."})
    if diagnostics.get("headers_or_footers"):
        findings.append({"id": "F7", "severity": "warning", "message": "Header/footer text detected; move essential contact details into the body for safer parsing."})
    if diagnostics.get("media_count"):
        findings.append({"id": "F8", "severity": "info", "message": "Embedded media detected; it may not be visible to parsers."})
    return {
        "extractable_word_count": len(re.findall(r"\b\w+[’'-]?\w*\b", text)),
        "line_count": len(lines),
        "findings": findings,
        "risk_level": "high" if any(f["severity"] == "error" for f in findings) else "medium" if any(f["severity"] == "warning" for f in findings) else "low",
        "recommendations": [
            "Use one column with ordinary section headings, consistent dates, and plain text links.",
            "Keep body text around 10.5–11 pt with stable margins and spacing.",
            "Use preserve mode for a clean existing DOCX or rebuild mode for an ATS-safe one-column document.",
        ],
    }


def audit_file(path: str) -> dict:
    file = Path(path)
    try:
        loaded = load(file)
    except ExtractionError as exc:
        return {"path": str(file), "status": "blocked", "findings": [{"id": "F0", "severity": "error", "message": str(exc)}]}
    result = audit_text(loaded["text"], loaded.get("diagnostics"))
    return {"path": str(file), "status": "audited", **result}
