"""Generate the deterministic 100-case benchmark fixture."""
from __future__ import annotations

import json
from pathlib import Path


def cases() -> list[dict]:
    result: list[dict] = []
    for index in range(20):
        result.append({
            "id": f"supported-resume-{index:02d}",
            "resume": f"PROJECTS\n- Built Python workflow automation validated through {40 + index} tests.",
            "job_description": "Python and workflow automation are required.",
            "expected_supported_terms": ["python", "workflow automation"],
            "expected_unsupported_terms": [],
            "expected_hard_gates": [],
            "forbidden_rewrite_terms": ["led", "production", "customers"],
        })
        result.append({
            "id": f"supported-external-{index:02d}",
            "resume": "PROJECTS\n- Contributed to an AI operations prototype.",
            "supporting_evidence": f"- Built Python automated procurement workflows validated through {100 + index} tests.",
            "job_description": "Python and workflow automation are required.",
            "expected_supported_terms": ["python", "workflow automation"],
            "expected_unsupported_terms": [],
            "expected_hard_gates": [],
            "forbidden_rewrite_terms": ["enterprise customers", "revenue"],
        })
        result.append({
            "id": f"unsupported-skill-{index:02d}",
            "resume": "SKILLS\nExcel, Power BI\nPROJECTS\n- Analysed financial data and built dashboards.",
            "job_description": "Python and SQL are required.",
            "expected_supported_terms": [],
            "expected_unsupported_terms": ["python", "sql"],
            "expected_hard_gates": [],
            "forbidden_rewrite_terms": ["python", "sql"],
        })
        result.append({
            "id": f"graduation-gate-{index:02d}",
            "resume": "EDUCATION\nBachelor of Commerce (Honours), Expected 2027\nSKILLS\nExcel",
            "job_description": "Applicants must graduate in 2027 and hold a bachelor's degree.",
            "expected_supported_terms": [],
            "expected_unsupported_terms": [],
            "expected_hard_gates": [
                {"kind": "graduation_year", "status": "met"},
                {"kind": "degree", "status": "met"},
            ],
            "forbidden_rewrite_terms": ["master"],
        })
        result.append({
            "id": f"experience-gate-{index:02d}",
            "resume": "EXPERIENCE\n- Completed 1 year of internship experience in operations.",
            "job_description": "At least 2 years of experience are required.",
            "expected_supported_terms": [],
            "expected_unsupported_terms": [],
            "expected_hard_gates": [{"kind": "experience_years", "status": "unmet"}],
            "forbidden_rewrite_terms": ["2 years", "led"],
        })
    return result


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    target = root / "benchmarks" / "datasets" / "cases_v2.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(json.dumps(case, sort_keys=True) + "\n" for case in cases()), encoding="utf-8")
    print(f"wrote {len(cases())} cases to {target}")


if __name__ == "__main__":
    main()
