"""Anchored text and structure-preserving DOCX edit operations."""
from __future__ import annotations

import copy
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from defusedxml.ElementTree import fromstring as safe_fromstring

from .ingestion import WORD_NS, load

REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
W_NS_URI = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
SUPPORTED_PRESERVE_PARTS = {None, "", "text", "word/document.xml"}
ALLOWED_OUTPUT_SUFFIXES = {".txt", ".md", ".markdown", ".docx"}
ElementTree.register_namespace("w", W_NS_URI)


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _paragraph_xml(text: str) -> str:
    stripped = text.strip()
    is_heading = stripped.upper() == stripped and 0 < len(stripped.split()) <= 5
    is_bullet = bool(re.match(r"^[-*•]\s*", stripped))
    clean = re.sub(r"^[-*•]\s*", "", stripped)
    ppr = ""
    if is_heading:
        ppr = '<w:pPr><w:pStyle w:val="Heading2"/></w:pPr>'
    elif is_bullet:
        ppr = '<w:pPr><w:pStyle w:val="ListBullet"/></w:pPr>'
    return (
        f'<w:p>{ppr}<w:r><w:t xml:space="preserve">'
        f"{_xml_escape(clean)}</w:t></w:r></w:p>"
    )


def write_ats_docx(path: Path, text: str) -> None:
    path = path.expanduser().resolve()
    paragraphs = "".join(
        _paragraph_xml(line) for line in text.splitlines() if line.strip()
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W_NS_URI}">'
        f"<w:body>{paragraphs}<w:sectPr/></w:body></w:document>"
    )
    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:styles xmlns:w="{W_NS_URI}">'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
        '<w:name w:val="Normal"/></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading2">'
        '<w:name w:val="heading 2"/><w:rPr><w:b/><w:sz w:val="22"/>'
        "</w:rPr></w:style>"
        '<w:style w:type="paragraph" w:styleId="ListBullet">'
        '<w:name w:val="List Bullet"/></w:style>'
        "</w:styles>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.'
        'wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.'
        'wordprocessingml.styles+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{REL_NS}">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        'relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )
    doc_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{REL_NS}">'
        '<Relationship Id="rIdStyles" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        'relationships/styles" Target="styles.xml"/>'
        "</Relationships>"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)
        archive.writestr("word/styles.xml", styles)
        archive.writestr("word/_rels/document.xml.rels", doc_rels)


def _paragraph_text(paragraph: ElementTree.Element) -> str:
    return "".join(
        node.text or "" for node in paragraph.iter(WORD_NS + "t")
    )


def _set_text_node(node: ElementTree.Element, text: str) -> None:
    node.text = text
    if text.startswith(" ") or text.endswith(" "):
        node.set(XML_SPACE, "preserve")
    else:
        node.attrib.pop(XML_SPACE, None)


def _replace_paragraph_span(
    paragraph: ElementTree.Element,
    expected: str,
    replacement: str,
) -> None:
    """Replace one exact paragraph span without flattening unaffected runs."""

    text_nodes = list(paragraph.iter(WORD_NS + "t"))
    current = "".join(node.text or "" for node in text_nodes)
    if current.count(expected) != 1:
        raise ValueError(
            "expected text is missing or ambiguous in anchored paragraph"
        )

    start = current.index(expected)
    end = start + len(expected)
    cursor = 0
    affected: list[tuple[ElementTree.Element, int, int, str]] = []
    for node in text_nodes:
        node_text = node.text or ""
        node_start = cursor
        node_end = cursor + len(node_text)
        cursor = node_end
        if node_end > start and node_start < end:
            affected.append((node, node_start, node_end, node_text))

    if not affected:
        raise ValueError("expected text has no editable DOCX text nodes")

    first_node, first_start, first_end, first_text = affected[0]
    prefix = first_text[: max(start - first_start, 0)]
    if len(affected) == 1:
        suffix = first_text[max(end - first_start, 0) :]
        _set_text_node(first_node, prefix + replacement + suffix)
        return

    _set_text_node(first_node, prefix + replacement)
    for node, _, _, _ in affected[1:-1]:
        _set_text_node(node, "")

    last_node, last_start, _, last_text = affected[-1]
    suffix = last_text[max(end - last_start, 0) :]
    _set_text_node(last_node, suffix)


def _find_paragraph(
    paragraphs: list[ElementTree.Element],
    anchor: dict,
    expected: str,
) -> tuple[int, ElementTree.Element]:
    index = anchor.get("paragraph_index")
    if isinstance(index, int) and 0 <= index < len(paragraphs):
        paragraph = paragraphs[index]
        if not expected or expected in _paragraph_text(paragraph):
            return index, paragraph
    candidates = [
        (i, paragraph)
        for i, paragraph in enumerate(paragraphs)
        if expected and expected in _paragraph_text(paragraph)
    ]
    if len(candidates) != 1:
        state = "missing" if not candidates else "ambiguous"
        raise ValueError(
            f"document anchor is {state} for text: {expected!r}"
        )
    return candidates[0]


def _new_paragraph_like(
    anchor: ElementTree.Element,
    text: str,
) -> ElementTree.Element:
    paragraph = ElementTree.Element(WORD_NS + "p")
    ppr = anchor.find(WORD_NS + "pPr")
    if ppr is not None:
        paragraph.append(copy.deepcopy(ppr))
    run = ElementTree.SubElement(paragraph, WORD_NS + "r")
    node = ElementTree.SubElement(run, WORD_NS + "t")
    _set_text_node(node, text)
    return paragraph


def _validate_preserve_parts(changes: list[dict]) -> None:
    for change in changes:
        anchor = change.get("anchor") or {}
        part = anchor.get("part")
        if part not in SUPPORTED_PRESERVE_PARTS:
            raise ValueError(
                f"unsupported DOCX part for preserve edit: {part}"
            )


def _parent_map(root: ElementTree.Element) -> dict[ElementTree.Element, ElementTree.Element]:
    return {
        child: parent
        for parent in root.iter()
        for child in list(parent)
    }


def _patch_docx_xml(xml: bytes, changes: list[dict]) -> bytes:
    _validate_preserve_parts(changes)
    root = safe_fromstring(xml)
    body = root.find(WORD_NS + "body")
    if body is None:
        raise ValueError("DOCX body is missing")
    paragraphs = list(body.iter(WORD_NS + "p"))

    replacements = [
        change
        for change in changes
        if change["operation"] in {"replace", "replace_span", "delete_span"}
    ]
    inserts = [
        change
        for change in changes
        if change["operation"] in {"insert_after", "insert_before"}
    ]
    for change in replacements:
        _, paragraph = _find_paragraph(
            paragraphs,
            change.get("anchor") or {},
            change["expected_text"],
        )
        replacement = (
            "" if change["operation"] == "delete_span" else change["replacement_text"]
        )
        try:
            _replace_paragraph_span(
                paragraph,
                change["expected_text"],
                replacement,
            )
        except ValueError as exc:
            raise ValueError(f"change {change['id']} {exc}") from exc

    insertion_records: list[
        tuple[int, dict, ElementTree.Element, ElementTree.Element]
    ] = []
    paragraphs = list(body.iter(WORD_NS + "p"))
    parents = _parent_map(root)
    for change in inserts:
        index, paragraph = _find_paragraph(
            paragraphs,
            change.get("anchor") or {},
            change.get("expected_text", ""),
        )
        parent = parents.get(paragraph)
        if parent is None:
            raise ValueError(
                f"change {change['id']} anchored paragraph has no XML parent"
            )
        insertion_records.append((index, change, paragraph, parent))

    for _, change, paragraph, parent in sorted(
        insertion_records,
        key=lambda item: item[0],
        reverse=True,
    ):
        children = list(parent)
        child_index = children.index(paragraph)
        offset = 1 if change["operation"] == "insert_after" else 0
        parent.insert(
            child_index + offset,
            _new_paragraph_like(paragraph, change["replacement_text"]),
        )

    return ElementTree.tostring(
        root,
        encoding="utf-8",
        xml_declaration=True,
    )


def _apply_text(text: str, changes: list[dict]) -> str:
    result = text
    for change in [
        item
        for item in changes
        if item["operation"] in {"replace", "replace_span", "delete_span"}
    ]:
        expected = change["expected_text"]
        if result.count(expected) != 1:
            raise ValueError(
                f"change {change['id']} expected text was not found exactly once"
            )
        replacement = (
            "" if change["operation"] == "delete_span" else change["replacement_text"]
        )
        result = result.replace(expected, replacement, 1)

    for change in [
        item
        for item in changes
        if item["operation"] in {"insert_after", "insert_before"}
    ]:
        anchor = change.get("anchor") or {}
        expected = change.get("expected_text") or anchor.get("heading") or ""
        current_lines = result.splitlines()
        if expected:
            matches = [
                index
                for index, line in enumerate(current_lines)
                if expected == line.strip() or expected in line
            ]
        else:
            line_number = anchor.get("line_number")
            matches = (
                [int(line_number) - 1]
                if isinstance(line_number, int)
                and 0 < line_number <= len(current_lines)
                else []
            )
        if len(matches) != 1:
            raise ValueError(
                f"change {change['id']} insertion anchor is missing or ambiguous"
            )
        offset = 1 if change["operation"] == "insert_after" else 0
        position = matches[0] + offset
        current_lines.insert(
            position,
            "- " + change["replacement_text"].lstrip("-*• "),
        )
        trailing = "\n" if text.endswith("\n") else ""
        result = "\n".join(current_lines) + trailing
    return result


def patch_document(
    source: Path,
    output: Path,
    changes: list[dict],
    *,
    mode: str = "preserve",
) -> None:
    source = source.expanduser().resolve()
    output = output.expanduser().resolve()
    if output == source:
        raise ValueError("output must not overwrite the source")
    output_suffix = output.suffix.lower()
    if output_suffix == ".pdf":
        raise ValueError(
            "PDF output requires a genuine PDF renderer; choose DOCX or text output"
        )
    if output_suffix not in ALLOWED_OUTPUT_SUFFIXES:
        raise ValueError(
            "unsupported output format: "
            f"{output_suffix or '<none>'}; choose TXT, Markdown, or DOCX"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    source_suffix = source.suffix.lower()
    if (
        source_suffix == ".docx"
        and output_suffix == ".docx"
        and mode == "preserve"
    ):
        with zipfile.ZipFile(source) as archive:
            names = archive.namelist()
            files = {name: archive.read(name) for name in names}
        files["word/document.xml"] = _patch_docx_xml(
            files["word/document.xml"],
            changes,
        )
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in files.items():
                archive.writestr(name, data)
        return

    loaded = load(source)
    updated = _apply_text(loaded["body_text"], changes)
    if output_suffix == ".docx":
        write_ats_docx(output, updated)
    else:
        output.write_text(updated, encoding="utf-8")
