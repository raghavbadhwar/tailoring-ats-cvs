from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from ats_agent.ingestion import ExtractionError, load


DOCUMENT_XML = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Experienced candidate built reliable Python workflow automation systems with careful human review and documented validation.</w:t></w:r></w:p>
    <w:sectPr/>
  </w:body>
</w:document>'''


class MalformedDocumentTests(unittest.TestCase):
    def _docx(
        self,
        path: Path,
        *,
        extra_entries: int = 0,
        document_xml: bytes = DOCUMENT_XML,
    ) -> None:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("word/document.xml", document_xml)
            for index in range(extra_entries):
                archive.writestr(
                    f"word/media/padding-{index}.txt",
                    "padding",
                )

    def test_oversized_input_is_blocked_before_reading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resume.txt"
            path.write_text("candidate evidence " * 20, encoding="utf-8")
            with patch("ats_agent.ingestion.MAX_INPUT_BYTES", 32):
                with self.assertRaisesRegex(ExtractionError, "input file is too large"):
                    load(path)

    def test_docx_with_excessive_archive_entries_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resume.docx"
            self._docx(path, extra_entries=4)
            with patch("ats_agent.ingestion.MAX_ARCHIVE_ENTRIES", 3):
                with self.assertRaisesRegex(ExtractionError, "too many archive entries"):
                    load(path)

    def test_docx_with_extreme_compression_ratio_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resume.docx"
            repeated = (
                b'''<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'''
                + b"safe candidate evidence " * 5000
                + b"</w:t></w:r></w:p></w:body></w:document>"
            )
            self._docx(path, document_xml=repeated)
            with patch("ats_agent.ingestion.MAX_COMPRESSION_RATIO", 2.0):
                with self.assertRaisesRegex(ExtractionError, "compression ratio"):
                    load(path)

    def test_html_ignores_script_and_style_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resume.html"
            path.write_text(
                "<html><head><style>secret-style-token</style>"
                "<script>secret-script-token</script></head>"
                "<body><h1>Projects</h1><p>Built reliable Python workflow "
                "automation with human approval and documented tests.</p></body></html>",
                encoding="utf-8",
            )
            result = load(path)["text"]
            self.assertIn("Built reliable Python", result)
            self.assertNotIn("secret-script-token", result)
            self.assertNotIn("secret-style-token", result)


if __name__ == "__main__":
    unittest.main()
