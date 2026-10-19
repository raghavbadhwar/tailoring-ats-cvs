from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ats_agent.benchmark import BenchmarkGateError
from ats_agent.cli import _error_exit_code, main


class CliErrorContractTests(unittest.TestCase):
    def test_error_categories_have_stable_nonzero_exits(self) -> None:
        self.assertEqual(_error_exit_code(BenchmarkGateError("benchmark")), 7)
        for message, expected in (("stale proposal", 3), ("proposal digest mismatch", 3), ("ownership escalation", 4), ("candidate identity mismatch", 4), ("unsupported output format", 5), ("document anchor absent", 5), ("ordinary bad input", 2)):
            with self.subTest(message=message):
                self.assertEqual(_error_exit_code(ValueError(message)), expected)

    def test_proof_card_command_uses_the_validated_append_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            draft = root / "draft.json"
            ledger = root / "run" / "proof-cards.json"
            draft.write_text(
                json.dumps(
                    {
                        "activity": "Built a workflow test.",
                        "setting": "student project",
                        "origin": {
                            "role": "Intern",
                            "requirement": "testing",
                            "gap": "testing",
                        },
                    }
                ),
                encoding="utf-8",
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(
                    [
                        "proof-card",
                        "--input",
                        str(draft),
                        "--out",
                        str(ledger),
                        "--candidate-id",
                        "candidate-a",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())["status"], "written")
            self.assertTrue(ledger.is_file())

            draft.write_text("[]", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(
                        [
                            "proof-card",
                            "--input",
                            str(draft),
                            "--out",
                            str(ledger),
                            "--candidate-id",
                            "candidate-a",
                        ]
                    ),
                    2,
                )


if __name__ == "__main__":
    unittest.main()
