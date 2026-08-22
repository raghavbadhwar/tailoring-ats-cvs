"""Performance budget check: 10-role batch proposes well under 90 seconds.

Per the reviewed constraint budget, a batch of ten postings must complete
ingest→propose in under 90 seconds offline. This script is the CI-runnable
assertion of that promise.
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ats_agent.workflow import build_proposal  # noqa: E402

BUDGET_SECONDS = 90.0
ROLES = 10


def main() -> int:
    started = time.monotonic()
    with tempfile.TemporaryDirectory() as tmp:
        resume = Path(tmp) / "resume.txt"
        resume.write_text(
            "PROJECTS\n- Helped build automated workflows with dashboards.\n",
            encoding="utf-8",
        )
        for index in range(ROLES):
            jd = Path(tmp) / f"jd-{index}.md"
            jd.write_text(
                f"# Analyst Intern {index}\n\n"
                "- Strong SQL skills on large datasets\n"
                "- Hands-on Power BI dashboards\n"
                "- Bachelor's degree in a related field\n",
                encoding="utf-8",
            )
            build_proposal(resume, jd, candidate_id="perf-candidate")
    elapsed = time.monotonic() - started
    result = {
        "roles": ROLES,
        "elapsed_seconds": round(elapsed, 3),
        "budget_seconds": BUDGET_SECONDS,
        "status": "passed" if elapsed < BUDGET_SECONDS else "failed",
    }
    print(json.dumps(result))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
