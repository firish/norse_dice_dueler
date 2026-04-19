"""
agents/
-------
Agent base class. All agents implement choose_keep() and choose_god_power().

Agent roster (build order from CLAUDE.md section 14):
    L0  RandomAgent      - uniform random legal actions
    L1  GreedyAgent      - heuristic score function (Aggro / Control / Economy variants)
    L2  ArchetypeAgent   - rule-based strategy (10-15 rules per archetype)
    L3+ MCTSAgent        - Monte Carlo Tree Search (only if results seem suspicious)
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Iterable, Mapping

if TYPE_CHECKING:
    from simulator.game_state import GameState


class Agent:
    """Abstract base class. Subclasses must implement choose_keep()."""

    def choose_keep(self, state: "GameState", player_num: int) -> frozenset[int]:
        """
        Return a frozenset of die indices to lock in this keep phase.

        Only indices where dice_kept[i] is False are valid choices.
        player_num is 1 or 2.
        """
        raise NotImplementedError

    def choose_god_power(
        self, state: "GameState", player_num: int
    ) -> tuple[str, int] | None:
        """
        Return a GP activation choice or None to pass.

        Returns:
            (gp_id, tier_idx) where tier_idx is 0=T1, 1=T2, 2=T3.
            None means the player passes (no GP this round).

        The engine validates the choice (loadout membership, token cost).
        Invalid choices are treated as a pass.
        Base class always passes - subclasses override to activate GPs.
        """
        return None


def choose_keep_by_faces(player, keep_faces: frozenset[str]) -> frozenset[int]:
    """Keep every currently unlocked die whose face matches the keep set."""
    return frozenset(
        i for i, (face, kept) in enumerate(zip(player.dice_faces, player.dice_kept))
        if not kept and face in keep_faces
    )


def with_banked_tokens(player):
    """Return a copy of player with bordered-hand tokens available this round."""
    banked = player.dice_faces.count("FACE_HAND_BORDERED")
    if banked == 0:
        return player
    return replace(player, tokens=player.tokens + banked)


def try_gp(player, god_powers: Mapping[str, object], gp_id: str, tier_order: Iterable[int]) -> tuple[str, int] | None:
    """Return the first affordable tier for a GP, or None if it cannot be cast."""
    if gp_id not in player.gp_loadout:
        return None

    gp = god_powers.get(gp_id)
    if gp is None:
        return None

    for tier_idx in tier_order:
        if player.tokens >= gp.tiers[tier_idx].cost:
            return (gp_id, tier_idx)
    return None


def first_affordable_gp(
    player,
    god_powers: Mapping[str, object],
    gp_priority: Iterable[str],
    tier_order: Iterable[int],
) -> tuple[str, int] | None:
    """Return the first affordable GP from a priority list."""
    for gp_id in gp_priority:
        choice = try_gp(player, god_powers, gp_id, tier_order)
        if choice is not None:
            return choice
    return None
