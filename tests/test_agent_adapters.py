"""Compatibility checks retained for the original adapter test module name."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AgentAdapterTests(unittest.TestCase):
    def test_version_and_bundle_builder(self) -> None:
        result = subprocess.run([sys.executable, "-m", "ats_agent.cli", "--version"], cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "1.0.0b4")
