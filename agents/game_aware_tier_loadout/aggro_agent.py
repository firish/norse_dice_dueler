"""Game+tier+loadout-aware Aggro pilot."""

from __future__ import annotations

import numpy as np

from agents.game_aware.evaluator import best_scored_gp, choose_keep_by_scores
from agents.game_aware.gp_strategy import choose_aggro_gp
from agents.game_aware.state_features import (
    estimate_total_threat,
    loadout_profile,
    opponent_has_role,
    player_with_available_tokens,
    view_for,
)
from agents.game_aware_tier.aggro_agent import GameAwareTierAggroAgent
from game_mechanics.game_state import GameState

_CANONICAL_GPS = frozenset({"GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_TYRS_JUDGMENT"})


class GameAwareTierLoadoutAggroAgent(GameAwareTierAggroAgent):
    """Aggro pilot that adapts pressure lines to the actual six-die package."""

    def __init__(self, rng: np.random.Generator | None = None, god_powers=None) -> None:
        super().__init__(rng=rng, god_powers=god_powers)

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        """Keep more GP fuel on token-heavy packages and more defense on light ones."""
        view = view_for(state, player_num)
        profile = loadout_profile(view.player)
        threat = estimate_total_threat(view, tier_order=(2, 1, 0), god_powers=self._god_powers)
        economy_opponent = opponent_has_role(view, "economy", self._god_powers)
        control_opponent = opponent_has_role(view, "control", self._god_powers)
        defense_score = 1.5 if threat >= view.player.hp else -0.5
        scores = {
            "FACE_AXE": 3.2 + (0.2 if profile.expected_axes >= 1.3 else 0.0),
            "FACE_ARROW": 2.7 + (0.2 if profile.expected_arrows >= 0.9 else 0.0),
            "FACE_HAND_BORDERED": 2.2 + (0.4 if profile.fuel_rich or profile.gambler_count > 0 else 0.0),
            "FACE_HAND": (1.0 if economy_opponent else -0.2) + (0.4 if profile.fuel_rich else 0.0),
            "FACE_HELMET": defense_score + (0.4 if profile.light_defense or profile.warden_count > 0 else 0.0),
            "FACE_SHIELD": defense_score + (0.4 if profile.light_defense else 0.0),
        }
        kept = set(choose_keep_by_scores(view, scores))
        if control_opponent and threat < view.player.hp and (profile.fuel_rich or profile.miser_count > 0):
            for idx, (face, already_kept) in enumerate(zip(view.player.dice_faces, view.player.dice_kept)):
                if already_kept or idx in kept:
                    continue
                if face == "FACE_HAND":
                    kept.add(idx)
                    break
        return frozenset(kept)

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        """Shift burst ordering based on whether the loadout is fuel-rich or race-heavy."""
        view = view_for(state, player_num)
        profile = loadout_profile(view.player)
        if _CANONICAL_GPS.issubset(set(view.player.gp_loadout)):
            player = player_with_available_tokens(view)
            for tier_idx in (2, 1, 0):
                choice = ("GP_FENRIRS_BITE", tier_idx)
                tier = self._god_powers["GP_FENRIRS_BITE"].tiers[tier_idx]
                if player.tokens >= tier.cost and tier.damage >= view.opponent.hp:
                    return choice
            for tier_idx in (2, 1, 0):
                choice = ("GP_SURTRS_FLAME", tier_idx)
                tier = self._god_powers["GP_SURTRS_FLAME"].tiers[tier_idx]
                if player.tokens >= tier.cost and tier.damage >= view.opponent.hp:
                    return choice

            if opponent_has_role(view, "control", self._god_powers):
                order = (
                    ("GP_FENRIRS_BITE", "GP_TYRS_JUDGMENT", "GP_SURTRS_FLAME")
                    if profile.fuel_rich or profile.gambler_count > 0 or profile.miser_count > 0
                    else ("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_TYRS_JUDGMENT")
                )
                return best_scored_gp(
                    view,
                    self._god_powers,
                    order,
                    tier_order=(2, 1, 0),
                    threat_tier_order=(2, 1, 0),
                    minimum_score=0.1,
                )

            if opponent_has_role(view, "economy", self._god_powers):
                order = (
                    ("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_TYRS_JUDGMENT")
                    if profile.expected_attack >= 2.1 and not profile.fuel_rich
                    else ("GP_FENRIRS_BITE", "GP_SURTRS_FLAME", "GP_TYRS_JUDGMENT")
                )
                return best_scored_gp(
                    view,
                    self._god_powers,
                    order,
                    tier_order=(2, 1, 0),
                    threat_tier_order=(2, 1, 0),
                    minimum_score=0.2,
                )

            order = (
                ("GP_FENRIRS_BITE", "GP_SURTRS_FLAME", "GP_TYRS_JUDGMENT")
                if profile.fuel_rich and profile.expected_attack < 2.2
                else ("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_TYRS_JUDGMENT")
            )
            return best_scored_gp(
                view,
                self._god_powers,
                order,
                tier_order=(2, 1, 0),
                threat_tier_order=(2, 1, 0),
                minimum_score=0.2,
            )
        return choose_aggro_gp(view, self._god_powers, tier_order=(2, 1, 0), threat_tier_order=(2, 1, 0))

