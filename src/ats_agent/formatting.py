from __future__ import annotations

import re
from pathlib import Path

SUPPORTED_TEXT = {".txt", ".md", ".markdown", ".rtf", ".html", ".htm"}


def audit_text(text: str) -> dict:
    lines = text.splitlines()
    findings = []
    if not text.strip():
        findings.append({"id": "F1", "severity": "error", "message": "Resume contains no extractable text."})
    if any(len(line) > 120 for line in lines):
        findings.append({"id": "F2", "severity": "warning", "message": "Long lines may indicate dense layout or poor reading order; target one-column text."})
    if any("\t" in line or re.search(r" {4,}", line) for line in lines):
        findings.append({"id": "F3", "severity": "warning", "message": "Tabular spacing detected; replace columns/tabs with labeled sections and normal spacing."})
    if any(re.match(r"^\s*[•●▪◦–—]", line) for line in lines):
        findings.append({"id": "F4", "severity": "info", "message": "Decorative bullets detected; use standard hyphen or round bullet characters consistently."})
    headings = {line.strip().lower().rstrip(":") for line in lines if line.strip().isupper() and len(line.split()) <= 5}
    missing = [name for name in ("education", "experience", "skills") if name not in headings]
    if missing:
        findings.append({"id": "F5", "severity": "info", "message": f"Standard section headings not detected: {', '.join(missing)}."})
    return {
        "extractable_word_count": len(re.findall(r"\b\w+[’'-]?\w*\b", text)),
        "line_count": len(lines),
        "findings": findings,
        "recommendations": [
            "Use one column with ordinary section headings, consistent dates, and plain text links.",
            "Keep body text around 10.5–11 pt with stable margins and spacing.",
            "Remove tables, text boxes, headers/footers, graphics, photos, and skill bars before export.",
        ],
    }


def audit_file(path: str) -> dict:
    file = Path(path)
    if file.suffix.lower() not in SUPPORTED_TEXT:
        return {"path": str(file), "status": "needs_extraction", "findings": [{"id": "F0", "severity": "info", "message": "Extract text with a reviewed PDF/DOCX adapter before formatting audit."}]}
    result = audit_text(file.read_text(encoding="utf-8", errors="replace"))
    return {"path": str(file), "status": "audited", **result}
