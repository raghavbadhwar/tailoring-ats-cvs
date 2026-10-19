"""Targeted tests for jobs_from_json_export normalization branches."""
from __future__ import annotations

import unittest
import socket
from unittest.mock import patch

from ats_agent.intake import jobs_from_json_export


class JsonExportNormalizationTests(unittest.TestCase):
    def setUp(self):
        dns = patch("ats_agent.capture.socket.getaddrinfo", return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        ])
        dns.start()
        self.addCleanup(dns.stop)

    def test_dict_jobs_list_with_fallback_and_defaults(self):
        payload = {"jobs": [
            {"id": "a", "company": "Acme", "role": "Analyst",
             "job_url": "https://x/a"},
            {"id": "b", "url": "https://x/b", "title": "Engineer",
             "fallback": {"description": "captured text",
                          "provider": "Test Aggregator", "source_url": "https://x/listing",
                          "fetched_at": "2026-01-01T00:00:00Z"}},
            {"no_url": True},
            "not-a-dict",
        ]}
        jobs = jobs_from_json_export(payload)
        self.assertEqual(len(jobs), 4)
        self.assertEqual(jobs[0]["source_status"], "draft")
        self.assertEqual(jobs[1]["role"], "Engineer")
        self.assertEqual(jobs[1]["fallback"]["description"], "captured text")
        self.assertEqual(jobs[1]["fallback"]["source_type"], "aggregator_fallback")
        self.assertEqual(jobs[1]["fallback"]["fetched_at"], "2026-01-01T00:00:00Z")
        self.assertTrue(all(job["import_status"] == "blocked_import" for job in jobs[2:]))

    def test_bare_list_payload(self):
        jobs = jobs_from_json_export([
            {"hostedUrl": "https://j/1", "role": "Intern"}
        ])
        self.assertEqual(jobs[0]["job_url"], "https://j/1")

    def test_empty_shapes(self):
        for payload in ({}, {"jobs": []}):
            with self.assertRaisesRegex(ValueError, "between 1"):
                jobs_from_json_export(payload)


if __name__ == "__main__":
    unittest.main()
