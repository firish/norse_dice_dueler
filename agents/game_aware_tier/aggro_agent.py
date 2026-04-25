"""Game+tier-aware Aggro pilot."""

from __future__ import annotations

import numpy as np

from agents import try_gp
from agents.game_aware.aggro_agent import GameAwareAggroAgent
from agents.game_aware.evaluator import choose_keep_by_scores
from agents.game_aware.gp_strategy import choose_aggro_gp
from agents.game_aware.state_features import (
    estimate_total_threat,
    opponent_has_role,
    player_with_available_tokens,
    view_for,
)
from game_mechanics.game_state import GameState

_CANONICAL_GPS = frozenset({"GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_TYRS_JUDGMENT"})


class GameAwareTierAggroAgent(GameAwareAggroAgent):
    """Aggro pilot that keeps game-aware pressure while evaluating higher GP tiers."""

    def __init__(self, rng: np.random.Generator | None = None, god_powers=None) -> None:
        super().__init__(rng=rng, god_powers=god_powers)

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        """Respect higher-tier GP threat while still pushing damage into Economy."""
        view = view_for(state, player_num)
        threat = estimate_total_threat(view, tier_order=(2, 1, 0), god_powers=self._god_powers)
        defense_score = 1.5 if threat >= view.player.hp else -0.5
        economy_opponent = opponent_has_role(view, "economy", self._god_powers)
        control_opponent = opponent_has_role(view, "control", self._god_powers)
        scores = {
            "FACE_AXE": 3.2,
            "FACE_ARROW": 2.7,
            "FACE_HAND_BORDERED": 2.2,
            "FACE_HAND": 1.0 if economy_opponent else -0.2,
            "FACE_HELMET": defense_score,
            "FACE_SHIELD": defense_score,
        }
        kept = set(choose_keep_by_scores(view, scores))
        if control_opponent and threat < view.player.hp:
            for idx, (face, already_kept) in enumerate(zip(view.player.dice_faces, view.player.dice_kept)):
                if already_kept or idx in kept:
                    continue
                if face == "FACE_HAND":
                    kept.add(idx)
                    break
        return frozenset(kept)

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        """Choose among equipped GPs, preserving the tuned canonical trio behavior."""
        view = view_for(state, player_num)
        if _CANONICAL_GPS.issubset(set(view.player.gp_loadout)):
            player = player_with_available_tokens(view)
            for tier_idx in (2, 1, 0):
                choice = try_gp(player, self._god_powers, "GP_FENRIRS_BITE", (tier_idx,))
                if choice is not None and self._god_powers["GP_FENRIRS_BITE"].tiers[tier_idx].damage >= view.opponent.hp:
                    return choice
            for tier_idx in (2, 1, 0):
                choice = try_gp(player, self._god_powers, "GP_SURTRS_FLAME", (tier_idx,))
                if choice is not None and self._god_powers["GP_SURTRS_FLAME"].tiers[tier_idx].damage >= view.opponent.hp:
                    return choice

            if opponent_has_role(view, "control", self._god_powers):
                from agents.game_aware.evaluator import best_scored_gp

                choice = best_scored_gp(
                    view,
                    self._god_powers,
                    ("GP_FENRIRS_BITE", "GP_TYRS_JUDGMENT", "GP_SURTRS_FLAME"),
                    tier_order=(2, 1, 0),
                    threat_tier_order=(2, 1, 0),
                    minimum_score=0.1,
                )
                if choice is not None:
                    return choice

            if opponent_has_role(view, "economy", self._god_powers):
                from agents.game_aware.evaluator import best_scored_gp

                choice = best_scored_gp(
                    view,
                    self._god_powers,
                    ("GP_FENRIRS_BITE", "GP_SURTRS_FLAME", "GP_TYRS_JUDGMENT"),
                    tier_order=(2, 1, 0),
                    threat_tier_order=(2, 1, 0),
                    minimum_score=0.2,
                )
                if choice is not None:
                    return choice

            from agents.game_aware.evaluator import best_scored_gp

            return best_scored_gp(
                view,
                self._god_powers,
                ("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_TYRS_JUDGMENT"),
                tier_order=(2, 1, 0),
                threat_tier_order=(2, 1, 0),
                minimum_score=0.2,
            )
        return choose_aggro_gp(view, self._god_powers, tier_order=(2, 1, 0), threat_tier_order=(2, 1, 0))
