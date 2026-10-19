from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ats_agent.documents import docx_structure_fingerprint, patch_document
from ats_agent.ingestion import ExtractionError, load

CORPUS = Path(__file__).parent / "fixtures" / "document-regression"
MANIFEST = CORPUS / "manifest.json"
MAX_FIXTURES = 8
MAX_FIXTURE_BYTES = 128 * 1024
MAX_MANIFEST_BYTES = 8 * 1024
FIELDS = {"id", "path", "sha256", "kind", "expected_status"}


def _validated_entries(manifest_path: Path = MANIFEST) -> list[tuple[dict, Path]]:
    if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("document corpus manifest is too large")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("document corpus manifest is not valid JSON") from exc
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "fixtures"}:
        raise ValueError("document corpus manifest fields are invalid")
    fixtures = payload["fixtures"]
    if payload["schema_version"] != 1 or not isinstance(fixtures, list):
        raise ValueError("document corpus manifest schema is invalid")
    if not 1 <= len(fixtures) <= MAX_FIXTURES:
        raise ValueError("document corpus fixture count is invalid")

    root = manifest_path.parent.resolve()
    validated: list[tuple[dict, Path]] = []
    for entry in fixtures:
        if not isinstance(entry, dict) or set(entry) != FIELDS:
            raise ValueError("document corpus fixture fields are invalid")
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("document corpus fixture must stay inside the corpus")
        fixture = (root / relative).resolve()
        try:
            fixture.relative_to(root)
        except ValueError as exc:
            raise ValueError("document corpus fixture must stay inside the corpus") from exc
        if not fixture.is_file() or fixture.stat().st_size > MAX_FIXTURE_BYTES:
            raise ValueError("document corpus fixture is missing or too large")
        digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
        if digest != entry["sha256"]:
            raise ValueError(f"document corpus hash mismatch: {entry['id']}")
        validated.append((entry, fixture))
    return validated


class DocumentRegressionCorpusTests(unittest.TestCase):
    def test_manifest_hashes_are_checked_before_document_loading(self) -> None:
        entries = _validated_entries()
        self.assertEqual(len(entries), 3)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "plain-valid.txt"
            fixture.write_bytes((CORPUS / "plain-valid.txt").read_bytes() + b"tamper")
            payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
            payload["fixtures"] = [
                {**payload["fixtures"][0], "path": fixture.name}
            ]
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            with patch(f"{__name__}.load") as document_load, self.assertRaisesRegex(
                ValueError, "hash mismatch"
            ):
                for _entry, path in _validated_entries(manifest):
                    document_load(path)
            document_load.assert_not_called()

    def test_valid_documents_load_and_invalid_docx_is_rejected(self) -> None:
        for entry, fixture in _validated_entries():
            if entry["expected_status"] == "blocked":
                with self.subTest(fixture=entry["id"]), self.assertRaises(
                    ExtractionError
                ):
                    load(fixture)
            else:
                loaded = load(fixture)
                self.assertEqual(loaded["quality"]["status"], "usable")
                self.assertIn("Python", loaded["body_text"])

    def test_strict_preserve_corpus_edit_keeps_structure_and_source_bytes(self) -> None:
        source = CORPUS / "single-column-valid.docx"
        before = source.read_bytes()
        loaded = load(source)
        target = next(
            paragraph
            for paragraph in loaded["paragraphs"]
            if "Python workflow" in paragraph["text"]
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "tailored.docx"
            patch_document(
                source,
                output,
                [
                    {
                        "id": "C1",
                        "operation": "replace_span",
                        "expected_text": target["text"],
                        "replacement_text": target["text"].replace(
                            "Python workflow", "Python workflow automation"
                        ),
                        "anchor": {
                            "part": target["part"],
                            "paragraph_index": target["paragraph_index"],
                        },
                    }
                ],
                mode="strict-preserve",
            )
            self.assertEqual(
                docx_structure_fingerprint(source),
                docx_structure_fingerprint(output),
            )
            self.assertIn("workflow automation", load(output)["body_text"])
        self.assertEqual(source.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
