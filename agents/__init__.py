"""Shared agent protocol and helper utilities.

The concrete agent implementations live in sibling modules:

- `random_agent.py` for the L0 baseline
- `greedy_agent.py` for the simple L1 GP baseline
- `aggro_agent.py`, `control_agent.py`, and `economy_agent.py` for
  matchup-aware archetype pilots used by the balance harnesses
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any, Iterable, Mapping

if TYPE_CHECKING:
    from game_mechanics.game_state import GameState


class Agent:
    """Abstract decision policy used by the simulator.

    Agents are intentionally lightweight. They only make decisions in the two
    keep phases and in the God Power phase. Every other phase is resolved by
    the engine.
    """

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
    """Keep every unlocked die whose current face is in ``keep_faces``."""
    return frozenset(
        i for i, (face, kept) in enumerate(zip(player.dice_faces, player.dice_kept))
        if not kept and face in keep_faces
    )


def with_banked_tokens(player):
    """Return a player copy with bordered-hand income added to current tokens.

    Several harness agents make GP decisions as if bordered hands are already
    banked, because that matches the current engine timing.
    """
    banked = player.dice_faces.count("FACE_HAND_BORDERED")
    if banked == 0:
        return player
    return replace(player, tokens=player.tokens + banked)


def try_gp(
    player,
    god_powers: Mapping[str, Any],
    gp_id: str,
    tier_order: Iterable[int],
) -> tuple[str, int] | None:
    """Return the first affordable tier for ``gp_id`` using ``tier_order``."""
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
    god_powers: Mapping[str, Any],
    gp_priority: Iterable[str],
    tier_order: Iterable[int],
) -> tuple[str, int] | None:
    """Return the first affordable GP from a priority list."""
    for gp_id in gp_priority:
        choice = try_gp(player, god_powers, gp_id, tier_order)
        if choice is not None:
            return choice
    return None


__all__ = [
    "Agent",
    "choose_keep_by_faces",
    "first_affordable_gp",
    "try_gp",
    "with_banked_tokens",
]
