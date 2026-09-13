"""Shared types and token budget (v1)."""

from __future__ import annotations

from dataclasses import dataclass


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars per token for mixed EN/ZH)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


@dataclass
class TokenBudget:
    l0_max: int = 500
    l1_max: int = 2000
    l2_max: int = 5000
    absolute_max: int = 16000
    memory_max_items: int = 5

    def truncate(self, text: str, max_tokens: int) -> tuple[str, int]:
        est = estimate_tokens(text)
        if est <= max_tokens:
            return text, est
        char_budget = max_tokens * 4
        return text[:char_budget] + "\n…[truncated]", max_tokens


DEFAULT_BUDGET = TokenBudget()
