"""Game-aware Economy pilot."""

from __future__ import annotations

import numpy as np

from agents import Agent
from agents.state_aware_agents.god_powers.gp_strategy import choose_economy_gp
from agents.state_aware_agents.locations.location_rules import gp_activation_blocked
from agents.state_aware_agents.state.state_evaluator import best_scored_gp, choose_keep_by_scores, try_view_gp
from agents.state_aware_agents.state.state_features import (
    estimate_total_threat,
    opponent_has_role,
    view_for,
)
from game_mechanics.game_state import GameState
from game_mechanics.god_powers import load_god_powers

_CANONICAL_GPS = frozenset({"GP_MJOLNIRS_WRATH", "GP_GULLVEIGS_HOARD", "GP_BRAGIS_SONG"})


class GameAwareEconomyAgent(Agent):
    """Economy agent that chooses between ramp, stabilization, and cash-out turns."""

    def __init__(self, rng: np.random.Generator | None = None, god_powers=None) -> None:
        self.rng = rng or np.random.default_rng()
        self._god_powers = god_powers if god_powers is not None else load_god_powers()

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        """Keep economy faces, but value defense when the opponent can race."""
        view = view_for(state, player_num)
        threat = estimate_total_threat(view, god_powers=self._god_powers)
        aggro_opponent = opponent_has_role(view, "aggro", self._god_powers)
        control_opponent = opponent_has_role(view, "control", self._god_powers)
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
        """Choose among equipped GPs, preserving the tuned canonical trio behavior."""
        view = view_for(state, player_num)
        if gp_activation_blocked(view.state.round_num, view.state.condition_ids):
            return None
        if _CANONICAL_GPS.issubset(set(view.player.gp_loadout)):
            threat = estimate_total_threat(view, god_powers=self._god_powers)

            mjolnir = try_view_gp(view, self._god_powers, "GP_MJOLNIRS_WRATH", (0,))
            if mjolnir is not None:
                tier = self._god_powers["GP_MJOLNIRS_WRATH"].tiers[mjolnir[1]]
                if view.opponent.hp <= tier.damage or threat < view.player.hp:
                    return mjolnir

            if opponent_has_role(view, "aggro", self._god_powers) and view.combat.incoming_total >= 2:
                bragi = try_view_gp(view, self._god_powers, "GP_BRAGIS_SONG", (0,))
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

            gullveig = try_view_gp(view, self._god_powers, "GP_GULLVEIGS_HOARD", (0,))
            if gullveig is not None and view.available_tokens < 8:
                return gullveig

            return mjolnir
        return choose_economy_gp(view, self._god_powers, tier_order=(0,), threat_tier_order=(0,))
