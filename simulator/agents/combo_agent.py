"""
combo_agent.py
--------------
L2 Combo archetype agent.

Strategy: build arrow synergy with Skadi's Volley.
  Keep: arrows (core combo piece), bordered hands (GP fuel), axes (supplemental damage).
  Reroll: helmets, shields (no synergy), plain hands (less important than arrows).
  GP priority:
    - Skadi when multiple arrows showing (the payoff).
    - Njordr to reroll for more hand dice in token phase (economy boost).
    - Odin for token gain at T3 (simplified info -> tokens).
  Skadi activation condition: only use if 2+ arrows currently showing.

Loadout (from CLAUDE.md Section 9):
  Dice: 4x Hunter + 2x Gambler
  GPs:  Skadi's Volley, Njordr's Tide, Odin's Insight
"""

from __future__ import annotations

import numpy as np

from simulator.agents import Agent
from simulator.game_state import GameState
from simulator.god_powers import load_god_powers

_KEEP_FACES = frozenset({"FACE_ARROW", "FACE_HAND_BORDERED", "FACE_AXE"})

_MIN_ARROWS_FOR_SKADI = 2


class ComboAgent(Agent):
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
        opponent = state.p2 if player_num == 1 else state.p1

        # Skadi when we have enough arrows showing.
        arrows = player.dice_faces.count("FACE_ARROW")
        opp_shields = opponent.dice_faces.count("FACE_SHIELD")
        unblocked = max(0, arrows - opp_shields)

        if unblocked >= _MIN_ARROWS_FOR_SKADI:
            choice = self._try_gp(player, "GP_SKADIS_VOLLEY")
            if choice is not None:
                return choice

        # Njordr to reroll dice for better token phase.
        choice = self._try_gp(player, "GP_NJORDS_TIDE")
        if choice is not None:
            return choice

        # Odin for token gain (T3 gives 2 tokens; lower tiers are info-only, skip them).
        gp = self._god_powers.get("GP_ODINS_INSIGHT")
        if gp is not None and "GP_ODINS_INSIGHT" in player.gp_loadout:
            if player.tokens >= gp.tiers[2].cost:
                return ("GP_ODINS_INSIGHT", 2)

        # Skadi even with fewer arrows as fallback.
        if arrows > 0:
            choice = self._try_gp(player, "GP_SKADIS_VOLLEY")
            if choice is not None:
                return choice

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
