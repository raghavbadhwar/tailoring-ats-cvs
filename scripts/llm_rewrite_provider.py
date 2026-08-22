"""Reference implementation: an LLM rewrite provider behind the existing
command-provider JSON contract.

The engine ships deterministic rewrites and never requires a network call.
When you want model-assisted phrasing, run this script as the provider:

    ats-agent propose resume.docx jd.md \
        --rewrite-command python --rewrite-command scripts/llm_rewrite_provider.py \
        ... (repeat --rewrite-command for extra argv, e.g. ANTHROPIC_API_KEY env)

Contract (identical to CommandRewriteProvider):
    stdin : RewriteContext JSON  {original_text, terms, target_section,
                                  max_characters, evidence_ids, ownership_ceiling}
    stdout: JSON list of {"id": "...", "text": "..."} variants

Safety: every provider output still passes the deterministic validation
gates (ownership ceilings, unsupported-term blocking, evidence binding) —
the model can phrase, it cannot fabricate. Requires the ANTHROPIC_API_KEY
environment variable; failures exit non-zero so the engine falls back to
the deterministic provider.
"""
from __future__ import annotations

import json
import os
import sys

SYSTEM_PROMPT = """You rewrite one resume bullet so it naturally surfaces the
target job terms. Hard rules:
- Use ONLY facts present in the original bullet. Never add employers, dates,
  metrics, tools, or outcomes that are not already there.
- Return JSON: [{"id": "balanced", "text": "..."}, {"id": "compact", "text": "..."}]
- No commentary."""


def main() -> int:
    context = json.loads(sys.stdin.read())
    try:
        import anthropic  # optional dependency: pip install anthropic
    except ImportError:
        print("anthropic package not installed; pip install 'tailoring-ats-cvs[llm]'",
              file=sys.stderr)
        return 3

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY is not set", file=sys.stderr)
        return 3

    client = anthropic.Anthropic(api_key=api_key)
    user_prompt = (
        f"Original bullet:\n{context['original_text']}\n\n"
        f"Target terms to surface if truthfully possible: "
        f"{', '.join(context['terms']) or '(none)'}\n"
        f"Max characters per variant: {context['max_characters']}"
    )
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = "".join(block.text for block in message.content if block.type == "text")
    variants = json.loads(text)
    if not isinstance(variants, list):
        raise ValueError("provider returned non-list")
    json.dump(variants, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
