"""Economy-family agents used by the balance harnesses.

The module currently exposes:

- `EconomyAgent` for the baseline T1 shell
- `MatchupAwareEconomyAgent` for tuned anti-race timing
- `TierAwareEconomyAgent` for the T2/T3 escalation harness
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from simulator.agents import Agent, choose_keep_by_faces, try_gp, with_banked_tokens
from simulator.game_state import GameState
from simulator.god_powers import load_god_powers

_DEFAULT_KEEP = frozenset({
    "FACE_HAND_BORDERED", "FACE_HAND", "FACE_AXE",
    "FACE_HELMET", "FACE_SHIELD",
})
_DEFAULT_GP_PRIORITY = ("GP_MJOLNIRS_WRATH", "GP_GULLVEIGS_HOARD", "GP_FRIGGS_VEIL")
_DEFAULT_TIER_ORDER = (0,)
_DEFAULT_FRIGG_THRESHOLD = 8   # priority[2] threshold
_DEFAULT_TOKEN_THRESHOLD = 2   # priority[1] threshold


class EconomyAgent(Agent):
    """Baseline Economy pilot that ramps tokens into Mjolnir turns."""

    def __init__(
        self,
        rng: np.random.Generator | None = None,
        keep_faces: frozenset[str] | None = None,
        gp_priority: tuple[str, ...] | None = None,
        tier_order: tuple[int, ...] | None = None,
        token_threshold: int | None = None,
        frigg_threshold: int | None = None,
        keep_select_fn: Callable | None = None,
        gp_select_fn: Callable | None = None,
    ) -> None:
        self.rng = rng or np.random.default_rng()
        self._god_powers = load_god_powers()
        self.keep_faces = keep_faces if keep_faces is not None else _DEFAULT_KEEP
        self.gp_priority = gp_priority if gp_priority is not None else _DEFAULT_GP_PRIORITY
        self.tier_order = tier_order if tier_order is not None else _DEFAULT_TIER_ORDER
        self.token_threshold = token_threshold if token_threshold is not None else _DEFAULT_TOKEN_THRESHOLD
        self.frigg_threshold = frigg_threshold if frigg_threshold is not None else _DEFAULT_FRIGG_THRESHOLD
        self.keep_select_fn = keep_select_fn
        self.gp_select_fn = gp_select_fn

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        """Keep Economy's token and survivability faces unless overridden."""
        player = state.p1 if player_num == 1 else state.p2
        if self.keep_select_fn is not None:
            return self.keep_select_fn(state, player_num)
        return choose_keep_by_faces(player, self.keep_faces)

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        """Cash out into Mjolnir first, then ramp, then optional late Frigg."""
        player = state.p1 if player_num == 1 else state.p2

        if self.gp_select_fn is not None:
            return self.gp_select_fn(state, player_num, self._god_powers)

        choice = try_gp(player, self._god_powers, self.gp_priority[0], self.tier_order)
        if choice is not None:
            return choice

        if len(self.gp_priority) > 1 and player.tokens >= self.token_threshold:
            choice = try_gp(player, self._god_powers, self.gp_priority[1], self.tier_order)
            if choice is not None:
                return choice

        if len(self.gp_priority) > 2 and player.tokens >= self.frigg_threshold:
            choice = try_gp(player, self._god_powers, self.gp_priority[2], self.tier_order)
            if choice is not None:
                return choice

        return None


class MatchupAwareEconomyAgent(EconomyAgent):
    """Economy pilot that uses Bragi specifically as anti-race stabilization."""

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        """Keep the trimmed anti-race face set used by the tuned L2/L3 harnesses."""
        player = state.p1 if player_num == 1 else state.p2
        keep_faces = frozenset({
            "FACE_HAND_BORDERED",
            "FACE_HAND",
            "FACE_AXE",
            "FACE_HELMET",
            "FACE_SHIELD",
        })
        return choose_keep_by_faces(player, keep_faces)

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        """Use Bragi into Aggro pressure, otherwise follow the ramp-to-Mjolnir plan."""
        player = with_banked_tokens(state.p1 if player_num == 1 else state.p2)
        opponent = state.p2 if player_num == 1 else state.p1

        opponent_axes = opponent.dice_faces.count("FACE_AXE")
        opponent_arrows = opponent.dice_faces.count("FACE_ARROW")
        my_helmets = player.dice_faces.count("FACE_HELMET")
        my_shields = player.dice_faces.count("FACE_SHIELD")
        predicted_incoming = max(
            0,
            (opponent_axes + opponent_arrows)
            - (min(opponent_axes, my_helmets) + min(opponent_arrows, my_shields)),
        )

        if "GP_SURTRS_FLAME" in opponent.gp_loadout and predicted_incoming >= 2:
            choice = try_gp(player, self._god_powers, "GP_BRAGIS_SONG", self.tier_order)
            if choice is not None:
                return choice

        choice = try_gp(player, self._god_powers, "GP_MJOLNIRS_WRATH", self.tier_order)
        if choice is not None:
            return choice

        return try_gp(player, self._god_powers, "GP_GULLVEIGS_HOARD", self.tier_order)


class TierAwareEconomyAgent(MatchupAwareEconomyAgent):
    """Tier-aware Economy pilot for T2/T3 cash-out tuning."""

    def __init__(self, rng: np.random.Generator | None = None) -> None:
        super().__init__(rng=rng, tier_order=(2, 1, 0))

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        """Spend up on Bragi only when racing Aggro, otherwise on lethal Mjolnir lines."""
        player = with_banked_tokens(state.p1 if player_num == 1 else state.p2)
        opponent = state.p2 if player_num == 1 else state.p1

        opponent_axes = opponent.dice_faces.count("FACE_AXE")
        opponent_arrows = opponent.dice_faces.count("FACE_ARROW")
        my_helmets = player.dice_faces.count("FACE_HELMET")
        my_shields = player.dice_faces.count("FACE_SHIELD")
        predicted_incoming = max(
            0,
            (opponent_axes + opponent_arrows)
            - (min(opponent_axes, my_helmets) + min(opponent_arrows, my_shields)),
        )

        if "GP_SURTRS_FLAME" in opponent.gp_loadout and predicted_incoming >= 4:
            choice = try_gp(player, self._god_powers, "GP_BRAGIS_SONG", (2, 1, 0))
            if choice is not None:
                return choice
        if "GP_SURTRS_FLAME" in opponent.gp_loadout and predicted_incoming >= 3:
            choice = try_gp(player, self._god_powers, "GP_BRAGIS_SONG", (1, 0, 2))
            if choice is not None:
                return choice
        if "GP_SURTRS_FLAME" in opponent.gp_loadout and predicted_incoming >= 2:
            choice = try_gp(player, self._god_powers, "GP_BRAGIS_SONG", (0, 1, 2))
            if choice is not None:
                return choice

        mjolnir = self._god_powers["GP_MJOLNIRS_WRATH"]
        for tier_idx in (2, 1, 0):
            tier = mjolnir.tiers[tier_idx]
            if player.tokens >= tier.cost and opponent.hp <= tier.damage:
                return ("GP_MJOLNIRS_WRATH", tier_idx)

        choice = try_gp(player, self._god_powers, "GP_MJOLNIRS_WRATH", (1, 0, 2))
        if choice is not None:
            return choice

        return try_gp(player, self._god_powers, "GP_GULLVEIGS_HOARD", (1, 0, 2))
