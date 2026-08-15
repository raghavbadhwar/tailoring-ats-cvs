from __future__ import annotations

import hashlib
import re
import zipfile
from html import unescape
from pathlib import Path
from xml.etree import ElementTree

SUPPORTED = {".txt", ".md", ".markdown", ".rtf", ".html", ".htm", ".docx", ".pdf"}


class ExtractionError(ValueError):
    pass


def _docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
        root = ElementTree.fromstring(xml)
    except (KeyError, OSError, ElementTree.ParseError) as exc:
        raise ExtractionError(f"DOCX extraction failed: {exc}") from exc
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    lines: list[str] = []
    for paragraph in root.iter(ns + "p"):
        text = "".join(node.text or "" for node in paragraph.iter(ns + "t"))
        if text.strip():
            lines.append(text)
    return "\n".join(lines)


def _pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader  # optional dependency; absence is a safe block
    except ImportError as exc:
        raise ExtractionError("PDF extraction requires the optional 'pypdf' dependency") from exc
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
    if not words or ("\ufffd" in text and text.count("\ufffd") > max(2, len(text) // 10)):
        raise ExtractionError("document_extraction_required: insufficient extractable text")
    return text


def load(path: Path) -> dict:
    text = extract(path)
    return {"path": str(path), "text": text, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "word_count": len(re.findall(r"\b\w+\b", text))}


def write_docx(path: Path, text: str) -> None:
    escaped = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
               .replace('"', "&quot;"))
    paragraphs = "".join(f"<w:p><w:r><w:t xml:space=\"preserve\">{line}</w:t></w:r></w:p>" for line in escaped.splitlines() or [""])
    document = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{paragraphs}<w:sectPr/></w:body></w:document>'''
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'''
    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'''
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)
