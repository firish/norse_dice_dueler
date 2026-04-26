"""Game+tier+loadout-aware Economy pilot."""

from __future__ import annotations

import numpy as np

from agents.game_aware.evaluator import best_scored_gp, choose_keep_by_scores, choice_cost
from agents.game_aware.location_rules import gp_activation_blocked
from agents.game_aware.gp_strategy import choose_economy_gp
from agents.game_aware.state_features import (
    estimate_total_threat,
    loadout_profile,
    opponent_has_role,
    view_for,
)
from agents.game_aware_tier.economy_agent import GameAwareTierEconomyAgent
from game_mechanics.game_state import GameState

_CANONICAL_GPS = frozenset({"GP_MJOLNIRS_WRATH", "GP_GULLVEIGS_HOARD", "GP_BRAGIS_SONG"})


class GameAwareTierLoadoutEconomyAgent(GameAwareTierEconomyAgent):
    """Economy pilot that cashes out earlier on pressure shells and ramps harder on engine shells."""

    def __init__(self, rng: np.random.Generator | None = None, god_powers=None) -> None:
        super().__init__(rng=rng, god_powers=god_powers)

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        """Keep attack faces more on Hunter/Berserker shells, pure fuel on Miser shells."""
        view = view_for(state, player_num)
        profile = loadout_profile(view.player)
        threat = estimate_total_threat(view, tier_order=(2, 1, 0), god_powers=self._god_powers)
        aggro_opponent = opponent_has_role(view, "aggro", self._god_powers)
        control_opponent = opponent_has_role(view, "control", self._god_powers)
        scores = {
            "FACE_HAND_BORDERED": 3.2 + (0.4 if profile.fuel_rich else 0.0),
            "FACE_HAND": 2.4 + (0.2 if profile.miser_count >= 2 else -0.2 if profile.attack_support else 0.0),
            "FACE_AXE": 1.7 + (0.2 if (profile.attack_support or profile.berserker_count > 0) and not aggro_opponent else 0.0),
            "FACE_ARROW": (2.0 if control_opponent else 1.4) + (0.4 if profile.hunter_count > 0 and control_opponent else 0.0),
            "FACE_HELMET": 2.4 if aggro_opponent or threat >= view.player.hp - 3 else 1.0,
            "FACE_SHIELD": 2.4 if aggro_opponent or threat >= view.player.hp - 3 else 1.0,
        }
        if profile.light_defense:
            scores["FACE_HELMET"] += 0.4
            scores["FACE_SHIELD"] += 0.4
        return choose_keep_by_scores(view, scores, keep_threshold=1.5)

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        """Raise the cash-out priority on pressure builds and ramp priority on token engines."""
        view = view_for(state, player_num)
        profile = loadout_profile(view.player)
        if gp_activation_blocked(view.state.round_num, view.state.condition_ids):
            return None
        if _CANONICAL_GPS.issubset(set(view.player.gp_loadout)):
            threat = estimate_total_threat(view, tier_order=(2, 1, 0), god_powers=self._god_powers)
            control_opponent = opponent_has_role(view, "control", self._god_powers)
            aggro_opponent = opponent_has_role(view, "aggro", self._god_powers)

            for tier_idx in (2, 1, 0):
                tier = self._god_powers["GP_MJOLNIRS_WRATH"].tiers[tier_idx]
                if choice_cost(view, self._god_powers, "GP_MJOLNIRS_WRATH", tier_idx) <= view.available_tokens and tier.damage >= view.opponent.hp:
                    return ("GP_MJOLNIRS_WRATH", tier_idx)

            if aggro_opponent and (view.combat.incoming_total >= 2 or threat >= view.player.hp):
                bragi_choice = best_scored_gp(
                    view,
                    self._god_powers,
                    ("GP_BRAGIS_SONG",),
                    tier_order=(2, 1, 0),
                    threat_tier_order=(2, 1, 0),
                    minimum_score=0.1,
                )
                if bragi_choice is not None:
                    return bragi_choice

            if (profile.attack_support or profile.hunter_count > 0) and not aggro_opponent:
                mjolnir_choice = best_scored_gp(
                    view,
                    self._god_powers,
                    ("GP_MJOLNIRS_WRATH",),
                    tier_order=(2, 1, 0),
                    threat_tier_order=(2, 1, 0),
                    minimum_score=0.15,
                )
                if mjolnir_choice is not None and threat < view.player.hp:
                    return mjolnir_choice

            ramp_threshold = 12
            if aggro_opponent:
                ramp_threshold = 11 if profile.hunter_count > 0 else 12
            elif profile.attack_support or profile.hunter_count > 0:
                ramp_threshold = 9 if control_opponent else 10
            elif profile.fuel_rich and profile.miser_count >= 2:
                ramp_threshold = 10 if control_opponent else 13

            if view.available_tokens < ramp_threshold:
                gullveig_choice = best_scored_gp(
                    view,
                    self._god_powers,
                    ("GP_GULLVEIGS_HOARD",),
                    tier_order=((1, 0) if control_opponent else (2, 1, 0)),
                    threat_tier_order=(2, 1, 0),
                    minimum_score=0.2,
                )
                if gullveig_choice is not None:
                    return gullveig_choice

            return best_scored_gp(
                view,
                self._god_powers,
                ("GP_MJOLNIRS_WRATH", "GP_BRAGIS_SONG"),
                tier_order=(2, 1, 0),
                threat_tier_order=(2, 1, 0),
                minimum_score=0.2 if not aggro_opponent else 0.1,
            )
        return choose_economy_gp(view, self._god_powers, tier_order=(2, 1, 0), threat_tier_order=(2, 1, 0))
