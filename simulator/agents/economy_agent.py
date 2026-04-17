"""
economy_agent.py
----------------
L2 Economy archetype agent.

Strategy: build tokens, fire Mjolnir as soon as affordable.
  Keep: bordered hands, plain hands, arrows, helmets, shields. Only reroll axes.
  GP priority:
    - Mjolnir when affordable (primary damage source).
    - Freyja to build tokens when Mjolnir isn't affordable.
    - Frigg as counter-play when flush.

Loadout:
  Dice: 3x Miser + 2x Huskarl + 1x Warden
  GPs:  Mjolnir's Wrath, Freyja's Blessing, Frigg's Veil
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from simulator.agents import Agent
from simulator.game_state import GameState
from simulator.god_powers import load_god_powers

_DEFAULT_KEEP = frozenset({
    "FACE_HAND_BORDERED", "FACE_HAND", "FACE_ARROW",
    "FACE_HELMET", "FACE_SHIELD",
})
_DEFAULT_GP_PRIORITY = ("GP_MJOLNIRS_WRATH", "GP_FREYAS_BLESSING", "GP_FRIGGS_VEIL")
_DEFAULT_TIER_ORDER = (2, 1, 0)
_DEFAULT_TOKEN_THRESHOLD = 6
_DEFAULT_FRIGG_THRESHOLD = 9


class EconomyAgent(Agent):
    def __init__(
        self,
        rng: np.random.Generator | None = None,
        keep_faces: frozenset[str] | None = None,
        gp_priority: tuple[str, ...] | None = None,
        tier_order: tuple[int, ...] | None = None,
        token_threshold: int | None = None,
        frigg_threshold: int | None = None,
        gp_select_fn: Callable | None = None,
    ) -> None:
        self.rng = rng or np.random.default_rng()
        self._god_powers = load_god_powers()
        self.keep_faces = keep_faces if keep_faces is not None else _DEFAULT_KEEP
        self.gp_priority = gp_priority if gp_priority is not None else _DEFAULT_GP_PRIORITY
        self.tier_order = tier_order if tier_order is not None else _DEFAULT_TIER_ORDER
        self.token_threshold = token_threshold if token_threshold is not None else _DEFAULT_TOKEN_THRESHOLD
        self.frigg_threshold = frigg_threshold if frigg_threshold is not None else _DEFAULT_FRIGG_THRESHOLD
        self.gp_select_fn = gp_select_fn

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        player = state.p1 if player_num == 1 else state.p2
        return frozenset(
            i for i, (face, kept) in enumerate(zip(player.dice_faces, player.dice_kept))
            if not kept and face in self.keep_faces
        )

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        player = state.p1 if player_num == 1 else state.p2

        if self.gp_select_fn is not None:
            return self.gp_select_fn(state, player_num, self._god_powers)

        choice = self._try_gp(player, self.gp_priority[0])
        if choice is not None:
            return choice

        if player.tokens >= self.token_threshold:
            choice = self._try_gp(player, self.gp_priority[1])
            if choice is not None:
                return choice

        if len(self.gp_priority) > 2 and player.tokens >= self.frigg_threshold:
            choice = self._try_gp(player, self.gp_priority[2])
            if choice is not None:
                return choice

        return None

    def _try_gp(self, player, gp_id: str) -> tuple[str, int] | None:
        if gp_id not in player.gp_loadout:
            return None
        gp = self._god_powers.get(gp_id)
        if gp is None:
            return None
        for tier_idx in self.tier_order:
            if player.tokens >= gp.tiers[tier_idx].cost:
                return (gp_id, tier_idx)
        return None
