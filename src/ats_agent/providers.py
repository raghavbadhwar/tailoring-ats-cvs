"""Rewrite provider contracts with a deterministic offline implementation."""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class RewriteContext:
    """Minimal, fact-bounded context supplied to a rewrite provider."""

    original_text: str
    terms: tuple[str, ...] = ()
    target_section: str = "projects"
    max_characters: int = 500
    evidence_ids: tuple[str, ...] = ()
    ownership_ceiling: str = "contributor"

    def __post_init__(self) -> None:
        if not self.original_text.strip():
            raise ValueError("original_text is required")
        if self.max_characters < 20:
            raise ValueError("max_characters must be at least 20")


@runtime_checkable
class RewriteProvider(Protocol):
    provider_id: str
    provider_version: str

    def generate(self, context: RewriteContext) -> list[dict]: ...


_GENERIC_PREFIXES = (
    r"^Results[- ]driven\s+",
    r"^Innovative\s+",
    r"^Passionate about\s+",
    r"^Cutting[- ]edge\s+",
)


def _safe_ownership_language(text: str) -> str:
    """Use an equivalent contribution verb without increasing ownership."""

    rules = (
        (r"^Helped\s+build\b", "Contributed to building"),
        (r"^Helped\b", "Contributed to"),
        (r"^Worked\s+on\b", "Contributed to"),
        (r"^Supported\b", "Contributed to"),
        (r"^Contributed\s+to\s+building\b", "Helped build"),
        (r"^Contributed\s+to\b", "Supported"),
        (r"^Assisted\s+with\b", "Supported"),
        (r"^Assisted\b", "Supported"),
        (r"^Participated\s+in\b", "Contributed to"),
        (r"^Collaborated\s+on\b", "Contributed to"),
        (r"^Responsible\s+for\b", "Contributed to"),
    )
    for pattern, replacement in rules:
        updated = re.sub(pattern, replacement, text, count=1, flags=re.IGNORECASE)
        if updated != text:
            return updated
    return text


def _remove_generic(text: str) -> str:
    result = text.strip()
    for pattern in _GENERIC_PREFIXES:
        result = re.sub(pattern, "", result, count=1, flags=re.IGNORECASE)
    result = re.sub(
        r"\b(?:leveraged|utilized)\s+AI\b",
        "used AI",
        result,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", result).strip()


def _surface_term(text: str, term: str) -> str:
    if term.lower() in text.lower():
        return text
    replacements: dict[str, tuple[tuple[str, str], ...]] = {
        "workflow automation": (
            (
                r"(?:building\s+)?automated\s+order\s+workflows",
                "workflow automation for orders",
            ),
            (
                r"(?:building\s+)?automated\s+procurement\s+workflows",
                "workflow automation for procurement",
            ),
            (r"automated\s+workflows", "workflow automation"),
            (r"workflow\s+systems", "workflow automation systems"),
        ),
        "human-in-the-loop": (
            (r"approval-first", "human-in-the-loop"),
            (r"approval[- ]gated", "human-in-the-loop"),
            (r"human approval", "human-in-the-loop approval"),
        ),
        "product requirements": (
            (r"\bPRD\b", "product requirements document (PRD)"),
        ),
        "retrieval-augmented generation": (
            (r"\bRAG\b", "retrieval-augmented generation (RAG)"),
        ),
        "git": ((r"\bGitHub\b", "Git/GitHub"),),
    }
    for pattern, replacement in replacements.get(term, ()):
        updated = re.sub(pattern, replacement, text, count=1, flags=re.IGNORECASE)
        if updated != text:
            return updated
    return text


def _balanced_structure(text: str) -> str:
    """Vary sentence structure without introducing a new factual claim."""

    if " for " in text:
        return text.replace(" for ", " to support ", 1)
    if ", with " in text:
        return text.replace(", with ", "; with ", 1)
    return text


def _compact(text: str) -> str:
    result = re.sub(
        r"\b(?:successfully|various|multiple|really|very)\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    result = re.sub(
        r"workflow automation for orders",
        "order-workflow automation",
        result,
        flags=re.IGNORECASE,
    )
    result = re.sub(
        r"workflow automation for procurement",
        "procurement-workflow automation",
        result,
        flags=re.IGNORECASE,
    )
    result = re.sub(
        r"^Contributed\s+to\s+building\b",
        "Contributed to",
        result,
        count=1,
        flags=re.IGNORECASE,
    )
    if ", with " in result:
        head, _, _ = result.partition(", with ")
        result = head.rstrip(" .") + "."
    elif "; with " in result:
        head, _, _ = result.partition("; with ")
        result = head.rstrip(" .") + "."
    return re.sub(r"\s+", " ", result).strip()


class DeterministicRewriteProvider:
    """Offline provider using controlled, reviewable transformations only."""

    provider_id = "deterministic"
    provider_version = "1.0.0"

    def generate(self, context: RewriteContext) -> list[dict]:
        conservative = _safe_ownership_language(
            _remove_generic(context.original_text)
        )
        balanced = conservative
        for term in dict.fromkeys(context.terms):
            balanced = _surface_term(balanced, term)
        if balanced == conservative:
            balanced = _balanced_structure(balanced)
        compact = _compact(balanced)

        variants: list[dict] = []
        for variant_id, text in (
            ("conservative", conservative),
            ("balanced", balanced),
            ("compact", compact),
        ):
            normalized = re.sub(r"\s+", " ", text).strip()
            if not normalized or len(normalized) > context.max_characters:
                continue
            if any(existing["text"] == normalized for existing in variants):
                continue
            variants.append({"id": variant_id, "text": normalized})
        return variants


class CommandRewriteProvider:
    """Optional local JSON subprocess provider with no shell execution."""

    provider_id = "command"
    provider_version = "1.0.0"

    def __init__(self, command: tuple[str, ...], *, timeout_seconds: float = 20.0):
        if not command:
            raise ValueError("command is required")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.command = command
        self.timeout_seconds = timeout_seconds

    def generate(self, context: RewriteContext) -> list[dict]:
        completed = subprocess.run(
            self.command,
            input=json.dumps(asdict(context)),
            capture_output=True,
            check=True,
            text=True,
            timeout=self.timeout_seconds,
            shell=False,
        )
        payload = json.loads(completed.stdout)
        if not isinstance(payload, list):
            raise ValueError("command provider must return a JSON list")
        variants: list[dict] = []
        for item in payload:
            if not isinstance(item, dict):
                raise ValueError("command provider variants must be objects")
            variant_id = str(item.get("id") or "")
            text = str(item.get("text") or "").strip()
            if variant_id not in {"conservative", "balanced", "compact"}:
                raise ValueError(f"unsupported variant id: {variant_id}")
            if not text or len(text) > context.max_characters:
                raise ValueError("command provider returned invalid variant text")
            variants.append({"id": variant_id, "text": text})
        return variants


def generate_with_fallback(
    provider: RewriteProvider,
    context: RewriteContext,
) -> tuple[list[dict], str, str, str | None]:
    """Use the selected provider and fail safely to deterministic output."""

    try:
        variants = provider.generate(context)
        if not variants:
            raise ValueError("provider returned no rewrite variants")
        return (
            variants,
            provider.provider_id,
            provider.provider_version,
            None,
        )
    except (OSError, ValueError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        fallback = DeterministicRewriteProvider()
        return (
            fallback.generate(context),
            fallback.provider_id,
            fallback.provider_version,
            f"{type(exc).__name__}: {exc}",
        )
