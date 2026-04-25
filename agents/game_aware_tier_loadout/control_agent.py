"""Game+tier+loadout-aware Control pilot."""

from __future__ import annotations

import numpy as np

from agents.game_aware.evaluator import best_scored_gp, choose_keep_by_scores
from agents.game_aware.gp_strategy import choose_control_gp
from agents.game_aware.state_features import (
    estimate_opponent_gp_damage,
    estimate_total_threat,
    loadout_profile,
    opponent_has_role,
    view_for,
)
from agents.game_aware_tier.control_agent import GameAwareTierControlAgent
from game_mechanics.game_state import GameState

_CANONICAL_GPS = frozenset({"GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_TYRS_JUDGMENT"})


class GameAwareTierLoadoutControlAgent(GameAwareTierControlAgent):
    """Control pilot that adapts to whether the package is turtle-heavy or hybrid."""

    def __init__(self, rng: np.random.Generator | None = None, god_powers=None) -> None:
        super().__init__(rng=rng, god_powers=god_powers)

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        """Keep more GP fuel on Skald/Miser shells and more offense on hybrid shells."""
        view = view_for(state, player_num)
        profile = loadout_profile(view.player)
        threat = estimate_total_threat(view, tier_order=(2, 1, 0), god_powers=self._god_powers)
        economy_opponent = opponent_has_role(view, "economy", self._god_powers)
        scores = {
            "FACE_HELMET": 3.0 + (0.5 if profile.light_defense else 0.0),
            "FACE_SHIELD": 3.0 + (0.4 if profile.light_defense else 0.0),
            "FACE_HAND_BORDERED": 2.4 + (0.5 if profile.fuel_rich or profile.skald_count > 0 else 0.0),
            "FACE_HAND": (2.0 if economy_opponent else 0.7) + (0.3 if profile.miser_count > 0 else 0.0),
            "FACE_AXE": (1.8 if threat < view.player.hp else 0.8) + (0.3 if profile.attack_support else 0.0),
            "FACE_ARROW": (1.6 if economy_opponent and threat < view.player.hp else 0.3)
            + (0.3 if profile.expected_arrows >= 0.7 else 0.0),
        }
        return choose_keep_by_scores(view, scores, keep_threshold=1.5)

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        """Push Tyr sooner on hybrid control shells and turtle harder on light-defense ones."""
        view = view_for(state, player_num)
        profile = loadout_profile(view.player)
        if _CANONICAL_GPS.issubset(set(view.player.gp_loadout)):
            incoming_gp = estimate_opponent_gp_damage(view, tier_order=(2, 1, 0), god_powers=self._god_powers)
            threat = estimate_total_threat(view, tier_order=(2, 1, 0), god_powers=self._god_powers)
            if opponent_has_role(view, "economy", self._god_powers):
                order = (
                    ("GP_TYRS_JUDGMENT", "GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY")
                    if profile.attack_support and threat < view.player.hp - 2
                    else ("GP_AEGIS_OF_BALDR", "GP_TYRS_JUDGMENT", "GP_EIRS_MERCY")
                )
                if incoming_gp > 0 or profile.fuel_rich or profile.light_defense:
                    choice = best_scored_gp(
                        view,
                        self._god_powers,
                        order,
                        tier_order=(2, 1, 0),
                        threat_tier_order=(2, 1, 0),
                        minimum_score=0.15,
                    )
                    if choice is not None:
                        return choice

            order = (
                ("GP_TYRS_JUDGMENT", "GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY")
                if profile.attack_support and threat < view.player.hp
                else ("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_TYRS_JUDGMENT")
            )
            if profile.fuel_rich and view.missing_hp >= 4 and threat < view.player.hp:
                order = ("GP_EIRS_MERCY", "GP_AEGIS_OF_BALDR", "GP_TYRS_JUDGMENT")
            return best_scored_gp(
                view,
                self._god_powers,
                order,
                tier_order=(2, 1, 0),
                threat_tier_order=(2, 1, 0),
                minimum_score=0.2,
            )
        return choose_control_gp(view, self._god_powers, tier_order=(2, 1, 0), threat_tier_order=(2, 1, 0))

