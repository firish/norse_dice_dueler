"""Rollout Economy pilot."""

from __future__ import annotations

import numpy as np

from agents.game_aware_tier_loadout.economy_agent import GameAwareTierLoadoutEconomyAgent
from agents.rollout.common import choose_gp_by_rollout
from game_mechanics.game_state import GameState


class RolloutEconomyAgent(GameAwareTierLoadoutEconomyAgent):
    """Economy rollout pilot that searches GP choices and keeps heuristic keep logic."""

    def __init__(self, rng: np.random.Generator | None = None, god_powers=None) -> None:
        super().__init__(rng=rng, god_powers=god_powers)

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        """Search over the current GP choice, then fall back to heuristic play."""
        heuristic_choice = super().choose_god_power(state, player_num)
        return choose_gp_by_rollout(
            state,
            player_num,
            rng=self.rng,
            god_powers=self._god_powers,
            heuristic_choice=heuristic_choice,
            current_heuristic_cls=GameAwareTierLoadoutEconomyAgent,
        )
