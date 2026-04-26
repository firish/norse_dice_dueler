"""Game-aware Aggro pilot."""

from __future__ import annotations

import numpy as np

from agents import Agent
from agents.game_aware.evaluator import choose_keep_by_scores, try_view_gp
from agents.game_aware.location_rules import gp_activation_blocked
from agents.game_aware.gp_strategy import choose_aggro_gp
from agents.game_aware.state_features import estimate_total_threat, view_for
from game_mechanics.game_state import GameState
from game_mechanics.god_powers import load_god_powers

_CANONICAL_GPS = frozenset({"GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_TYRS_JUDGMENT"})


class GameAwareAggroAgent(Agent):
    """Aggro agent that adapts pressure decisions to lethal and survival windows."""

    def __init__(self, rng: np.random.Generator | None = None, god_powers=None) -> None:
        self.rng = rng or np.random.default_rng()
        self._god_powers = god_powers if god_powers is not None else load_god_powers()

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        """Keep pressure by default, but respect defense when close to dying."""
        view = view_for(state, player_num)
        threat = estimate_total_threat(view, god_powers=self._god_powers)
        defense_score = 1.4 if threat >= view.player.hp else -0.5
        scores = {
            "FACE_AXE": 3.2,
            "FACE_ARROW": 2.7,
            "FACE_HAND_BORDERED": 2.2,
            "FACE_HAND": -0.2,
            "FACE_HELMET": defense_score,
            "FACE_SHIELD": defense_score,
        }
        return choose_keep_by_scores(view, scores)

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        """Choose among equipped GPs, preserving the tuned canonical trio behavior."""
        view = view_for(state, player_num)
        if gp_activation_blocked(view.state.round_num, view.state.condition_ids):
            return None
        if _CANONICAL_GPS.issubset(set(view.player.gp_loadout)):
            surtr = try_view_gp(view, self._god_powers, "GP_SURTRS_FLAME", (0,))
            fenrir = try_view_gp(view, self._god_powers, "GP_FENRIRS_BITE", (0,))
            tyr = try_view_gp(view, self._god_powers, "GP_TYRS_JUDGMENT", (0,))

            if fenrir is not None and view.opponent.hp <= 4:
                return fenrir
            if tyr is not None and view.opponent.hp <= 3:
                return tyr
            if surtr is not None and view.player.hp > 1:
                return surtr
            if fenrir is not None:
                return fenrir
            return tyr
        return choose_aggro_gp(view, self._god_powers, tier_order=(0,), threat_tier_order=(0,))
