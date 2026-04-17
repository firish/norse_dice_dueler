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

import numpy as np

from simulator.agents import Agent
from simulator.game_state import GameState
from simulator.god_powers import load_god_powers

_KEEP_FACES = frozenset({
    "FACE_HAND_BORDERED", "FACE_HAND", "FACE_ARROW",
    "FACE_HELMET", "FACE_SHIELD",
})

_TOKEN_THRESHOLD_BIG_PLAY = 6  # fire Mjolnir T1 as soon as possible


class EconomyAgent(Agent):
    def __init__(self, rng: np.random.Generator | None = None) -> None:
        self.rng = rng or np.random.default_rng()
        self._god_powers = load_god_powers()

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        player = state.p1 if player_num == 1 else state.p2
        return frozenset(
            i for i, (face, kept) in enumerate(zip(player.dice_faces, player.dice_kept))
            if not kept and face in _KEEP_FACES
        )

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        player = state.p1 if player_num == 1 else state.p2

        # Priority 1: fire Mjolnir whenever affordable.
        choice = self._try_gp(player, "GP_MJOLNIRS_WRATH")
        if choice is not None:
            return choice

        # Priority 2: Freyja when we have excess tokens.
        if player.tokens >= _TOKEN_THRESHOLD_BIG_PLAY:
            choice = self._try_gp(player, "GP_FREYAS_BLESSING")
            if choice is not None:
                return choice

        # Priority 3: Frigg when flush.
        if player.tokens >= 9:
            choice = self._try_gp(player, "GP_FRIGGS_VEIL")
            if choice is not None:
                return choice

        # Save tokens for Mjolnir.
        return None

    def _try_gp(self, player, gp_id: str) -> tuple[str, int] | None:
        if gp_id not in player.gp_loadout:
            return None
        gp = self._god_powers.get(gp_id)
        if gp is None:
            return None
        for tier_idx in (2, 1, 0):
            if player.tokens >= gp.tiers[tier_idx].cost:
                return (gp_id, tier_idx)
        return None
