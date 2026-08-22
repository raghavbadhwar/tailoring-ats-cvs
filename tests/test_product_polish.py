"""Regression tests for product-polish fixes: segmentation, degree aliases,
variant distinctness, and related-content anchoring."""

import unittest

from ats_agent.evidence import EvidenceItem, EvidenceLedger
from ats_agent.providers import DeterministicRewriteProvider, RewriteContext
from ats_agent.requirements import extract_requirements
from ats_agent.rewriting import _find_section_anchor


def _item(
    item_id: str,
    text: str,
    *,
    source: str = "resume",
    line_number: int | None = 1,
    paragraph_index: int | None = None,
    part: str = "text",
) -> EvidenceItem:
    return EvidenceItem(
        id=item_id,
        candidate_id="candidate-2026",
        text=text,
        source=source,
        source_file="resume.txt" if source == "resume" else "evidence.md",
        source_span=f"line {line_number}",
        line_number=line_number,
        paragraph_index=paragraph_index,
        part=part,
        ownership="direct",
    )


class SegmentationTests(unittest.TestCase):
    def test_unpunctuated_bullet_lines_become_segments(self):
        jd = (
            "Junior analyst role\n"
            "## Requirements\n"
            "- Strong SQL skills with experience on large datasets\n"
            "- Hands-on Power BI or Tableau\n"
            "- Experience running A/B tests is required\n"
            "- Bachelor's degree in commerce or economics\n"
        )
        terms = {
            term
            for requirement in extract_requirements(jd)
            for term in requirement["normalized_terms"]
        }
        self.assertIn("sql", terms)
        self.assertIn("power bi", terms)
        self.assertIn("tableau", terms)
        self.assertIn("a/b testing", terms)

    def test_degree_requirement_extracts_once_not_as_skill(self):
        jd = "Bachelor's degree in commerce, economics, or related field\n"
        requirements = extract_requirements(jd)
        degrees = [r for r in requirements if r["kind"] == "degree"]
        skills = [r for r in requirements if r["kind"] == "skill"]
        self.assertEqual(len(degrees), 1)
        self.assertEqual(degrees[0]["normalized_terms"], ["bachelor"])
        self.assertFalse(any("bachelor" in r["normalized_terms"] for r in skills))


class DegreeAliasTests(unittest.TestCase):
    def test_bcom_evidence_satisfies_bachelor_term(self):
        from ats_agent.requirements import _alias_match

        self.assertTrue(_alias_match("bachelor", "B.Com (Hons), Christ University"))
        self.assertTrue(_alias_match("master", "MBA, Christ University"))

    def test_disavowal_lines_never_count_as_coverage(self):
        from ats_agent.requirements import _alias_match

        self.assertFalse(_alias_match("a/b testing", "No A/B testing experience."))
        self.assertFalse(
            _alias_match("aws", "No cloud platform experience (no AWS/GCP/Azure).")
        )
        self.assertFalse(_alias_match("tableau", "Explicit non-evidence: never used Tableau."))
        self.assertTrue(
            _alias_match("power bi", "Built sales dashboards in Power BI for store managers.")
        )

    def test_degree_hard_gate_recognizes_indian_degrees(self):
        ledger = EvidenceLedger(
            "candidate-2026",
            (_item("E1", "B.Com (Hons), Christ University, 2022-2025"),),
        )
        requirements = [
            {
                "id": "R1",
                "kind": "degree",
                "text": "Bachelor's degree required",
                "normalized_terms": ["bachelor"],
                "importance": "mandatory",
                "category": "education",
                "source_span": {"start": 0, "end": 26},
            }
        ]
        from ats_agent.requirements import evaluate_hard_gates

        gates = evaluate_hard_gates(requirements, ledger)
        self.assertTrue(all(gate.get("status") != "unmet" for gate in gates))


class VariantDistinctnessTests(unittest.TestCase):
    def test_semicolon_text_yields_distinct_balanced_variant(self):
        provider = DeterministicRewriteProvider()
        context = RewriteContext(
            original_text=(
                "Maintained donation tracking in Google Sheets covering "
                "8,000 kg total; flagged two supply shortfalls early."
            ),
            terms=("data analysis",),
            target_section="projects",
            max_characters=400,
            evidence_ids=("E1",),
            ownership_ceiling="direct",
        )
        variants = provider.generate(context)
        texts = [variant["text"] for variant in variants]
        self.assertGreaterEqual(len(set(texts)), 2)
        self.assertTrue(
            any(". Flagged" in text for text in texts),
            f"expected sentence-split balanced variant, got {texts}",
        )

    def test_compact_with_tail_still_compacts(self):
        provider = DeterministicRewriteProvider()
        variants = provider.generate(
            RewriteContext(
                original_text="Supported analytics; with traceable controls.",
                max_characters=120,
            )
        )
        self.assertTrue(
            any(item["text"].endswith("analytics.") for item in variants)
        )


class RelatedAnchorTests(unittest.TestCase):
    def test_supporting_evidence_anchors_near_related_resume_line(self):
        resume_lines = [
            _item("E1", "Data Analyst Intern, KiranaMart Retail", line_number=5),
            _item(
                "E2",
                "Analytics Volunteer, Bengaluru Food Drive (Jan 2025 - Apr 2025)",
                line_number=8,
            ),
            _item("E3", "Skills: SQL, Power BI, Excel", line_number=13),
        ]
        supporting = _item(
            "E9",
            (
                "Bengaluru Food Drive volunteer analytics, Jan-Apr 2025: tracked "
                "8,000 kg of donations and flagged supply shortfalls two days early."
            ),
            source="supporting",
            line_number=None,
        )
        ledger = EvidenceLedger("candidate-2026", (*resume_lines, supporting))
        anchor = _find_section_anchor(
            "resume body",
            ledger,
            "projects",
            prefer_text=supporting.text,
        )
        self.assertEqual(anchor["line_number"], 8)


class DisavowalTests(unittest.TestCase):
    def test_disavowal_evidence_never_surfaced(self):
        from ats_agent.rewriting import _is_disavowal

        self.assertTrue(_is_disavowal("No A/B testing experience."))
        self.assertTrue(_is_disavowal("No stakeholder presentations to executives."))
        self.assertTrue(_is_disavowal("Explicit non-evidence: never used Tableau."))
        self.assertFalse(
            _is_disavowal("Built weekly sales dashboards in Power BI for managers.")
        )


if __name__ == "__main__":
    unittest.main()
