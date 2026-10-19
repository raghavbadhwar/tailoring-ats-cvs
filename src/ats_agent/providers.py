"""Offline-first rewrite provider contracts."""
from __future__ import annotations

from typing import Protocol


class RewriteProvider(Protocol):
    provider_id: str
    provider_version: str


class DeterministicRewriteProvider:
    provider_id = "deterministic"
    provider_version = "v1"


class CommandRewriteProvider:
    """Reserved optional provider; no command executes without explicit configuration."""
    provider_id = "command"
    provider_version = "v1"


class OpenAIRewriteProvider:
    """Optional adapter marker; network calls are intentionally not part of core."""
    provider_id = "openai"
    provider_version = "v1"
