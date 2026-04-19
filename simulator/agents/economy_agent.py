"""
economy_agent.py
----------------
L2 Economy archetype agent (T1-only).

Strategy: build tokens, then cash out into Mjolnir.
  Keep: bordered hands, plain hands, helmets, shields, axes.
  GP priority:
    - Mjolnir when affordable (primary damage source).
    - Gullveig to accelerate toward the Mjolnir turn.
    - Frigg only as late counter-play once the economy engine is already online.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from simulator.agents import Agent, choose_keep_by_faces, try_gp, with_banked_tokens
from simulator.game_state import GameState
from simulator.god_powers import load_god_powers

_DEFAULT_KEEP = frozenset({
    "FACE_HAND_BORDERED", "FACE_HAND", "FACE_AXE",
    "FACE_HELMET", "FACE_SHIELD",
})
_DEFAULT_GP_PRIORITY = ("GP_MJOLNIRS_WRATH", "GP_GULLVEIGS_HOARD", "GP_FRIGGS_VEIL")
_DEFAULT_TIER_ORDER = (0,)
_DEFAULT_FRIGG_THRESHOLD = 8   # priority[2] threshold
_DEFAULT_TOKEN_THRESHOLD = 2   # priority[1] threshold


class EconomyAgent(Agent):
    def __init__(
        self,
        rng: np.random.Generator | None = None,
        keep_faces: frozenset[str] | None = None,
        gp_priority: tuple[str, ...] | None = None,
        tier_order: tuple[int, ...] | None = None,
        token_threshold: int | None = None,
        frigg_threshold: int | None = None,
        keep_select_fn: Callable | None = None,
        gp_select_fn: Callable | None = None,
    ) -> None:
        self.rng = rng or np.random.default_rng()
        self._god_powers = load_god_powers()
        self.keep_faces = keep_faces if keep_faces is not None else _DEFAULT_KEEP
        self.gp_priority = gp_priority if gp_priority is not None else _DEFAULT_GP_PRIORITY
        self.tier_order = tier_order if tier_order is not None else _DEFAULT_TIER_ORDER
        self.token_threshold = token_threshold if token_threshold is not None else _DEFAULT_TOKEN_THRESHOLD
        self.frigg_threshold = frigg_threshold if frigg_threshold is not None else _DEFAULT_FRIGG_THRESHOLD
        self.keep_select_fn = keep_select_fn
        self.gp_select_fn = gp_select_fn

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        player = with_banked_tokens(state.p1 if player_num == 1 else state.p2)
        if self.keep_select_fn is not None:
            return self.keep_select_fn(state, player_num)
        return choose_keep_by_faces(player, self.keep_faces)

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        player = state.p1 if player_num == 1 else state.p2

        if self.gp_select_fn is not None:
            return self.gp_select_fn(state, player_num, self._god_powers)

        choice = try_gp(player, self._god_powers, self.gp_priority[0], self.tier_order)
        if choice is not None:
            return choice

        if len(self.gp_priority) > 1 and player.tokens >= self.token_threshold:
            choice = try_gp(player, self._god_powers, self.gp_priority[1], self.tier_order)
            if choice is not None:
                return choice

        if len(self.gp_priority) > 2 and player.tokens >= self.frigg_threshold:
            choice = try_gp(player, self._god_powers, self.gp_priority[2], self.tier_order)
            if choice is not None:
                return choice

        return None
