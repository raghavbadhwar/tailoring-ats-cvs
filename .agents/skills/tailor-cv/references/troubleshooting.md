# Troubleshooting

Bootstrap statuses and their meanings:

- `bootstrap_required` / `upgrade_required` — the engine is missing or too
  old. The JSON includes the full ordered `attempts` chain; read it to the
  user, obtain one explicit yes, then run
  `ensure_cli.py --install --manager auto`. The single consent covers every
  tier, including automatic fall-through from PyPI to the pinned GitHub tag
  to an isolated venv.
- `installed` — a tier succeeded and strict doctor verification passed.
  Subsequent checks resolve the engine through the install-state manifest,
  so no PATH entry is required even for the venv tier.
- `manual_install_required` — every automatic tier failed (or none matches
  `--manager`). Run one of the listed manual commands yourself, then re-run
  `--check`.
- `unhealthy` — the engine exists but failed its strict doctor check. Show
  the `message`; never bypass a failed doctor check.
- `invalid_policy` — the bundled policy file is damaged or from an older
  schema; reinstall the skill/plugin from the current repository.

Useful flags: `--uninstall` clears the state manifest and convenience link;
the environment variable `ATS_AGENT_EXECUTABLE_OVERRIDE` points checks at a
specific binary for development.
