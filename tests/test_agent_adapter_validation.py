from __future__ import annotations

import unittest
from pathlib import Path

from scripts.validate_agent_adapters import validate_repository


class AgentAdapterValidationTests(unittest.TestCase):
    def test_repository_agent_adapters_are_valid(self) -> None:
        diagnostics = validate_repository(Path(__file__).resolve().parents[1])
        self.assertEqual(diagnostics["errors"], [])
        self.assertTrue(diagnostics["explicit_install_approval"])
        self.assertTrue(diagnostics["explicit_change_approval"])
