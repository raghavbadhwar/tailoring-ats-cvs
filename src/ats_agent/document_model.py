"""Normalized, read-only document model used by evidence and document checks."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from .ingestion import load
from .models import ArtifactFingerprint


class TextRun(BaseModel):
    run_id: str
    text: str
    style_fingerprint: str = "unknown"
    hyperlink_target: str | None = None


class DocumentParagraph(BaseModel):
    paragraph_id: str
    part: str
    table_path: tuple[int, ...] = ()
    style_name: str | None = None
    runs: tuple[TextRun, ...]
    text: str


class DocumentModel(BaseModel):
    artifact: ArtifactFingerprint
    paragraphs: tuple[DocumentParagraph, ...]
    reading_order: tuple[str, ...]
    diagnostics: tuple[str, ...] = ()


def parse_document(artifact: ArtifactFingerprint) -> DocumentModel:
    parsed = load(Path(artifact.path))
    paragraphs = tuple(DocumentParagraph(paragraph_id=f"P{index}", part=str(item["part"]),
        runs=(TextRun(run_id=f"P{index}:R0", text=str(item["text"])),), text=str(item["text"]))
        for index, item in enumerate(parsed["paragraphs"], 1))
    diagnostics = tuple(f"{key}:{value}" for key, value in parsed.get("diagnostics", {}).items())
    return DocumentModel(artifact=artifact, paragraphs=paragraphs, reading_order=tuple(p.paragraph_id for p in paragraphs), diagnostics=diagnostics)
