from __future__ import annotations

import unittest

from ats_agent.benchmark import run


class BenchmarkTests(unittest.TestCase):
    def assert_release_metrics(self, result: dict, expected_cases: int) -> None:
        self.assertEqual(result["case_count"], expected_cases)
        self.assertEqual(result["status"], "passed", result["failures"])
        metrics = result["metrics"]
        self.assertGreaterEqual(metrics["supported_requirement_recall"], 0.90)
        self.assertGreaterEqual(metrics["unsupported_requirement_accuracy"], 0.90)
        self.assertGreaterEqual(metrics["hard_gate_recall"], 0.90)
        self.assertEqual(metrics["evidence_provenance_coverage"], 1.0)
        self.assertEqual(metrics["ownership_escalation_rate"], 0.0)
        self.assertEqual(metrics["incomplete_rewrite_rate"], 0.0)
        self.assertEqual(metrics["unsupported_term_insertion_rate"], 0.0)

    def test_quick_benchmark_meets_release_gate(self):
        self.assert_release_metrics(run(suite="quick"), 20)

    def test_full_benchmark_meets_release_gate(self):
        self.assert_release_metrics(run(suite="full"), 100)


if __name__ == "__main__":
    unittest.main()
