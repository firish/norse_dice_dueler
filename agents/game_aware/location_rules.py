"""Shared L4 rule helpers for smart agents.

These helpers mirror condition-driven engine rules that directly affect GP
legality or affordability, so agents can reason about the same constraints the
engine will enforce.
"""

from __future__ import annotations

from collections.abc import Iterable

from game_mechanics.conditions import condition_param


def gp_activation_blocked(round_num: int, condition_ids: Iterable[str]) -> bool:
    """Return whether battlefield conditions currently prevent GP activation."""
    active = tuple(condition_ids)
    blocked_rounds = int(condition_param("COND_TYR_ARENA", "blocked_rounds", 1))
    return "COND_TYR_ARENA" in active and round_num <= blocked_rounds


def effective_gp_cost(base_cost: int, round_num: int, condition_ids: Iterable[str]) -> int:
    """Return the effective GP cost after condition-based modifiers."""
    active = tuple(condition_ids)
    if "COND_JOTUN_MIGHT" in active:
        min_base_cost = int(condition_param("COND_JOTUN_MIGHT", "min_base_cost", 8))
        cost_discount = int(condition_param("COND_JOTUN_MIGHT", "cost_discount", 1))
        if base_cost >= min_base_cost:
            return max(1, base_cost - cost_discount)
    return base_cost
