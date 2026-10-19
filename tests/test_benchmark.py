from __future__ import annotations

import unittest

from ats_agent.benchmark import run


class BenchmarkTests(unittest.TestCase):
    def assert_report_is_honest(self, result: dict) -> None:
        self.assertGreater(result["case_count"], 0)
        self.assertIn("measurement_status", result)
        self.assertIsNone(result["human_rewrite_preference"])

    def test_quick_benchmark_meets_release_gate(self):
        self.assert_report_is_honest(run(suite="quick"))

    def test_full_benchmark_meets_release_gate(self):
        self.assert_report_is_honest(run(suite="full"))


if __name__ == "__main__":
    unittest.main()
