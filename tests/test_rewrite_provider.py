from __future__ import annotations

import unittest

from ats_agent.providers import DeterministicRewriteProvider, RewriteContext


class DeterministicRewriteProviderTests(unittest.TestCase):
    def test_provider_returns_three_distinct_role_aligned_variants(self) -> None:
        provider = DeterministicRewriteProvider()
        context = RewriteContext(
            original_text=(
                "Helped build automated procurement workflows with 42 tests."
            ),
            terms=("workflow automation",),
            target_section="projects",
            max_characters=180,
        )
        variants = provider.generate(context)
        self.assertEqual(
            {variant["id"] for variant in variants},
            {"conservative", "balanced", "compact"},
        )
        self.assertEqual(len({variant["text"] for variant in variants}), 3)
        self.assertTrue(
            any(
                "workflow automation" in variant["text"].lower()
                for variant in variants
            )
        )
        self.assertTrue(
            all(
                len(variant["text"]) <= context.max_characters
                for variant in variants
            )
        )

    def test_safe_leading_verbs_still_produce_three_non_noop_variants(self) -> None:
        provider = DeterministicRewriteProvider()
        originals = (
            "Supported agentic workflows for support triage, with reviewable implementation notes.",
            "Contributed to analytics for portfolio monitoring, with traceable operating controls.",
        )
        for original in originals:
            with self.subTest(original=original):
                variants = provider.generate(
                    RewriteContext(
                        original_text=original,
                        terms=(),
                        target_section="projects",
                        max_characters=220,
                    )
                )
                self.assertEqual(
                    {variant["id"] for variant in variants},
                    {"conservative", "balanced", "compact"},
                )
                self.assertEqual(
                    len({variant["text"] for variant in variants}),
                    3,
                )
                self.assertTrue(
                    all(variant["text"] != original for variant in variants)
                )

    def test_provider_exposes_stable_identity(self) -> None:
        provider = DeterministicRewriteProvider()
        self.assertEqual(provider.provider_id, "deterministic")
        self.assertRegex(provider.provider_version, r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
