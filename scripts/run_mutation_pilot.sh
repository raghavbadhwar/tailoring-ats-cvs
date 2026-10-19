#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
artifact_dir="${MUTATION_ARTIFACT_DIR:-$root/build/mutation-pilot}"
temp_base="${TMPDIR:-/tmp}"
temp_base="${temp_base%/}"
temp="$(mktemp -d "$temp_base/ats-agent-mutation.XXXXXX")"
worktree="$temp/repo"
primary_status="$(git -C "$root" status --porcelain=v1)"

cleanup() {
  if [ -e "$worktree/.git" ]; then
    git -C "$root" worktree remove --force "$worktree" >/dev/null 2>&1 || true
  fi
  case "$temp" in
    "$temp_base"/ats-agent-mutation.*) rm -rf -- "$temp" ;;
    *) echo "mutation-pilot: refused unsafe cleanup target: $temp" >&2 ;;
  esac
}
trap cleanup EXIT

mkdir -p "$artifact_dir"
git -C "$root" worktree add --detach "$worktree" HEAD >/dev/null
cd "$worktree"
export PYTHONPATH="$worktree/src"
python - "$worktree" <<'PY'
from pathlib import Path
import ats_agent
import sys

root = Path(sys.argv[1]).resolve()
loaded = Path(ats_agent.__file__).resolve()
loaded.relative_to(root)
print(f"mutation-pilot: package={loaded}")
PY

started="$(date +%s)"
cosmic-ray baseline cosmic-ray.toml > "$artifact_dir/baseline.txt" 2>&1
echo "mutation-pilot: baseline=passed" >> "$artifact_dir/baseline.txt"
cosmic-ray init --force cosmic-ray.toml "$temp/full.sqlite"
python scripts/select_mutation_pilot.py "$temp/full.sqlite" "$temp/pilot.sqlite"
cosmic-ray exec cosmic-ray.toml "$temp/pilot.sqlite"
cosmic-ray dump "$temp/pilot.sqlite" > "$artifact_dir/session.jsonl"
python scripts/summarize_mutation_session.py \
  "$artifact_dir/session.jsonl" "$artifact_dir/summary.json"
elapsed="$(( $(date +%s) - started ))"
printf 'mutation-pilot: elapsed_seconds=%s\n' "$elapsed" | tee "$artifact_dir/runtime.txt"
if [ "$elapsed" -gt 600 ]; then
  echo "mutation-pilot: exceeded 600-second execution budget" >&2
  exit 1
fi
if [ "$(git -C "$root" status --porcelain=v1)" != "$primary_status" ]; then
  echo "mutation-pilot: primary checkout changed" >&2
  exit 1
fi
