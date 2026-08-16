import tomllib
import unittest
from pathlib import Path

import ats_agent

ROOT = Path(__file__).resolve().parents[1]


class BetaReleaseContractTests(unittest.TestCase):
    def test_package_and_project_versions_match_beta(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(project["project"]["version"], "1.0.0b1")
        self.assertEqual(ats_agent.__version__, "1.0.0b1")

    def test_release_workflow_requires_protected_holdout_before_publish(self):
        workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        self.assertIn("environment: release", workflow)
        self.assertIn("PRIVATE_HOLDOUT_B64", workflow)
        self.assertIn("release_check.py --private-holdout", workflow)
        self.assertLess(workflow.index("release_check.py --private-holdout"), workflow.index("gh release create"))

    def test_security_and_cross_platform_workflows_are_present(self):
        security = (ROOT / ".github/workflows/security.yml").read_text(encoding="utf-8")
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("bandit -r src/ats_agent", security)
        self.assertIn("github/codeql-action/analyze@v4", security)
        self.assertIn("windows-latest", ci)
        self.assertIn("--fail-under=90", ci)


if __name__ == "__main__":
    unittest.main()
