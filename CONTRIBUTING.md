# Contributing

Keep changes small and evidence-bound. Add or update a fixture when changing benchmark behavior, and never commit real candidate documents or personal data.

Run before opening a pull request:

```bash
python scripts/validate_skill.py
python -m unittest discover -s tests -v
python -m compileall -q src scripts
```

Changes that alter the approval boundary or evidence rules require a documented fixture and review of `SKILL.md`.
