"""
control_agent.py
----------------
L2 Control archetype agent (T1-only).

Strategy: outlast via defense and sustain.
  Keep: all dice (defense blocks, offense closes games, hands fuel GPs).
  GP priority switches on HP:
    Healthy: Aegis (block) > Tyr (block + dmg) > Eir (heal)
    Hurt:    Eir (heal)    > Aegis           > Tyr
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from simulator.agents import Agent, choose_keep_by_faces, first_affordable_gp, with_banked_tokens
from simulator.game_state import GameState
from simulator.god_powers import load_god_powers

_DEFAULT_KEEP = frozenset({
    "FACE_HELMET", "FACE_SHIELD", "FACE_HAND_BORDERED",
    "FACE_AXE", "FACE_ARROW",
})
_DEFAULT_GP_HEALTHY = ("GP_AEGIS_OF_BALDR", "GP_TYRS_JUDGMENT", "GP_EIRS_MERCY")
_DEFAULT_GP_HURT = ("GP_EIRS_MERCY", "GP_AEGIS_OF_BALDR", "GP_TYRS_JUDGMENT")
_DEFAULT_TIER_ORDER = (0,)
_DEFAULT_HP_THRESHOLD = 8


class ControlAgent(Agent):
    def __init__(
        self,
        rng: np.random.Generator | None = None,
        keep_faces: frozenset[str] | None = None,
        gp_priority_healthy: tuple[str, ...] | None = None,
        gp_priority_hurt: tuple[str, ...] | None = None,
        hp_threshold: int | None = None,
        tier_order: tuple[int, ...] | None = None,
        keep_select_fn: Callable | None = None,
        gp_select_fn: Callable | None = None,
    ) -> None:
        self.rng = rng or np.random.default_rng()
        self._god_powers = load_god_powers()
        self.keep_faces = keep_faces if keep_faces is not None else _DEFAULT_KEEP
        self.gp_priority_healthy = gp_priority_healthy if gp_priority_healthy is not None else _DEFAULT_GP_HEALTHY
        self.gp_priority_hurt = gp_priority_hurt if gp_priority_hurt is not None else _DEFAULT_GP_HURT
        self.hp_threshold = hp_threshold if hp_threshold is not None else _DEFAULT_HP_THRESHOLD
        self.tier_order = tier_order if tier_order is not None else _DEFAULT_TIER_ORDER
        self.keep_select_fn = keep_select_fn
        self.gp_select_fn = gp_select_fn

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        player = state.p1 if player_num == 1 else state.p2
        if self.keep_select_fn is not None:
            return self.keep_select_fn(state, player_num)
        return choose_keep_by_faces(player, self.keep_faces)

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        player = with_banked_tokens(state.p1 if player_num == 1 else state.p2)

        if self.gp_select_fn is not None:
            return self.gp_select_fn(state, player_num, self._god_powers)

        if player.hp <= self.hp_threshold:
            priority = self.gp_priority_hurt
        else:
            priority = self.gp_priority_healthy

        return first_affordable_gp(player, self._god_powers, priority, self.tier_order)
