"""Aggro-family agents used by the balance harnesses.

The module currently exposes:

- `AggroAgent` for the baseline T1 shell
- `TierAwareAggroAgent` for the T2/T3 escalation harness
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from simulator.agents import (
    Agent,
    choose_keep_by_faces,
    first_affordable_gp,
    try_gp,
    with_banked_tokens,
)
from simulator.game_state import GameState
from simulator.god_powers import load_god_powers

_DEFAULT_KEEP = frozenset({"FACE_AXE", "FACE_ARROW", "FACE_HAND_BORDERED"})
_DEFAULT_GP_PRIORITY = ("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_TYRS_JUDGMENT")
_DEFAULT_TIER_ORDER = (0,)


class AggroAgent(Agent):
    """Baseline Aggro pilot used in the core L2/L3 harnesses."""

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
        """Keep offensive faces and bordered hands unless a custom selector exists."""
        player = state.p1 if player_num == 1 else state.p2
        if self.keep_select_fn is not None:
            return self.keep_select_fn(state, player_num)
        return choose_keep_by_faces(player, self.keep_faces)

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        """Spend on the first affordable GP in Aggro's priority order."""
        player = with_banked_tokens(state.p1 if player_num == 1 else state.p2)

        if self.gp_select_fn is not None:
            return self.gp_select_fn(state, player_num, self._god_powers)

        return first_affordable_gp(player, self._god_powers, self.gp_priority, self.tier_order)


class TierAwareAggroAgent(AggroAgent):
    """Aggro pilot that can cash up into T2/T3 finishers when it matters."""

    def __init__(self, rng: np.random.Generator | None = None) -> None:
        super().__init__(rng=rng, tier_order=(2, 1, 0))

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        """Prefer lethal or near-lethal tier upgrades before defaulting to T1 pressure."""
        player = with_banked_tokens(state.p1 if player_num == 1 else state.p2)
        opponent = state.p2 if player_num == 1 else state.p1

        if player.tokens >= 13 and opponent.hp <= 7:
            choice = try_gp(player, self._god_powers, "GP_FENRIRS_BITE", (2,))
            if choice is not None:
                return choice
        if player.tokens >= 9 and opponent.hp <= 5:
            choice = try_gp(player, self._god_powers, "GP_FENRIRS_BITE", (1,))
            if choice is not None:
                return choice
        if player.tokens >= 7:
            choice = try_gp(player, self._god_powers, "GP_FENRIRS_BITE", (0,))
            if choice is not None:
                return choice

        if player.tokens >= 9 and opponent.hp <= 5:
            choice = try_gp(player, self._god_powers, "GP_SURTRS_FLAME", (2,))
            if choice is not None:
                return choice
        if player.tokens >= 6 and opponent.hp <= 3:
            choice = try_gp(player, self._god_powers, "GP_SURTRS_FLAME", (1,))
            if choice is not None:
                return choice

        return try_gp(player, self._god_powers, "GP_SURTRS_FLAME", (0,)) or try_gp(
            player,
            self._god_powers,
            "GP_TYRS_JUDGMENT",
            (1, 0, 2),
        )
