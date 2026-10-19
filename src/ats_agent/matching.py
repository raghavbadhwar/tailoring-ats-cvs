"""Small indexed retrieval layer for requirement-to-claim matching."""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable

from .models import AtomicClaim


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


class EvidenceIndex:
    def __init__(self, claims: Iterable[AtomicClaim]) -> None:
        self.claims = tuple(claims)
        self.by_token: dict[str, set[str]] = defaultdict(set)
        self.by_id = {claim.claim_id: claim for claim in self.claims}
        for claim in self.claims:
            for token in _tokens(claim.source_text):
                self.by_token[token].add(claim.claim_id)

    def retrieve(self, requirement_text: str, limit: int = 10) -> tuple[AtomicClaim, ...]:
        ids = set().union(*(self.by_token.get(token, set()) for token in _tokens(requirement_text)))
        return tuple(self.by_id[item] for item in sorted(ids)[:limit])
