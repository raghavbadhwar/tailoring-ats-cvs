from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from docx import Document


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "capability-upgrade" / "cases.json"


class CapabilityUpgradeFixtureTests(unittest.TestCase):
    def test_sanitized_pilot_shapes_are_complete_and_pii_free(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        for marker in ("@", "linkedin", "raghav", "srcc"):
            self.assertNotIn(marker, json.dumps(payload).lower())
        self.assertIn("CGPA 8.55", payload["resume"])
        self.assertIn("CGPA 8.82", payload["supporting_evidence"])
        self.assertIn("6-12 months", payload["zurich_job"])
        self.assertIn("A/B testing", payload["tiktok_job"])
        self.assertEqual(payload["cheq_fallback"]["provider"], "Sanitized Listing Provider")

        with tempfile.TemporaryDirectory() as directory:
            docx = Path(directory) / "sanitized-resume.docx"
            document = Document()
            document.add_paragraph(payload["resume"])
            document.save(docx)
            self.assertTrue(docx.is_file())


if __name__ == "__main__":
    unittest.main()
