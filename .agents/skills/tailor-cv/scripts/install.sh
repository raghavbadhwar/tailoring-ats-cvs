#!/usr/bin/env sh
set -eu

PACKAGE_REF='git+https://github.com/raghavbadhwar/tailoring-ats-cvs.git@f666ab5a6a3b074fad6f470f986436814b56a3d3'

if [ "${1:-}" != "--approved" ]; then
  printf '%s\n' "Installation requires explicit approval. Re-run: install.sh --approved" >&2
  exit 2
fi

if command -v uv >/dev/null 2>&1; then
  exec uv tool install "$PACKAGE_REF"
fi
if command -v pipx >/dev/null 2>&1; then
  exec pipx install "$PACKAGE_REF"
fi

printf '%s\n' "No supported installer found. Run: python -m venv .venv && .venv/bin/python -m pip install \"$PACKAGE_REF\"" >&2
exit 1
