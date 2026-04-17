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

from typing import Callable

import numpy as np

from simulator.agents import Agent
from simulator.game_state import GameState
from simulator.god_powers import load_god_powers

_DEFAULT_KEEP = frozenset({"FACE_ARROW", "FACE_HAND_BORDERED", "FACE_AXE"})
_DEFAULT_GP_PRIORITY = ("GP_SKADIS_VOLLEY", "GP_NJORDS_TIDE", "GP_ODINS_INSIGHT")
_DEFAULT_TIER_ORDER = (2, 1, 0)
_DEFAULT_MIN_ARROWS = 2


class ComboAgent(Agent):
    def __init__(
        self,
        rng: np.random.Generator | None = None,
        keep_faces: frozenset[str] | None = None,
        gp_priority: tuple[str, ...] | None = None,
        tier_order: tuple[int, ...] | None = None,
        min_arrows_for_skadi: int | None = None,
        gp_select_fn: Callable | None = None,
    ) -> None:
        self.rng = rng or np.random.default_rng()
        self._god_powers = load_god_powers()
        self.keep_faces = keep_faces if keep_faces is not None else _DEFAULT_KEEP
        self.gp_priority = gp_priority if gp_priority is not None else _DEFAULT_GP_PRIORITY
        self.tier_order = tier_order if tier_order is not None else _DEFAULT_TIER_ORDER
        self.min_arrows_for_skadi = min_arrows_for_skadi if min_arrows_for_skadi is not None else _DEFAULT_MIN_ARROWS
        self.gp_select_fn = gp_select_fn

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        player = state.p1 if player_num == 1 else state.p2
        return frozenset(
            i for i, (face, kept) in enumerate(zip(player.dice_faces, player.dice_kept))
            if not kept and face in self.keep_faces
        )

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        player = state.p1 if player_num == 1 else state.p2
        opponent = state.p2 if player_num == 1 else state.p1

        if self.gp_select_fn is not None:
            return self.gp_select_fn(state, player_num, self._god_powers)

        arrows = player.dice_faces.count("FACE_ARROW")
        opp_shields = opponent.dice_faces.count("FACE_SHIELD")
        unblocked = max(0, arrows - opp_shields)

        if unblocked >= self.min_arrows_for_skadi:
            choice = self._try_gp(player, "GP_SKADIS_VOLLEY")
            if choice is not None:
                return choice

        for gp_id in self.gp_priority:
            if gp_id == "GP_SKADIS_VOLLEY":
                continue
            if gp_id == "GP_ODINS_INSIGHT":
                gp = self._god_powers.get(gp_id)
                if gp is not None and gp_id in player.gp_loadout:
                    if player.tokens >= gp.tiers[2].cost:
                        return (gp_id, 2)
                continue
            choice = self._try_gp(player, gp_id)
            if choice is not None:
                return choice

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
        for tier_idx in self.tier_order:
            if player.tokens >= gp.tiers[tier_idx].cost:
                return (gp_id, tier_idx)
        return None
