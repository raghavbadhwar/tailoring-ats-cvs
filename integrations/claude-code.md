# Claude Code

## Native install (recommended)

```text
/plugin marketplace add raghavbadhwar/tailoring-ats-cvs
/plugin install tailoring-ats-cvs@raghavbadhwar
```

Then run `/tailoring-ats-cvs:tailor-cv <cv> <jd> [evidence...]`. The bundled
slash command drives the entire approval-first flow, including the single
consent prompt that installs and verifies the `ats-agent` engine on first
use.

## Development install

From a checkout run `claude --plugin-dir .`, then use `/tailoring-ats-cvs:tailor-cv`.

## Notes

- For public job research, use the existing AI Job Search workspace first; pass its read-only unfiltered export to `ats-agent research-jobs`. Do not copy discovery, ranking, portal, or tracker logic into the plugin.
- A role-relevant unsupported gap is handled conversationally: ask neutrally whether the candidate genuinely did it; a bare yes never becomes CV text. After confirmation with setting/timeframe, write a candidate-owned supplemental evidence artifact and rebuild the draft with `--evidence`. The fresh draft still needs explicit approval before apply.
- Release bundles remain available as release assets: unzip and `claude --plugin-dir ./tailoring-ats-cvs`. Structural loading is tested in CI; interactive `/plugin install` remains a manual host check when Claude Code is available.
