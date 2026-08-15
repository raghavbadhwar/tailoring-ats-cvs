from __future__ import annotations

import hashlib
import re
import zipfile
from html import unescape
from pathlib import Path
from xml.etree import ElementTree

SUPPORTED = {
    ".txt",
    ".md",
    ".markdown",
    ".rtf",
    ".html",
    ".htm",
    ".docx",
    ".pdf",
}
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class ExtractionError(ValueError):
    pass


def _xml_paragraphs(xml: bytes) -> list[str]:
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise ExtractionError(f"DOCX XML extraction failed: {exc}") from exc

    lines: list[str] = []
    for paragraph in root.iter(WORD_NS + "p"):
        fragments: list[str] = []
        for node in paragraph.iter():
            if node.tag == WORD_NS + "t":
                fragments.append(node.text or "")
            elif node.tag == WORD_NS + "tab":
                fragments.append("\t")
            elif node.tag in {WORD_NS + "br", WORD_NS + "cr"}:
                fragments.append("\n")
        text = "".join(fragments)
        if text.strip():
            lines.append(text)
    return lines


def _docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if "word/document.xml" not in names:
                raise ExtractionError("DOCX is missing word/document.xml")
            header_parts = sorted(
                name
                for name in names
                if re.fullmatch(r"word/header\d+\.xml", name)
            )
            footer_parts = sorted(
                name
                for name in names
                if re.fullmatch(r"word/footer\d+\.xml", name)
            )
            parts = [*header_parts, "word/document.xml", *footer_parts]
            lines = [
                line
                for part in parts
                for line in _xml_paragraphs(archive.read(part))
            ]
    except ExtractionError:
        raise
    except (KeyError, OSError, zipfile.BadZipFile) as exc:
        raise ExtractionError(f"DOCX extraction failed: {exc}") from exc
    return "\n".join(lines)


def _pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader  # optional dependency; absence is a safe block
    except ImportError as exc:
        raise ExtractionError(
            "PDF extraction requires the optional 'pypdf' dependency"
        ) from exc
    try:
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    except Exception as exc:  # parser-specific errors must become a safe extraction block
        raise ExtractionError(f"PDF extraction failed: {exc}") from exc


def extract(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        raise ExtractionError(f"unsupported document type: {suffix or '<none>'}")
    if suffix == ".docx":
        text = _docx_text(path)
    elif suffix == ".pdf":
        text = _pdf_text(path)
    else:
        text = path.read_text(encoding="utf-8", errors="replace")
        if suffix in {".html", ".htm"}:
            text = re.sub(r"<[^>]+>", " ", unescape(text))
    words = re.findall(r"\b\w+\b", text)
    if not words or (
        "\ufffd" in text and text.count("\ufffd") > max(2, len(text) // 10)
    ):
        raise ExtractionError(
            "document_extraction_required: insufficient extractable text"
        )
    return text


def load(path: Path) -> dict:
    text = extract(path)
    return {
        "path": str(path),
        "text": text,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "word_count": len(re.findall(r"\b\w+\b", text)),
    }


def write_docx(path: Path, text: str) -> None:
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    paragraphs = "".join(
        (
            '<w:p><w:r><w:t xml:space="preserve">'
            f"{line}</w:t></w:r></w:p>"
        )
        for line in escaped.splitlines() or [""]
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{paragraphs}<w:sectPr/></w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)
