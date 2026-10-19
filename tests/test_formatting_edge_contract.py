from __future__ import annotations

import unittest
from unittest.mock import patch

from ats_agent.formatting import audit_file, audit_text
from ats_agent.ingestion import ExtractionError


class FormattingEdgeContractTests(unittest.TestCase):
    def test_empty_and_document_diagnostics_are_visible(self) -> None:
        result = audit_text("", {"has_tables": True, "headers_or_footers": True, "media_count": 1})
        self.assertEqual(result["risk_level"], "high")
        self.assertEqual({item["id"] for item in result["findings"]}, {"F1", "F5", "F6", "F7", "F8"})

    def test_extraction_failure_is_a_visible_block(self) -> None:
        with patch("ats_agent.formatting.load", side_effect=ExtractionError("bad document")):
            result = audit_file("broken.docx")
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["findings"][0]["id"], "F0")


if __name__ == "__main__":
    unittest.main()
