"""Game-aware Control pilot."""

from __future__ import annotations

import numpy as np

from agents import Agent
from agents.game_aware.evaluator import best_scored_gp, choose_keep_by_scores
from agents.game_aware.state_features import (
    estimate_opponent_gp_damage,
    estimate_total_threat,
    opponent_has_role,
    view_for,
)
from game_mechanics.game_state import GameState
from game_mechanics.god_powers import load_god_powers


class GameAwareControlAgent(Agent):
    """Control agent that times defense, healing, and Tyr based on visible threat."""

    def __init__(self, rng: np.random.Generator | None = None) -> None:
        self.rng = rng or np.random.default_rng()
        self._god_powers = load_god_powers()

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        """Keep defense under pressure, otherwise keep enough offense/tokens to close."""
        view = view_for(state, player_num)
        threat = estimate_total_threat(view)
        economy_opponent = opponent_has_role(view, "economy")
        scores = {
            "FACE_HELMET": 3.0,
            "FACE_SHIELD": 3.0,
            "FACE_HAND_BORDERED": 2.4,
            "FACE_HAND": 2.0 if economy_opponent else 0.7,
            "FACE_AXE": 1.8 if threat < view.player.hp else 0.8,
            "FACE_ARROW": 1.6 if economy_opponent and threat < view.player.hp else 0.3,
        }
        return choose_keep_by_scores(view, scores, keep_threshold=1.5)

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        """Use Aegis for real GP danger, Eir when healing matters, Tyr for pressure."""
        view = view_for(state, player_num)
        incoming_gp = estimate_opponent_gp_damage(view)

        if opponent_has_role(view, "economy") and incoming_gp > 0:
            choice = best_scored_gp(
                view,
                self._god_powers,
                ("GP_TYRS_JUDGMENT", "GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY"),
                tier_order=(0,),
                minimum_score=0.5,
            )
            if choice is not None:
                return choice

        return best_scored_gp(
            view,
            self._god_powers,
            ("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_TYRS_JUDGMENT"),
            tier_order=(0,),
            minimum_score=0.5,
        )
