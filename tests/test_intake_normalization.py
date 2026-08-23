"""Targeted tests for jobs_from_json_export normalization branches."""
from __future__ import annotations

import unittest

from ats_agent.intake import jobs_from_json_export


class JsonExportNormalizationTests(unittest.TestCase):
    def test_dict_jobs_list_with_fallback_and_defaults(self):
        payload = {"jobs": [
            {"id": "a", "company": "Acme", "role": "Analyst",
             "job_url": "https://x/a"},
            {"id": "b", "url": "https://x/b", "title": "Engineer",
             "fallback": {"description": "captured text",
                          "fetched_at": "2026-01-01T00:00:00Z"}},
            {"no_url": True},
            "not-a-dict",
        ]}
        jobs = jobs_from_json_export(payload)
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0]["source"], "json_export")
        self.assertEqual(jobs[0]["description"], "")
        self.assertEqual(jobs[1]["role"], "Engineer")
        self.assertEqual(jobs[1]["description"], "captured text")
        self.assertEqual(jobs[1]["fetched_at"], "2026-01-01T00:00:00Z")

    def test_bare_list_payload(self):
        jobs = jobs_from_json_export([
            {"hostedUrl": "https://j/1", "role": "Intern"}
        ])
        self.assertEqual(jobs[0]["job_url"], "https://j/1")

    def test_empty_shapes(self):
        self.assertEqual(jobs_from_json_export({}), [])
        self.assertEqual(jobs_from_json_export({"jobs": []}), [])


if __name__ == "__main__":
    unittest.main()
