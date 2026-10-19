#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
run_dir="$(mktemp -d "${TMPDIR:-/tmp}/ats-agent-coverage.XXXXXX")"
trap 'rm -rf "$run_dir"' EXIT
coverage run --source=ats_agent -m unittest discover -s tests -v
coverage run --append --source=ats_agent scripts/check_benchmark.py
coverage run --append --source=ats_agent -m ats_agent.cli --version >/dev/null
coverage run --append --source=ats_agent -m ats_agent.cli doctor >/dev/null
coverage run --append --source=ats_agent -m ats_agent.cli format examples/sample_resume.txt >/dev/null
coverage run --append --source=ats_agent -m ats_agent.cli propose examples/sample_resume.txt examples/sample_job.md --evidence examples/sample_project_bank.md --candidate-id coverage-candidate --output "$run_dir/proposal.json" >/dev/null
coverage run --append --source=ats_agent -m ats_agent.cli review "$run_dir/proposal.json" --markdown "$run_dir/review.md" --html "$run_dir/review.html" --output-document tailored-resume.txt >/dev/null
selection="$(python - "$run_dir/proposal.json" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding='utf-8')); c=next(x for x in p['changes'] if x.get('supported')); print(f"{c['id']}:{c.get('default_variant') or c['variants'][0]['id']}")
PY
)"
coverage run --append --source=ats_agent -m ats_agent.cli approve "$run_dir/proposal.json" --select "$selection" --output "$run_dir/approval.json" --output-document tailored-resume.txt >/dev/null
coverage run --append --source=ats_agent -m ats_agent.cli apply "$run_dir/approval.json" >/dev/null
coverage run --append --source=ats_agent -m ats_agent.cli validate "$run_dir/tailored-resume.txt" >/dev/null
coverage run --append --source=ats_agent -m ats_agent.cli benchmark --suite smoke --report "$run_dir/smoke.json" >/dev/null
coverage_json="$run_dir/coverage.json"
coverage json --fail-under=0 -o "$coverage_json"
echo "coverage-json: $coverage_json"
base="${COVERAGE_GUARD_BASE:-}"
if [ -z "$base" ] && [ "${COVERAGE_GUARD_EVENT_NAME:-}" = "pull_request" ]; then
  base="${COVERAGE_GUARD_PR_BASE:-}"
elif [ -z "$base" ] && [ "${COVERAGE_GUARD_EVENT_NAME:-}" = "push" ]; then
  before="${COVERAGE_GUARD_PUSH_BEFORE:-}"
  if [ -n "$before" ] && ! [[ "$before" =~ ^0+$ ]] && git cat-file -e "$before^{commit}" 2>/dev/null; then
    base="$before"
  else
    base="$(git merge-base origin/main HEAD 2>/dev/null || true)"
  fi
fi
if [ -n "$base" ]; then python scripts/check_changed_coverage.py --base "$base" --coverage-json "$coverage_json"; else echo "coverage-guard: base ref unavailable (non-gating run)"; fi
coverage report --show-missing --fail-under=91
