"""Safe, local document ingestion with extraction-quality diagnostics."""
from __future__ import annotations

import hashlib
import re
import zipfile
from html import unescape
from html.parser import HTMLParser
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

# Conservative local-processing limits. They are deliberately module-level so
# integrators can lower them for constrained environments and tests can verify
# the fail-closed behavior without allocating large files.
MAX_INPUT_BYTES = 25 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 512
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100.0


class ExtractionError(ValueError):
    pass


class _TextHTMLParser(HTMLParser):
    """Extract visible HTML text while ignoring executable and style content."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs
        if tag.lower() in {"script", "style", "noscript", "template"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if (
            tag.lower() in {"script", "style", "noscript", "template"}
            and self._ignored_depth
        ):
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth and data.strip():
            self.parts.append(data.strip())


def _paragraphs_from_text(text: str, part: str = "text") -> list[dict]:
    return [
        {
            "part": part,
            "paragraph_index": None,
            "line_number": line_number,
            "text": line.strip(),
        }
        for line_number, line in enumerate(text.splitlines(), 1)
        if line.strip()
    ]


def _xml_paragraphs(xml: bytes, part: str) -> list[dict]:
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise ExtractionError(
            f"DOCX XML extraction failed in {part}: {exc}"
        ) from exc
    result: list[dict] = []
    for paragraph_index, paragraph in enumerate(root.iter(WORD_NS + "p")):
        text = "".join(
            node.text or "" for node in paragraph.iter(WORD_NS + "t")
        )
        if text.strip():
            result.append(
                {
                    "part": part,
                    "paragraph_index": paragraph_index,
                    "line_number": None,
                    "text": text,
                }
            )
    return result


def _validate_archive(archive: zipfile.ZipFile) -> None:
    """Reject archives that could exhaust memory or hide decompression abuse."""

    entries = [item for item in archive.infolist() if not item.is_dir()]
    if len(entries) > MAX_ARCHIVE_ENTRIES:
        raise ExtractionError(
            "DOCX extraction failed: too many archive entries "
            f"({len(entries)} > {MAX_ARCHIVE_ENTRIES})"
        )

    total_uncompressed = sum(item.file_size for item in entries)
    if total_uncompressed > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
        raise ExtractionError(
            "DOCX extraction failed: uncompressed archive is too large "
            f"({total_uncompressed} bytes)"
        )

    total_compressed = sum(item.compress_size for item in entries)
    ratio = total_uncompressed / max(total_compressed, 1)
    if ratio > MAX_COMPRESSION_RATIO:
        raise ExtractionError(
            "DOCX extraction failed: archive compression ratio "
            f"{ratio:.1f} exceeds {MAX_COMPRESSION_RATIO:.1f}"
        )


def _docx(path: Path) -> tuple[str, str, list[dict], dict]:
    try:
        with zipfile.ZipFile(path) as archive:
            _validate_archive(archive)
            names = set(archive.namelist())
            if "word/document.xml" not in names:
                raise ExtractionError(
                    "DOCX extraction failed: word/document.xml is missing"
                )
            document_xml = archive.read("word/document.xml")
            body = _xml_paragraphs(document_xml, "word/document.xml")
            ancillary: list[dict] = []
            for name in sorted(names):
                if re.fullmatch(r"word/(?:header|footer)\d+\.xml", name):
                    ancillary.extend(_xml_paragraphs(archive.read(name), name))
            media_count = sum(name.startswith("word/media/") for name in names)
            has_tables = b"<w:tbl" in document_xml
    except ExtractionError:
        raise
    except (zipfile.BadZipFile, OSError, KeyError) as exc:
        raise ExtractionError(f"DOCX extraction failed: {exc}") from exc
    body_text = "\n".join(item["text"] for item in body)
    all_text = "\n".join(item["text"] for item in [*ancillary, *body])
    diagnostics = {
        "headers_or_footers": bool(ancillary),
        "media_count": media_count,
        "has_tables": has_tables,
        "body_paragraphs": len(body),
        "ancillary_paragraphs": len(ancillary),
    }
    return all_text, body_text, [*ancillary, *body], diagnostics


def _pdf(path: Path) -> tuple[str, list[dict]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ExtractionError(
            "PDF extraction requires the optional 'pypdf' dependency"
        ) from exc
    try:
        pages = [page.extract_text() or "" for page in PdfReader(str(path)).pages]
    except Exception as exc:
        raise ExtractionError(f"PDF extraction failed: {exc}") from exc
    text = "\n".join(pages)
    paragraphs: list[dict] = []
    for page_index, page_text in enumerate(pages):
        for line_number, line in enumerate(page_text.splitlines(), 1):
            if line.strip():
                paragraphs.append(
                    {
                        "part": f"page:{page_index + 1}",
                        "paragraph_index": None,
                        "line_number": line_number,
                        "text": line.strip(),
                    }
                )
    return text, paragraphs


def _rtf_to_text(text: str) -> str:
    text = re.sub(r"\\par[d]?\b", "\n", text)
    text = re.sub(r"\\'[0-9a-fA-F]{2}", " ", text)
    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", text)
    text = text.replace("{", "").replace("}", "")
    return unescape(text)


def _html_to_text(text: str) -> str:
    parser = _TextHTMLParser()
    parser.feed(text)
    parser.close()
    return "\n".join(parser.parts)


def _quality(text: str) -> dict:
    words = re.findall(r"\b\w+[’'-]?\w*\b", text)
    replacement_ratio = text.count("\ufffd") / max(len(text), 1)
    printable_ratio = sum(
        char.isprintable() or char in "\n\t" for char in text
    ) / max(len(text), 1)
    score = 1.0
    if len(words) < 10:
        score -= 0.35
    if replacement_ratio > 0.01:
        score -= 0.35
    if printable_ratio < 0.95:
        score -= 0.35
    return {
        "score": max(0.0, round(score, 3)),
        "word_count": len(words),
        "replacement_character_ratio": replacement_ratio,
        "printable_ratio": printable_ratio,
        "status": (
            "usable"
            if words and replacement_ratio <= 0.1 and printable_ratio >= 0.8
            else "blocked"
        ),
    }


def _validate_input_path(path: Path) -> None:
    if not path.is_file():
        raise ExtractionError(f"input file does not exist: {path}")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ExtractionError(f"cannot inspect input file: {exc}") from exc
    if size > MAX_INPUT_BYTES:
        raise ExtractionError(
            "input file is too large "
            f"({size} bytes > {MAX_INPUT_BYTES} bytes)"
        )


def load(path: Path) -> dict:
    path = path.expanduser().resolve()
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        raise ExtractionError(
            f"unsupported document type: {suffix or '<none>'}"
        )
    _validate_input_path(path)

    diagnostics: dict = {}
    if suffix == ".docx":
        text, body_text, paragraphs, diagnostics = _docx(path)
    elif suffix == ".pdf":
        text, paragraphs = _pdf(path)
        body_text = text
        diagnostics = {"input_only": True}
    else:
        raw = path.read_text(encoding="utf-8", errors="replace")
        if suffix in {".html", ".htm"}:
            text = _html_to_text(raw)
        elif suffix == ".rtf":
            text = _rtf_to_text(raw)
        else:
            text = raw
        body_text = text
        paragraphs = _paragraphs_from_text(text)
    quality = _quality(text)
    if quality["status"] == "blocked":
        raise ExtractionError(
            "document_extraction_required: insufficient extractable text"
        )
    return {
        "path": str(path),
        "format": suffix.lstrip("."),
        "text": text,
        "body_text": body_text,
        "paragraphs": paragraphs,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "word_count": quality["word_count"],
        "quality": quality,
        "diagnostics": diagnostics,
    }


def extract(path: Path) -> str:
    return load(path)["text"]


def write_docx(path: Path, text: str) -> None:
    # Backward-compatible alias. The implementation lives in documents.py to
    # keep ingestion read-focused.
    from .documents import write_ats_docx

    write_ats_docx(path, text)
