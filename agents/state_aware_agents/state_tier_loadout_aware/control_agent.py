"""Game+tier+loadout-aware Control pilot."""

from __future__ import annotations

import numpy as np

from agents.state_aware_agents.state.state_evaluator import best_scored_gp, choose_keep_by_scores
from agents.state_aware_agents.god_powers.gp_scoring import (
    EXTREME_GP_THREAT_SCORE,
    HIGH_GP_THREAT_SCORE,
    MEANINGFUL_GP_THREAT_SCORE,
)
from agents.state_aware_agents.god_powers.gp_loadout import minimum_tier_cost
from agents.state_aware_agents.locations.location_rules import gp_activation_blocked
from agents.state_aware_agents.god_powers.gp_strategy import choose_control_gp
from agents.state_aware_agents.state.state_features import (
    banked_tokens_for_player,
    estimate_opponent_gp_damage,
    estimate_opponent_gp_value,
    estimate_total_threat,
    loadout_profile,
    opponent_has_role,
    view_for,
)
from agents.state_aware_agents.state_tier_aware.control_agent import GameAwareTierControlAgent
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
        equipped = set(view.player.gp_loadout)
        scores = {
            "FACE_HELMET": 3.0 + (0.5 if profile.light_defense else 0.0),
            "FACE_SHIELD": 3.0 + (0.4 if profile.light_defense else 0.0),
            "FACE_HAND_BORDERED": 2.4 + (0.5 if profile.fuel_rich or profile.skald_count > 0 else 0.0),
            "FACE_HAND": (2.0 if economy_opponent else 0.7) + (0.3 if profile.miser_count > 0 else 0.0),
            "FACE_AXE": (1.8 if threat < view.player.hp else 0.8) + (0.3 if profile.attack_support else 0.0),
            "FACE_ARROW": (1.6 if economy_opponent and threat < view.player.hp else 0.3)
            + (0.3 if profile.expected_arrows >= 0.7 else 0.0),
        }
        if economy_opponent and profile.berserker_count > 0:
            scores["FACE_AXE"] += 0.5
            scores["FACE_ARROW"] += 0.4
            scores["FACE_HAND_BORDERED"] += 0.2
            scores["FACE_HAND"] += 0.2
        if economy_opponent and "GP_FRIGGS_VEIL" in equipped:
            scores["FACE_HAND_BORDERED"] += 0.4
            scores["FACE_HAND"] += 0.4
        if economy_opponent and "GP_BRAGIS_SONG" in equipped and "GP_AEGIS_OF_BALDR" not in equipped:
            scores["FACE_HELMET"] -= 0.3
            scores["FACE_SHIELD"] -= 0.3
            scores["FACE_AXE"] += 0.2
        return choose_keep_by_scores(view, scores, keep_threshold=1.5)

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        """Push Tyr sooner on hybrid control shells and turtle harder on light-defense ones."""
        view = view_for(state, player_num)
        profile = loadout_profile(view.player)
        equipped = set(view.player.gp_loadout)
        if gp_activation_blocked(view.state.round_num, view.state.condition_ids):
            return None
        if _CANONICAL_GPS.issubset(set(view.player.gp_loadout)):
            incoming_gp = estimate_opponent_gp_damage(view, tier_order=(2, 1, 0), god_powers=self._god_powers)
            incoming_gp_value = estimate_opponent_gp_value(view, tier_order=(2, 1, 0), god_powers=self._god_powers)
            threat = estimate_total_threat(view, tier_order=(2, 1, 0), god_powers=self._god_powers)
            if opponent_has_role(view, "economy", self._god_powers):
                if incoming_gp_value >= HIGH_GP_THREAT_SCORE and "GP_FRIGGS_VEIL" in view.player.gp_loadout:
                    choice = best_scored_gp(
                        view,
                        self._god_powers,
                        ("GP_FRIGGS_VEIL", "GP_TYRS_JUDGMENT", "GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY"),
                        tier_order=(2, 1, 0),
                        threat_tier_order=(2, 1, 0),
                        minimum_score=-0.1,
                    )
                    if choice is not None:
                        return choice
                order = (
                    ("GP_TYRS_JUDGMENT", "GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY")
                    if profile.attack_support and threat < view.player.hp - 2
                    else ("GP_AEGIS_OF_BALDR", "GP_TYRS_JUDGMENT", "GP_EIRS_MERCY")
                )
                if (
                    incoming_gp > 0
                    or incoming_gp_value >= MEANINGFUL_GP_THREAT_SCORE
                    or profile.fuel_rich
                    or profile.light_defense
                ):
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
        if opponent_has_role(view, "economy", self._god_powers):
            incoming_gp = estimate_opponent_gp_damage(view, tier_order=(2, 1, 0), god_powers=self._god_powers)
            incoming_gp_value = estimate_opponent_gp_value(view, tier_order=(2, 1, 0), god_powers=self._god_powers)
            threat = estimate_total_threat(view, tier_order=(2, 1, 0), god_powers=self._god_powers)
            opp_available = view.opponent.tokens + banked_tokens_for_player(view.state, view.opponent)
            safe_to_bank = threat <= max(3, view.player.hp - 3)

            if "GP_FRIGGS_VEIL" in equipped:
                frigg_cost = minimum_tier_cost(("GP_FRIGGS_VEIL",), self._god_powers)
                if opp_available >= 8 or incoming_gp_value >= EXTREME_GP_THREAT_SCORE:
                    choice = best_scored_gp(
                        view,
                        self._god_powers,
                        ("GP_FRIGGS_VEIL", "GP_TYRS_JUDGMENT", "GP_BRAGIS_SONG", "GP_EIRS_MERCY", "GP_AEGIS_OF_BALDR"),
                        tier_order=(2, 1, 0),
                        threat_tier_order=(2, 1, 0),
                        minimum_score=-0.1,
                    )
                    if choice is not None:
                        return choice
                if safe_to_bank and view.available_tokens < frigg_cost:
                    return None

            if "GP_TYRS_JUDGMENT" in equipped and (profile.berserker_count > 0 or profile.attack_support):
                choice = best_scored_gp(
                    view,
                    self._god_powers,
                    ("GP_TYRS_JUDGMENT", "GP_AEGIS_OF_BALDR", "GP_BRAGIS_SONG", "GP_EIRS_MERCY"),
                    tier_order=(2, 1, 0),
                    threat_tier_order=(2, 1, 0),
                    minimum_score=(0.0 if safe_to_bank else 0.2),
                )
                if choice is not None:
                    return choice

            if "GP_BRAGIS_SONG" in equipped and view.combat.incoming_total >= 2:
                choice = best_scored_gp(
                    view,
                    self._god_powers,
                    ("GP_BRAGIS_SONG", "GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_TYRS_JUDGMENT"),
                    tier_order=(2, 1, 0),
                    threat_tier_order=(2, 1, 0),
                    minimum_score=0.05,
                )
                if choice is not None:
                    return choice

            if "GP_EIRS_MERCY" in equipped and safe_to_bank and view.missing_hp <= 2:
                return None
        return choose_control_gp(view, self._god_powers, tier_order=(2, 1, 0), threat_tier_order=(2, 1, 0))
