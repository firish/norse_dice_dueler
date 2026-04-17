"""
control_agent.py
----------------
L2 Control archetype agent.

Strategy: survive to round 8+, outlast opponent with defense and healing.
  Keep: all dice (defense blocks damage, offense provides kill pressure, hands fuel GPs).
  Control wins by sustaining - it needs SOME offense to eventually close out games.
  GP priority: Aegis (block GP damage) > Eir (heal) > Vidar (reflect big plays).

Loadout (from CLAUDE.md Section 9):
  Dice: 4x Warden + 2x Huskarl
  GPs:  Aegis of Baldr, Eir's Mercy, Vidar's Reflection
"""

from __future__ import annotations

import numpy as np

from simulator.agents import Agent
from simulator.game_state import GameState
from simulator.god_powers import load_god_powers

_KEEP_FACES = frozenset({
    "FACE_HELMET", "FACE_SHIELD", "FACE_HAND_BORDERED",
    "FACE_AXE", "FACE_ARROW",
})



class ControlAgent(Agent):
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

        # When hurt: heal first, then shield
        # When healthy: Tyr for offense+defense, then Aegis
        if player.hp <= 8:
            priority = ("GP_EIRS_MERCY", "GP_AEGIS_OF_BALDR", "GP_TYRS_JUDGMENT")
        else:
            priority = ("GP_TYRS_JUDGMENT", "GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY")

        for gp_id in priority:
            if gp_id not in player.gp_loadout:
                continue
            gp = self._god_powers.get(gp_id)
            if gp is None:
                continue
            for tier_idx in (0, 1, 2):
                if player.tokens >= gp.tiers[tier_idx].cost:
                    return (gp_id, tier_idx)

        return None
