"""
aggro_agent.py
--------------
L2 Aggro archetype agent.

Strategy: maximize front-loaded damage, end game by round 5-6.
  Keep: axes, arrows (damage), bordered hands (GP fuel).
  Reroll: helmets, shields, plain hands (no offensive value).
  GP priority: Surtr (cheap burst) > Fenrir (damage + bleed) > Heimdallr (unblockable).
  Always picks highest affordable tier.

This class provides the baseline archetype behavior. Experiment layers can
override keep logic or GP choice with hooks without rewriting the core agent.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from simulator.agents import Agent, choose_keep_by_faces, first_affordable_gp
from simulator.game_state import GameState
from simulator.god_powers import load_god_powers

_DEFAULT_KEEP = frozenset({"FACE_AXE", "FACE_ARROW", "FACE_HAND_BORDERED"})
_DEFAULT_GP_PRIORITY = ("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_HEIMDALLRS_WATCH")
_DEFAULT_TIER_ORDER = (2, 1, 0)


class AggroAgent(Agent):
    def __init__(
        self,
        rng: np.random.Generator | None = None,
        keep_faces: frozenset[str] | None = None,
        gp_priority: tuple[str, ...] | None = None,
        tier_order: tuple[int, ...] | None = None,
        keep_select_fn: Callable | None = None,
        gp_select_fn: Callable | None = None,
    ) -> None:
        self.rng = rng or np.random.default_rng()
        self._god_powers = load_god_powers()
        self.keep_faces = keep_faces if keep_faces is not None else _DEFAULT_KEEP
        self.gp_priority = gp_priority if gp_priority is not None else _DEFAULT_GP_PRIORITY
        self.tier_order = tier_order if tier_order is not None else _DEFAULT_TIER_ORDER
        self.keep_select_fn = keep_select_fn
        self.gp_select_fn = gp_select_fn

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        player = state.p1 if player_num == 1 else state.p2
        if self.keep_select_fn is not None:
            return self.keep_select_fn(state, player_num)
        return choose_keep_by_faces(player, self.keep_faces)

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        player = state.p1 if player_num == 1 else state.p2

        if self.gp_select_fn is not None:
            return self.gp_select_fn(state, player_num, self._god_powers)

        return first_affordable_gp(player, self._god_powers, self.gp_priority, self.tier_order)
