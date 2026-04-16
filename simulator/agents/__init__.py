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
from typing import TYPE_CHECKING

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
