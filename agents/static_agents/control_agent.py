"""Control-family agents used by the balance harnesses.

The module currently exposes:

- `ControlAgent` for the baseline T1 shell
- `MatchupAwareControlAgent` for tuned anti-Economy timing
- `TierAwareControlAgent` for the T2/T3 escalation harness
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from agents import (
    Agent,
    choose_keep_by_faces,
    first_affordable_gp,
    try_gp,
    with_banked_tokens,
)
from game_mechanics.game_state import GameState
from game_mechanics.god_powers import load_god_powers

_DEFAULT_KEEP = frozenset({
    "FACE_HELMET", "FACE_SHIELD", "FACE_HAND_BORDERED",
    "FACE_AXE", "FACE_ARROW",
})
_DEFAULT_GP_HEALTHY = ("GP_AEGIS_OF_BALDR", "GP_TYRS_JUDGMENT", "GP_EIRS_MERCY")
_DEFAULT_GP_HURT = ("GP_EIRS_MERCY", "GP_AEGIS_OF_BALDR", "GP_TYRS_JUDGMENT")
_DEFAULT_TIER_ORDER = (0,)
_DEFAULT_HP_THRESHOLD = 8


class ControlAgent(Agent):
    """Baseline Control pilot centered on defense, sustain, and Tyr chip damage."""

    def __init__(
        self,
        rng: np.random.Generator | None = None,
        god_powers=None,
        keep_faces: frozenset[str] | None = None,
        gp_priority_healthy: tuple[str, ...] | None = None,
        gp_priority_hurt: tuple[str, ...] | None = None,
        hp_threshold: int | None = None,
        tier_order: tuple[int, ...] | None = None,
        keep_select_fn: Callable | None = None,
        gp_select_fn: Callable | None = None,
    ) -> None:
        self.rng = rng or np.random.default_rng()
        self._god_powers = god_powers if god_powers is not None else load_god_powers()
        self.keep_faces = keep_faces if keep_faces is not None else _DEFAULT_KEEP
        self.gp_priority_healthy = gp_priority_healthy if gp_priority_healthy is not None else _DEFAULT_GP_HEALTHY
        self.gp_priority_hurt = gp_priority_hurt if gp_priority_hurt is not None else _DEFAULT_GP_HURT
        self.hp_threshold = hp_threshold if hp_threshold is not None else _DEFAULT_HP_THRESHOLD
        self.tier_order = tier_order if tier_order is not None else _DEFAULT_TIER_ORDER
        self.keep_select_fn = keep_select_fn
        self.gp_select_fn = gp_select_fn

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        """Keep Control's defensive and utility faces unless overridden."""
        player = state.p1 if player_num == 1 else state.p2
        if self.keep_select_fn is not None:
            return self.keep_select_fn(state, player_num)
        return choose_keep_by_faces(player, self.keep_faces)

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        """Switch between healthy and hurt GP priorities based on current HP."""
        player = with_banked_tokens(state.p1 if player_num == 1 else state.p2)

        if self.gp_select_fn is not None:
            return self.gp_select_fn(state, player_num, self._god_powers)

        if player.hp <= self.hp_threshold:
            priority = self.gp_priority_hurt
        else:
            priority = self.gp_priority_healthy

        return first_affordable_gp(player, self._god_powers, priority, self.tier_order)


class MatchupAwareControlAgent(ControlAgent):
    """Control pilot tuned around anti-Economy timing without losing the Aggro edge."""

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        """Prioritize hands a little more when the opponent advertises Mjolnir."""
        player = state.p1 if player_num == 1 else state.p2
        opponent = state.p2 if player_num == 1 else state.p1
        if "GP_MJOLNIRS_WRATH" in opponent.gp_loadout:
            keep_faces = frozenset({
                "FACE_HELMET",
                "FACE_SHIELD",
                "FACE_HAND_BORDERED",
                "FACE_HAND",
                "FACE_AXE",
            })
        else:
            keep_faces = self.keep_faces
        return choose_keep_by_faces(player, keep_faces)

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        """Use Frigg/Tyr timing into Economy and the default healthy/hurt flow elsewhere."""
        player = with_banked_tokens(state.p1 if player_num == 1 else state.p2)
        opponent = with_banked_tokens(state.p2 if player_num == 1 else state.p1)

        if "GP_MJOLNIRS_WRATH" in opponent.gp_loadout:
            choice = try_gp(player, self._god_powers, "GP_FRIGGS_VEIL", self.tier_order)
            if choice is not None:
                return choice
            choice = try_gp(player, self._god_powers, "GP_TYRS_JUDGMENT", self.tier_order)
            if choice is not None:
                return choice
            return try_gp(player, self._god_powers, "GP_AEGIS_OF_BALDR", self.tier_order)

        priority = self.gp_priority_hurt if player.hp <= self.hp_threshold else self.gp_priority_healthy
        return first_affordable_gp(player, self._god_powers, priority, self.tier_order)


class TierAwareControlAgent(MatchupAwareControlAgent):
    """Tier-aware Control pilot for the T2/T3 escalation harness."""

    def __init__(self, rng: np.random.Generator | None = None, god_powers=None) -> None:
        super().__init__(rng=rng, god_powers=god_powers, tier_order=(2, 1, 0))

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        """Spend up on defensive tiers only when the incoming threat justifies it."""
        player = with_banked_tokens(state.p1 if player_num == 1 else state.p2)
        opponent = with_banked_tokens(state.p2 if player_num == 1 else state.p1)

        opponent_axes = opponent.dice_faces.count("FACE_AXE")
        opponent_arrows = opponent.dice_faces.count("FACE_ARROW")
        my_helmets = player.dice_faces.count("FACE_HELMET")
        my_shields = player.dice_faces.count("FACE_SHIELD")
        incoming = max(
            0,
            (opponent_axes + opponent_arrows)
            - (min(opponent_axes, my_helmets) + min(opponent_arrows, my_shields)),
        )
        if "GP_SURTRS_FLAME" in opponent.gp_loadout and opponent.tokens >= 3:
            incoming += 2
        if "GP_MJOLNIRS_WRATH" in opponent.gp_loadout and opponent.tokens >= 8:
            incoming += 3

        if "GP_SURTRS_FLAME" in opponent.gp_loadout:
            if incoming >= 5 or (opponent.tokens >= 7 and player.tokens >= 7):
                choice = try_gp(player, self._god_powers, "GP_AEGIS_OF_BALDR", (1, 0, 2))
                if choice is not None:
                    return choice
            if incoming >= 3 or opponent.tokens >= 3:
                choice = try_gp(player, self._god_powers, "GP_AEGIS_OF_BALDR", (0, 1, 2))
                if choice is not None:
                    return choice
            if player.hp <= 9:
                choice = try_gp(player, self._god_powers, "GP_TYRS_JUDGMENT", (0, 1, 2))
                if choice is not None:
                    return choice
            if player.hp <= 3:
                return try_gp(player, self._god_powers, "GP_EIRS_MERCY", (1, 0, 2))

        if player.hp <= 4:
            return try_gp(player, self._god_powers, "GP_EIRS_MERCY", (2, 1, 0))
        if player.hp <= 7:
            choice = try_gp(player, self._god_powers, "GP_EIRS_MERCY", (1, 0, 2))
            if choice is not None:
                return choice

        if incoming >= 7:
            choice = try_gp(player, self._god_powers, "GP_AEGIS_OF_BALDR", (2, 1, 0))
            if choice is not None:
                return choice
        if incoming >= 5:
            choice = try_gp(player, self._god_powers, "GP_AEGIS_OF_BALDR", (1, 0, 2))
            if choice is not None:
                return choice
        if incoming >= 2:
            choice = try_gp(player, self._god_powers, "GP_AEGIS_OF_BALDR", (0, 1, 2))
            if choice is not None:
                return choice

        if player.hp <= 8:
            return try_gp(player, self._god_powers, "GP_TYRS_JUDGMENT", (1, 0, 2))
        return try_gp(player, self._god_powers, "GP_TYRS_JUDGMENT", (0, 1, 2))
