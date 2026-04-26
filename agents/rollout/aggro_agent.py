"""Rollout Aggro pilot.

This first rollout generation only searches the GP decision. Keep/reroll logic
is inherited from the current loadout/location-aware heuristic agent.
"""

from __future__ import annotations

import numpy as np

from agents.game_aware_tier_loadout.aggro_agent import GameAwareTierLoadoutAggroAgent
from agents.rollout.common import choose_gp_by_rollout
from game_mechanics.game_state import GameState


class RolloutAggroAgent(GameAwareTierLoadoutAggroAgent):
    """Aggro rollout pilot that evaluates a shortlist of GP choices by playout."""

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
            current_heuristic_cls=GameAwareTierLoadoutAggroAgent,
        )
