"""Game+tier-aware Economy pilot."""

from __future__ import annotations

import numpy as np

from agents import Agent, try_gp
from agents.game_aware.economy_agent import GameAwareEconomyAgent
from agents.game_aware.evaluator import best_scored_gp, choose_keep_by_scores
from agents.game_aware.state_features import (
    estimate_total_threat,
    opponent_has_role,
    player_with_available_tokens,
    view_for,
)
from game_mechanics.game_state import GameState


class GameAwareTierEconomyAgent(GameAwareEconomyAgent):
    """Economy pilot that chooses between ramp, defense, and higher-tier cash-outs."""

    def __init__(self, rng: np.random.Generator | None = None, god_powers=None) -> None:
        super().__init__(rng=rng, god_powers=god_powers)

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        """Preserve game-aware keep logic but account for higher-tier burst threats."""
        view = view_for(state, player_num)
        threat = estimate_total_threat(view, tier_order=(2, 1, 0), god_powers=self._god_powers)
        aggro_opponent = opponent_has_role(view, "aggro")
        control_opponent = opponent_has_role(view, "control")
        scores = {
            "FACE_HAND_BORDERED": 3.2,
            "FACE_HAND": 2.4,
            "FACE_AXE": 1.7,
            "FACE_ARROW": 2.0 if control_opponent else 1.4,
            "FACE_HELMET": 2.4 if aggro_opponent or threat >= view.player.hp - 3 else 1.0,
            "FACE_SHIELD": 2.4 if aggro_opponent or threat >= view.player.hp - 3 else 1.0,
        }
        return choose_keep_by_scores(view, scores, keep_threshold=1.5)

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        """Prefer lethal Mjolnir tiers, Bragi under race pressure, then efficient ramp."""
        view = view_for(state, player_num)
        player = player_with_available_tokens(view)
        threat = estimate_total_threat(view, tier_order=(2, 1, 0), god_powers=self._god_powers)
        control_opponent = opponent_has_role(view, "control")

        mjolnir = self._god_powers["GP_MJOLNIRS_WRATH"]
        for tier_idx in (2, 1, 0):
            tier = mjolnir.tiers[tier_idx]
            if player.tokens >= tier.cost and tier.damage >= view.opponent.hp:
                return ("GP_MJOLNIRS_WRATH", tier_idx)

        if opponent_has_role(view, "aggro") and (view.combat.incoming_total >= 2 or threat >= view.player.hp):
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

            mjolnir_under_pressure = best_scored_gp(
                view,
                self._god_powers,
                ("GP_MJOLNIRS_WRATH",),
                tier_order=(2, 1, 0),
                threat_tier_order=(2, 1, 0),
                minimum_score=0.4,
            )
            if mjolnir_under_pressure is not None:
                return mjolnir_under_pressure

        mjolnir_choice = best_scored_gp(
            view,
            self._god_powers,
            ("GP_MJOLNIRS_WRATH",),
            tier_order=(2, 1, 0),
            threat_tier_order=(2, 1, 0),
            minimum_score=0.2,
        )
        if mjolnir_choice is not None and threat < view.player.hp:
            return mjolnir_choice

        if player.tokens < (9 if control_opponent else 12):
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

        return mjolnir_choice
