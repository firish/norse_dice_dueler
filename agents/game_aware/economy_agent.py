"""Game-aware Economy pilot."""

from __future__ import annotations

import numpy as np

from agents import Agent, try_gp
from agents.game_aware.evaluator import best_scored_gp, choose_keep_by_scores
from agents.game_aware.state_features import (
    estimate_total_threat,
    opponent_has_role,
    player_with_available_tokens,
    view_for,
)
from game_mechanics.game_state import GameState
from game_mechanics.god_powers import load_god_powers


class GameAwareEconomyAgent(Agent):
    """Economy agent that chooses between ramp, stabilization, and cash-out turns."""

    def __init__(self, rng: np.random.Generator | None = None, god_powers=None) -> None:
        self.rng = rng or np.random.default_rng()
        self._god_powers = god_powers if god_powers is not None else load_god_powers()

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        """Keep economy faces, but value defense when the opponent can race."""
        view = view_for(state, player_num)
        threat = estimate_total_threat(view)
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
        """Stabilize with Bragi under race pressure, otherwise ramp or cash out."""
        view = view_for(state, player_num)
        player = player_with_available_tokens(view)
        threat = estimate_total_threat(view)

        mjolnir = try_gp(player, self._god_powers, "GP_MJOLNIRS_WRATH", (0,))
        if mjolnir is not None:
            tier = self._god_powers["GP_MJOLNIRS_WRATH"].tiers[mjolnir[1]]
            if view.opponent.hp <= tier.damage or threat < view.player.hp:
                return mjolnir

        if opponent_has_role(view, "aggro") and view.combat.incoming_total >= 2:
            bragi = try_gp(player, self._god_powers, "GP_BRAGIS_SONG", (0,))
            if bragi is not None:
                return bragi

        if threat >= view.player.hp:
            defensive = best_scored_gp(
                view,
                self._god_powers,
                ("GP_BRAGIS_SONG", "GP_MJOLNIRS_WRATH"),
                tier_order=(0,),
                minimum_score=0.5,
            )
            if defensive is not None:
                return defensive

        gullveig = try_gp(player, self._god_powers, "GP_GULLVEIGS_HOARD", (0,))
        if gullveig is not None and player.tokens < 8:
            return gullveig

        return mjolnir
