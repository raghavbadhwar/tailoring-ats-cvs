from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ats_agent import __version__
from ats_agent.cli import main
from ats_agent.hashing import verify_proposal_digest


class AgentCliHealthTests(unittest.TestCase):
    def run_cli(self, argv: list[str]) -> tuple[int, dict]:
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(argv)
        return code, json.loads(stdout.getvalue())

    def test_doctor_contract(self) -> None:
        code, payload = self.run_cli(["doctor"])
        self.assertEqual(code, 0)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["package"]["version"], __version__)

    def test_strict_doctor_smoke(self) -> None:
        code, payload = self.run_cli(["doctor", "--strict"])
        self.assertEqual(code, 0)
        self.assertEqual(payload["strict_check"]["status"], "passed")
        self.assertTrue(payload["strict_check"]["output_validated"])

    def test_audit_returns_a_digest_bound_draft(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume = root / "resume.txt"
            job = root / "job.txt"
            resume.write_text("PROJECTS\n- Built workflow automation.\n", encoding="utf-8")
            job.write_text("Workflow automation is required.\n", encoding="utf-8")
            code, payload = self.run_cli(["audit", str(resume), str(job)])
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "draft")
        self.assertEqual(verify_proposal_digest(payload), payload["proposal_digest"])
