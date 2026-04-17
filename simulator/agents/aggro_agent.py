"""
aggro_agent.py
--------------
L2 Aggro archetype agent.

Strategy: maximize front-loaded damage, end game by round 5-6.
  Keep: axes, arrows (damage), bordered hands (GP fuel).
  Reroll: helmets, shields, plain hands (no offensive value).
  GP priority: Surtr (cheap burst) > Fenrir (damage + bleed) > Heimdallr (unblockable).
  Always picks highest affordable tier.

Loadout (from CLAUDE.md Section 9):
  Dice: 4x Berserkr + 2x Gambler
  GPs:  Surtr's Flame, Fenrir's Bite, Heimdallr's Watch
"""

from __future__ import annotations

import numpy as np

from simulator.agents import Agent
from simulator.game_state import GameState
from simulator.god_powers import load_god_powers

_KEEP_FACES = frozenset({"FACE_AXE", "FACE_ARROW", "FACE_HAND_BORDERED"})

_GP_PRIORITY = ("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_HEIMDALLRS_WATCH")


class AggroAgent(Agent):
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

        for gp_id in _GP_PRIORITY:
            if gp_id not in player.gp_loadout:
                continue
            gp = self._god_powers.get(gp_id)
            if gp is None:
                continue
            for tier_idx in (2, 1, 0):
                if player.tokens >= gp.tiers[tier_idx].cost:
                    return (gp_id, tier_idx)

        return None
