from __future__ import annotations

import unittest
from unittest.mock import patch

from pydantic import ValidationError

from ats_agent.job_search import IntakeAnswers, _linkedin_cards, intake_questions, search_public_jobs


def _answers(**changes: object) -> IntakeAnswers:
    values: dict[str, object] = {
        "role_queries": ["Product Analyst"],
        "locations": ["Worldwide"],
        "work_modes": ["remote"],
        "work_authorization": "India",
        "sponsorship": "unknown",
        "relocation": "case-by-case",
        "availability": "Immediately",
        "deal_breakers": [],
        "use_linkedin_public_jobs": False,
    }
    values.update(changes)
    return IntakeAnswers.model_validate(values)


class JobSearchTests(unittest.TestCase):
    def test_intake_requires_candidate_location_and_work_mode(self) -> None:
        questions = {item["id"] for item in intake_questions(["Product Analyst"])}
        self.assertTrue({"locations", "work_modes", "work_authorization"} <= questions)
        with self.assertRaises(ValidationError):
            _answers(locations=["Remote", "remote"])

    def test_linkedin_public_cards_are_normalized(self) -> None:
        cards = _linkedin_cards(
            '''<li data-entity-urn="urn:li:jobPosting:12345">
            <h3 class="base-search-card__title"> Senior &amp; Product Analyst </h3>
            <h4 class="base-search-card__subtitle"> Example Co </h4>
            <span class="job-search-card__location"> London, UK </span>
            <time class="job-search-card__listdate" datetime="2026-08-16"></time></li>''',
            "hybrid",
        )
        self.assertEqual(cards[0]["external_id"], "12345")
        self.assertEqual(cards[0]["title"], "Senior & Product Analyst")
        self.assertEqual(cards[0]["work_mode"], "hybrid")

    def test_search_is_opt_in_bounded_and_deduplicated(self) -> None:
        job = {
            "source": "freehire",
            "external_id": "one",
            "title": "Product Analyst",
            "company": "Example Co",
            "location": "Remote",
            "work_mode": "remote",
            "posted_at": "2026-08-16",
            "job_url": "https://jobs.example.com/one",
            "description": "Analyse product performance using SQL.",
            "provider_url": "https://freehire.me/jobs/one",
        }
        with patch("ats_agent.job_search._freehire", return_value=[job, dict(job)]), patch(
            "ats_agent.job_search._linkedin"
        ) as linkedin:
            result = search_public_jobs(_answers())
        linkedin.assert_not_called()
        self.assertEqual(result["request_count"], 1)
        self.assertEqual(len(result["jobs"]), 1)
        self.assertIn("jurisdiction", result["jobs"][0]["eligibility_note"])


if __name__ == "__main__":
    unittest.main()
