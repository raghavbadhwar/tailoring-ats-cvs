from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.check_changed_coverage as guard


class ChangedCoverageGuardTests(unittest.TestCase):
    def _git(self, root: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def _repo(self, root: Path) -> str:
        self._git(root, "init", "-q")
        self._git(root, "config", "user.email", "coverage@example.invalid")
        self._git(root, "config", "user.name", "Coverage Guard")
        source = root / "src" / "ats_agent" / "sample.py"
        source.parent.mkdir(parents=True)
        source.write_text("VALUE = 1\n", encoding="utf-8")
        self._git(root, "add", "src/ats_agent/sample.py")
        self._git(root, "commit", "-qm", "base")
        return self._git(root, "rev-parse", "HEAD")

    def _run(self, root: Path, *args: str) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(guard, "ROOT", root), contextlib.redirect_stdout(
            stdout
        ), contextlib.redirect_stderr(stderr):
            result = guard.main(list(args))
        return result, stdout.getvalue(), stderr.getvalue()

    def test_executed_changed_statement_passes_and_missing_one_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = self._repo(root)
            source = root / "src" / "ats_agent" / "sample.py"
            source.write_text("VALUE = 1\nOTHER = 2\n", encoding="utf-8")
            self._git(root, "add", "src/ats_agent/sample.py")
            self._git(root, "commit", "-qm", "change")
            report = root / "coverage.json"
            report.write_text(
                json.dumps(
                    {
                        "files": {
                            "src/ats_agent/sample.py": {
                                "executed_lines": [1, 2],
                                "missing_lines": [],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            code, stdout, stderr = self._run(
                root, "--base", base, "--coverage-json", str(report)
            )
            self.assertEqual((code, stderr), (0, ""))
            self.assertIn("1/1 executed statement lines", stdout)

            report.write_text(
                json.dumps(
                    {
                        "files": {
                            "src/ats_agent/sample.py": {
                                "executed_lines": [1],
                                "missing_lines": [2],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            code, _stdout, stderr = self._run(
                root, "--base", base, "--coverage-json", str(report)
            )
            self.assertEqual(code, 1)
            self.assertIn("src/ats_agent/sample.py:2", stderr)

    def test_no_executable_source_change_has_an_explicit_zero_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = self._repo(root)
            source = root / "src" / "ats_agent" / "sample.py"
            source.write_text("VALUE = 1\n# explanation\n", encoding="utf-8")
            self._git(root, "add", "src/ats_agent/sample.py")
            self._git(root, "commit", "-qm", "comment only")
            report = root / "coverage.json"
            report.write_text(
                json.dumps(
                    {
                        "files": {
                            "src/ats_agent/sample.py": {
                                "executed_lines": [1],
                                "missing_lines": [],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            code, stdout, _stderr = self._run(
                root, "--base", base, "--coverage-json", str(report)
            )
            self.assertEqual(code, 0)
            self.assertIn("0/0 executed statement lines", stdout)
            self.assertIn("files: 0", stdout)

    def test_missing_invalid_and_unmatched_reports_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = self._repo(root)
            source = root / "src" / "ats_agent" / "sample.py"
            source.write_text("VALUE = 2\n", encoding="utf-8")
            self._git(root, "add", "src/ats_agent/sample.py")
            self._git(root, "commit", "-qm", "change")
            report = root / "coverage.json"

            code, _stdout, stderr = self._run(
                root, "--base", base, "--coverage-json", str(report)
            )
            self.assertEqual(code, 1)
            self.assertIn("coverage JSON missing", stderr)

            for payload, message in (
                ("not-json", "coverage JSON is invalid"),
                (json.dumps({"files": []}), "coverage JSON is invalid"),
                (json.dumps({"files": {}}), "coverage entry missing or ambiguous"),
            ):
                report.write_text(payload, encoding="utf-8")
                with self.subTest(payload=payload):
                    code, _stdout, stderr = self._run(
                        root, "--base", base, "--coverage-json", str(report)
                    )
                    self.assertEqual(code, 1)
                    self.assertIn(message, stderr)

            code, _stdout, stderr = self._run(
                root,
                "--base",
                "missing-ref",
                "--coverage-json",
                str(report),
                "--report-only",
            )
            self.assertEqual(code, 0)
            self.assertIn("coverage-guard:", stderr)


if __name__ == "__main__":
    unittest.main()
