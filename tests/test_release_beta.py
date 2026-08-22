import re
import unittest
from pathlib import Path

import ats_agent

ROOT = Path(__file__).resolve().parents[1]


class BetaReleaseContractTests(unittest.TestCase):
    def test_package_and_project_versions_match_beta(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, flags=re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "1.0.0b3")
        self.assertEqual(ats_agent.__version__, "1.0.0b3")

    def test_release_workflow_gates_before_publish(self):
        workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        self.assertIn('test "${GITHUB_REF_NAME}" = "v1.0.0-beta.3"', workflow)
        self.assertIn('assert version == "1.0.0b3", version', workflow)
        self.assertIn("environment: release", workflow)
        self.assertIn("PRIVATE_HOLDOUT_B64", workflow)
        self.assertIn("release_check.py --private-holdout", workflow)
        self.assertLess(workflow.index("release_check.py --private-holdout"), workflow.index("gh release create"))
        self.assertLess(workflow.index("release_check.py > release-check.json"), workflow.index("gh release create"))

    def test_beta_holdout_gate_is_conditional_with_disclosure(self):
        checker = (ROOT / "scripts/release_check.py").read_text(encoding="utf-8")
        self.assertIn("--require-holdout", checker)
        self.assertIn('"executed": False', checker)
        self.assertIn("NOT executed", checker)
        workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        self.assertIn("steps.holdout.outputs.available == 'true'", workflow)
        self.assertIn("PROTECTED HOLDOUT NOT EXECUTED", workflow)
        self.assertIn("--require-holdout", workflow)

    def test_require_holdout_fails_closed_without_dataset(self):
        import subprocess
        import sys

        completed = subprocess.run(
            [sys.executable, "scripts/release_check.py", "--require-holdout"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("require-holdout", (completed.stderr + completed.stdout).lower())
        self.assertNotIn('"status": "passed"', completed.stdout)

    def test_security_and_cross_platform_workflows_are_present(self):
        security = (ROOT / ".github/workflows/security.yml").read_text(encoding="utf-8")
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("bandit -r src/ats_agent", security)
        self.assertIn("github/codeql-action/analyze@v4", security)
        self.assertIn("windows-latest", ci)
        self.assertIn("--fail-under=90", ci)


if __name__ == "__main__":
    unittest.main()
