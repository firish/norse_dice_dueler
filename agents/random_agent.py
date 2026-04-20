"""
random_agent.py
---------------
RandomAgent - the L0 baseline agent.

Makes every decision by sampling uniformly at random:
  - Keep phase: each unkept die kept independently with 50% probability.
  - God Power: none (L0).

Used to establish the L0 symmetry baseline: two RandomAgents playing mirror
loadouts should produce P1 win rate 48-52% (Constitution first-mover check).
"""

from __future__ import annotations

import numpy as np

from agents import Agent
from game_mechanics.game_state import GameState


class RandomAgent(Agent):
    """Agent that makes every decision uniformly at random.

    Used as the L0 baseline. Two RandomAgents on mirror loadouts should
    produce a P1 win rate of 48-52% - the first-mover symmetry check.

    Args:
        rng: optional NumPy random generator. Pass a seeded generator for
             reproducible results (e.g. np.random.default_rng(42)).
    """
    def __init__(self, rng: np.random.Generator | None = None) -> None:
        self.rng = rng or np.random.default_rng()

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        """Independently keep each currently unlocked die with 50% probability."""
        player = state.p1 if player_num == 1 else state.p2
        # Only offer the indices that are not yet locked in.
        available = [i for i, kept in enumerate(player.dice_kept) if not kept]
        # Each available die kept with 50% probability independently.
        kept = frozenset(i for i in available if self.rng.random() < 0.5)
        return kept
