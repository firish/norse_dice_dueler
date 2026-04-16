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

    def choose_god_power(self, state: GameState, player_num: int) -> None:
        """Return God Power activation choice. Returns None at L0 (no powers)."""
        return None
