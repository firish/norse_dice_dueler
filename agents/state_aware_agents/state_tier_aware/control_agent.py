"""Game+tier-aware Control pilot."""

from __future__ import annotations

import numpy as np

from agents.state_aware_agents.god_powers.gp_scoring import MEANINGFUL_GP_THREAT_SCORE
from agents.state_aware_agents.god_powers.gp_strategy import choose_control_gp
from agents.state_aware_agents.locations.location_rules import gp_activation_blocked
from agents.state_aware_agents.state.state_evaluator import best_scored_gp, choose_keep_by_scores
from agents.state_aware_agents.state.state_features import (
    estimate_opponent_gp_damage,
    estimate_opponent_gp_value,
    estimate_total_threat,
    opponent_has_role,
    view_for,
)
from agents.state_aware_agents.state_aware.control_agent import GameAwareControlAgent
from game_mechanics.game_state import GameState

_CANONICAL_GPS = frozenset({"GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_TYRS_JUDGMENT"})


class GameAwareTierControlAgent(GameAwareControlAgent):
    """Control pilot that keeps game-aware reads while escalating Aegis/Eir/Tyr tiers."""

    def __init__(self, rng: np.random.Generator | None = None, god_powers=None) -> None:
        super().__init__(rng=rng, god_powers=god_powers)

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        """Preserve game-aware keep logic but account for higher-tier threat."""
        view = view_for(state, player_num)
        threat = estimate_total_threat(view, tier_order=(2, 1, 0), god_powers=self._god_powers)
        economy_opponent = opponent_has_role(view, "economy", self._god_powers)
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
        """Choose among equipped GPs, preserving the tuned canonical trio behavior."""
        view = view_for(state, player_num)
        if gp_activation_blocked(view.state.round_num, view.state.condition_ids):
            return None
        if _CANONICAL_GPS.issubset(set(view.player.gp_loadout)):
            incoming_gp = estimate_opponent_gp_damage(view, tier_order=(2, 1, 0), god_powers=self._god_powers)
            incoming_gp_value = estimate_opponent_gp_value(view, tier_order=(2, 1, 0), god_powers=self._god_powers)
            threat = estimate_total_threat(view, tier_order=(2, 1, 0), god_powers=self._god_powers)
            if opponent_has_role(view, "economy", self._god_powers):
                if threat < max(5, view.player.hp):
                    choice = best_scored_gp(
                        view,
                        self._god_powers,
                        ("GP_TYRS_JUDGMENT", "GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY"),
                        tier_order=(2, 1, 0),
                        threat_tier_order=(2, 1, 0),
                        minimum_score=0.05,
                    )
                    if choice is not None:
                        return choice
            if opponent_has_role(view, "economy", self._god_powers) and (
                incoming_gp > 0 or incoming_gp_value >= MEANINGFUL_GP_THREAT_SCORE
            ):
                choice = best_scored_gp(
                    view,
                    self._god_powers,
                    ("GP_TYRS_JUDGMENT", "GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY"),
                    tier_order=(2, 1, 0),
                    threat_tier_order=(2, 1, 0),
                    minimum_score=0.2,
                )
                if choice is not None:
                    return choice
            return best_scored_gp(
                view,
                self._god_powers,
                ("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_TYRS_JUDGMENT"),
                tier_order=(2, 1, 0),
                threat_tier_order=(2, 1, 0),
                minimum_score=0.2,
            )
        return choose_control_gp(view, self._god_powers, tier_order=(2, 1, 0), threat_tier_order=(2, 1, 0))
