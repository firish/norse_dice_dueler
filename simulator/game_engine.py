"""
game_engine.py
--------------
Pure game logic. Holds only an RNG as mutable state; everything else is
derived from the immutable GameState passed in.

Pattern:
    state, events = engine.step(state, p1_action, p2_action)

Agents only need to supply actions for KEEP_1, KEEP_2, and GOD_POWER phases.
All other phases advance automatically (no agent input required).

L2 scope:
    - All 16 God Powers resolved with full resolution order.
    - Bleed ticks in REVEAL phase.
    - Heimdallr unblockable attacks in COMBAT phase.
    - No Battlefield Conditions (L4), no Runes (L5).
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import numpy as np

from simulator.game_state import GameEvent, GamePhase, GameState, PlayerState
from simulator.die_types import DieType
from simulator.god_powers import GodPower, load_god_powers

if TYPE_CHECKING:
    from simulator.agents import Agent

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
NUM_DICE = 6
STARTING_HP = 15
STARTING_TOKENS = 0
_BLANK_FACES = ("",) * NUM_DICE
_ALL_FREE = (False,) * NUM_DICE


# ---------------------------------------------------------------------------
# Internal die-rolling helpers (not part of the public API)
# ---------------------------------------------------------------------------

def _roll_die(die: DieType, rng: np.random.Generator) -> str:
    """Return one randomly selected face from the given die."""
    return die.faces[rng.integers(0, NUM_DICE)]


def _roll_all(die_types: list[DieType], rng: np.random.Generator) -> tuple[str, ...]:
    """Roll each die in the loadout once and return the resulting faces."""
    return tuple(_roll_die(d, rng) for d in die_types)


def _reroll_unkept(
    faces: tuple[str, ...],
    kept: tuple[bool, ...],
    die_types: list[DieType],
    rng: np.random.Generator,
) -> tuple[str, ...]:
    """Reroll only the dice not marked as kept and return the new faces."""
    new = list(faces)
    for i, (k, die) in enumerate(zip(kept, die_types)):
        if not k:
            new[i] = _roll_die(die, rng)
    return tuple(new)


def _apply_keep(
    prev_kept: tuple[bool, ...],
    new_indices: frozenset[int],
) -> tuple[bool, ...]:
    """Merge newly kept indices into the existing keep mask."""
    return tuple(prev_kept[i] or (i in new_indices) for i in range(NUM_DICE))


# ---------------------------------------------------------------------------
# GameEngine
# ---------------------------------------------------------------------------

class GameEngine:
    """
    Stateless game-rule machine (except for the RNG).

    Args:
        p1_die_types:  Ordered list of 6 DieType objects for player 1's loadout.
        p2_die_types:  Ordered list of 6 DieType objects for player 2's loadout.
        rng:           numpy Generator. Pass a seeded rng for reproducibility.
        p1_gp_ids:     Tuple of up to 3 GP IDs for player 1 (empty = L0, no GPs).
        p2_gp_ids:     Tuple of up to 3 GP IDs for player 2 (empty = L0, no GPs).
    """

    def __init__(
        self,
        p1_die_types: list[DieType],
        p2_die_types: list[DieType],
        rng: np.random.Generator | None = None,
        p1_gp_ids: tuple[str, ...] = (),
        p2_gp_ids: tuple[str, ...] = (),
        enable_thorns: bool = True,
        enable_token_shield: bool = True,
    ) -> None:
        assert len(p1_die_types) == NUM_DICE, f"P1 loadout must have {NUM_DICE} dice"
        assert len(p2_die_types) == NUM_DICE, f"P2 loadout must have {NUM_DICE} dice"
        self.p1_die_types = p1_die_types
        self.p2_die_types = p2_die_types
        self.rng = rng or np.random.default_rng()
        self.p1_gp_ids = p1_gp_ids
        self.p2_gp_ids = p2_gp_ids
        # House-rule toggles. Default ON to preserve L0/L1/L2 baseline behavior.
        # thorns: every 2 successful blocks deal 1 damage back to attacker.
        # token_shield: every 4 tokens held reduces incoming dice damage by 1.
        self.enable_thorns = enable_thorns
        self.enable_token_shield = enable_token_shield
        # Load GP definitions once; empty if no GPs in either loadout.
        if p1_gp_ids or p2_gp_ids:
            self._god_powers = load_god_powers()
        else:
            self._god_powers: dict = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def new_game(self) -> GameState:
        """Return the initial GameState at the start of round 1."""
        return GameState(
            round_num=1,
            phase=GamePhase.REVEAL,
            p1=PlayerState(
                hp=STARTING_HP,
                tokens=STARTING_TOKENS,
                dice_faces=_BLANK_FACES,
                dice_kept=_ALL_FREE,
                gp_loadout=self.p1_gp_ids,
            ),
            p2=PlayerState(
                hp=STARTING_HP,
                tokens=STARTING_TOKENS,
                dice_faces=_BLANK_FACES,
                dice_kept=_ALL_FREE,
                gp_loadout=self.p2_gp_ids,
            ),
            winner=None,
        )

    def step(
        self,
        state: GameState,
        p1_action: frozenset[int] | tuple[str, int] | None = None,
        p2_action: frozenset[int] | tuple[str, int] | None = None,
    ) -> tuple[GameState, list[GameEvent]]:
        """
        Advance the game by one phase.

        p1_action / p2_action meaning depends on the current phase:
          KEEP_1 / KEEP_2:  frozenset[int] - die indices to lock in.
          GOD_POWER:        tuple[str, int] - (gp_id, tier_idx 0-2), or None to pass.
          All other phases: ignored.
        """
        phase = state.phase
        if phase == GamePhase.REVEAL:
            return self._phase_reveal(state)
        if phase == GamePhase.ROLL:
            return self._phase_roll(state)
        if phase == GamePhase.KEEP_1:
            return self._phase_keep(state, p1_action, p2_action, next_phase=GamePhase.REROLL_1)
        if phase == GamePhase.REROLL_1:
            return self._phase_reroll(state, next_phase=GamePhase.KEEP_2)
        if phase == GamePhase.KEEP_2:
            return self._phase_keep(state, p1_action, p2_action, next_phase=GamePhase.REROLL_2)
        if phase == GamePhase.REROLL_2:
            return self._phase_reroll(state, next_phase=GamePhase.GOD_POWER)
        if phase == GamePhase.GOD_POWER:
            return self._phase_god_power(state, p1_action, p2_action)  # type: ignore[arg-type]
        if phase == GamePhase.COMBAT:
            return self._phase_combat(state)
        if phase == GamePhase.GOD_RESOLVE:
            return self._phase_god_resolve(state)
        if phase == GamePhase.TOKENS:
            return self._phase_tokens(state)
        if phase == GamePhase.END_CHECK:
            return self._phase_end_check(state)
        raise ValueError(f"Cannot step from terminal phase {phase}")

    def run_round(
        self,
        state: GameState,
        p1_agent: "Agent",
        p2_agent: "Agent",
    ) -> tuple[GameState, list[GameEvent]]:
        """
        Run all phases of one round, collecting agent decisions where needed.
        Assumes state.phase == REVEAL at entry.
        Returns the state after END_CHECK (either GAME_OVER or REVEAL of next round).
        """
        all_events: list[GameEvent] = []

        def tick(p1_act=None, p2_act=None):
            nonlocal state
            state, evts = self.step(state, p1_act, p2_act)
            all_events.extend(evts)

        tick()                                              # REVEAL -> ROLL
        tick()                                              # ROLL -> KEEP_1
        tick(p1_agent.choose_keep(state, 1),                # KEEP_1 -> REROLL_1
             p2_agent.choose_keep(state, 2))
        tick()                                              # REROLL_1 -> KEEP_2
        tick(p1_agent.choose_keep(state, 1),                # KEEP_2 -> REROLL_2
             p2_agent.choose_keep(state, 2))
        tick()                                              # REROLL_2 -> GOD_POWER
        tick(p1_agent.choose_god_power(state, 1),           # GOD_POWER -> COMBAT
             p2_agent.choose_god_power(state, 2))
        tick()                                              # COMBAT -> GOD_RESOLVE
        tick()                                              # GOD_RESOLVE -> TOKENS
        tick()                                              # TOKENS -> END_CHECK
        tick()                                              # END_CHECK -> REVEAL / GAME_OVER

        return state, all_events

    def run_game(
        self,
        p1_agent: "Agent",
        p2_agent: "Agent",
        max_rounds: int = 100,
    ) -> tuple[GameState, list[GameEvent]]:
        """
        Play a complete game from start to GAME_OVER.

        max_rounds is a safety cap; a game that reaches it is recorded as a draw.
        """
        state = self.new_game()
        all_events: list[GameEvent] = []

        while state.phase != GamePhase.GAME_OVER:
            if state.round_num > max_rounds:
                state = replace(state, phase=GamePhase.GAME_OVER, winner=0)
                all_events.append(GameEvent(
                    "game_over",
                    {"winner": 0, "round": state.round_num,
                     "p1_hp": state.p1.hp, "p2_hp": state.p2.hp,
                     "reason": "max_rounds_exceeded"},
                ))
                break
            state, events = self.run_round(state, p1_agent, p2_agent)
            all_events.extend(events)

        return state, all_events

    # ------------------------------------------------------------------
    # Phase implementations (private)
    # ------------------------------------------------------------------

    def _phase_reveal(self, state: GameState) -> tuple[GameState, list[GameEvent]]:
        """Bleed ticks (L2+), battlefield conditions (L4+). Then advance to ROLL."""
        events: list[GameEvent] = []
        p1 = state.p1
        p2 = state.p2

        # Bleed: 1 dmg per stack, then decrement stacks by 1.
        if p1.bleed_stacks > 0:
            p1 = replace(p1, hp=p1.hp - p1.bleed_stacks, bleed_stacks=p1.bleed_stacks - 1)
            events.append(GameEvent("bleed_tick", {"player": 1, "damage": state.p1.bleed_stacks, "remaining": p1.bleed_stacks}))
        if p2.bleed_stacks > 0:
            p2 = replace(p2, hp=p2.hp - p2.bleed_stacks, bleed_stacks=p2.bleed_stacks - 1)
            events.append(GameEvent("bleed_tick", {"player": 2, "damage": state.p2.bleed_stacks, "remaining": p2.bleed_stacks}))

        return replace(state, phase=GamePhase.ROLL, p1=p1, p2=p2), events

    def _phase_roll(self, state: GameState) -> tuple[GameState, list[GameEvent]]:
        p1_faces = _roll_all(self.p1_die_types, self.rng)
        p2_faces = _roll_all(self.p2_die_types, self.rng)
        new_state = replace(
            state,
            phase=GamePhase.KEEP_1,
            p1=replace(state.p1, dice_faces=p1_faces, dice_kept=_ALL_FREE),
            p2=replace(state.p2, dice_faces=p2_faces, dice_kept=_ALL_FREE),
        )
        return new_state, [GameEvent("dice_rolled", {"p1": p1_faces, "p2": p2_faces})]

    def _phase_keep(
        self,
        state: GameState,
        p1_action: frozenset[int] | None,
        p2_action: frozenset[int] | None,
        next_phase: GamePhase,
    ) -> tuple[GameState, list[GameEvent]]:
        p1_kept = _apply_keep(state.p1.dice_kept, p1_action or frozenset())
        p2_kept = _apply_keep(state.p2.dice_kept, p2_action or frozenset())
        new_state = replace(
            state,
            phase=next_phase,
            p1=replace(state.p1, dice_kept=p1_kept),
            p2=replace(state.p2, dice_kept=p2_kept),
        )
        return new_state, []

    def _phase_reroll(
        self,
        state: GameState,
        next_phase: GamePhase,
    ) -> tuple[GameState, list[GameEvent]]:
        p1_faces = _reroll_unkept(
            state.p1.dice_faces, state.p1.dice_kept, self.p1_die_types, self.rng
        )
        p2_faces = _reroll_unkept(
            state.p2.dice_faces, state.p2.dice_kept, self.p2_die_types, self.rng
        )
        new_state = replace(
            state,
            phase=next_phase,
            p1=replace(state.p1, dice_faces=p1_faces),
            p2=replace(state.p2, dice_faces=p2_faces),
        )
        return new_state, []

    def _phase_god_power(
        self,
        state: GameState,
        p1_action: tuple[str, int] | None,
        p2_action: tuple[str, int] | None,
    ) -> tuple[GameState, list[GameEvent]]:
        """
        Accept GP choices from both agents, validate them, deduct token costs,
        and write the confirmed choice into each PlayerState for GOD_RESOLVE.

        Validation rules:
          - GP must be in the player's loadout.
          - Tier index must be 0, 1, or 2.
          - Player must have enough tokens to pay the cost.
        Invalid choices are silently treated as a pass (None).
        """
        p1 = state.p1
        p2 = state.p2
        events: list[GameEvent] = []

        def _validate(
            player: PlayerState,
            action: tuple[str, int] | None,
            player_num: int,
        ) -> tuple[PlayerState, tuple[str, int] | None]:
            if action is None:
                return player, None
            gp_id, tier_idx = action
            if gp_id not in player.gp_loadout:
                return player, None
            if tier_idx not in (0, 1, 2):
                return player, None
            gp = self._god_powers.get(gp_id)
            if gp is None:
                return player, None
            tier = gp.tiers[tier_idx]
            if player.tokens < tier.cost:
                return player, None
            # Valid - deduct tokens and record choice.
            new_player = replace(
                player,
                tokens=player.tokens - tier.cost,
                gp_choice=(gp_id, tier_idx),
            )
            events.append(GameEvent("gp_chosen", {
                "player": player_num, "gp_id": gp_id,
                "tier": tier_idx, "cost": tier.cost,
            }))
            return new_player, (gp_id, tier_idx)

        p1, _ = _validate(p1, p1_action, 1)
        p2, _ = _validate(p2, p2_action, 2)

        return replace(state, phase=GamePhase.COMBAT, p1=p1, p2=p2), events

    def _phase_combat(self, state: GameState) -> tuple[GameState, list[GameEvent]]:
        """
        Simultaneous attack resolution.
        Axes blocked by opponent Helmets; Arrows blocked by opponent Shields.
        Heimdallr's Watch makes N attacks unblockable (99 = all).
        Heimdallr's damage_reduction reduces incoming damage.
        """
        p1 = state.p1
        p2 = state.p2

        p1_axes   = p1.dice_faces.count("FACE_AXE")
        p1_arrows = p1.dice_faces.count("FACE_ARROW")
        p2_axes   = p2.dice_faces.count("FACE_AXE")
        p2_arrows = p2.dice_faces.count("FACE_ARROW")
        p1_helmets = p1.dice_faces.count("FACE_HELMET")
        p1_shields = p1.dice_faces.count("FACE_SHIELD")
        p2_helmets = p2.dice_faces.count("FACE_HELMET")
        p2_shields = p2.dice_faces.count("FACE_SHIELD")

        p1_unblockable, p1_dmg_red = self._get_heimdallr_buffs(p1)
        p2_unblockable, p2_dmg_red = self._get_heimdallr_buffs(p2)

        dmg_to_p2, p2_blocks, p2_baxes, p2_barrows = self._calc_dice_damage(p1_axes, p1_arrows, p2_helmets, p2_shields, p1_unblockable)
        dmg_to_p1, p1_blocks, p1_baxes, p1_barrows = self._calc_dice_damage(p2_axes, p2_arrows, p1_helmets, p1_shields, p2_unblockable)

        dmg_to_p1 = max(0, dmg_to_p1 - p1_dmg_red)
        dmg_to_p2 = max(0, dmg_to_p2 - p2_dmg_red)

        # Token-threshold defense (uncapped): every 4 tokens held reduces
        # incoming dice damage by 1. Checked at start of combat (post-GP payment),
        # so spending tokens on a GP reduces your shield - real tradeoff.
        if self.enable_token_shield:
            p1_token_shield = p1.tokens // 4
            p2_token_shield = p2.tokens // 4
            dmg_to_p1 = max(0, dmg_to_p1 - p1_token_shield)
            dmg_to_p2 = max(0, dmg_to_p2 - p2_token_shield)

        # Successful dice blocks generate tokens (1 per 2 blocks, round up).
        # p1_tokens = p1.tokens + (p1_blocks + 1) // 2
        # p2_tokens = p2.tokens + (p2_blocks + 1) // 2
        p1_tokens = p1.tokens
        p2_tokens = p2.tokens

        # Thorns: every 2 blocked attacks (any type) deal 1 damage back to the attacker.
        # 2 blocks -> 1, 4 -> 2, 6 -> 3.
        if self.enable_thorns:
            thorns_to_p1 = (p2_baxes + p2_barrows) // 2
            thorns_to_p2 = (p1_baxes + p1_barrows) // 2
        else:
            thorns_to_p1 = 0
            thorns_to_p2 = 0

        new_state = replace(
            state,
            phase=GamePhase.GOD_RESOLVE,
            p1=replace(p1, hp=p1.hp - dmg_to_p1 - thorns_to_p1, tokens=p1_tokens),
            p2=replace(p2, hp=p2.hp - dmg_to_p2 - thorns_to_p2, tokens=p2_tokens),
        )
        return new_state, [
            GameEvent("combat", {
                "dmg_to_p1": dmg_to_p1, "dmg_to_p2": dmg_to_p2,
                "p1_block_tokens": p1_blocks, "p2_block_tokens": p2_blocks,
                "thorns_to_p1": thorns_to_p1, "thorns_to_p2": thorns_to_p2,
            })
        ]

    def _get_heimdallr_buffs(self, player: PlayerState) -> tuple[int, int]:
        """Return (unblockable_count, damage_reduction) from Heimdallr's Watch if chosen."""
        if player.gp_choice is None:
            return 0, 0
        gp_id, tier_idx = player.gp_choice
        if gp_id != "GP_HEIMDALLRS_WATCH":
            return 0, 0
        gp = self._god_powers.get(gp_id)
        if gp is None:
            return 0, 0
        tier = gp.tiers[tier_idx]
        return tier.unblockable, tier.damage_reduction

    @staticmethod
    def _calc_dice_damage(
        axes: int, arrows: int, opp_helmets: int, opp_shields: int,
        unblockable: int,
    ) -> tuple[int, int, int, int]:
        """Calculate dice combat damage and successful blocks.

        Returns (damage, effective_blocks, blocked_axes, blocked_arrows).
        Bypasses are distributed from axes first.
        """
        if unblockable >= axes + arrows:
            return axes + arrows, 0, 0, 0
        raw_blocked_axes   = min(axes, opp_helmets)
        raw_blocked_arrows = min(arrows, opp_shields)
        bypassed_axes   = min(unblockable, raw_blocked_axes)
        bypassed_arrows = min(unblockable - bypassed_axes, raw_blocked_arrows)
        eff_blocked_axes   = raw_blocked_axes - bypassed_axes
        eff_blocked_arrows = raw_blocked_arrows - bypassed_arrows
        effective_blocks   = eff_blocked_axes + eff_blocked_arrows
        bypassed           = bypassed_axes + bypassed_arrows
        normal_dmg         = axes + arrows - (raw_blocked_axes + raw_blocked_arrows)
        return normal_dmg + bypassed, effective_blocks, eff_blocked_axes, eff_blocked_arrows

    def _phase_god_resolve(self, state: GameState) -> tuple[GameState, list[GameEvent]]:
        """
        Full L2 God Power resolution.

        Resolution order:
          1. Frigg's Veil - cancel opponent's GP
          2. Aegis of Baldr / Tyr's Judgment - set up damage shields
          3. Vidar's Reflection - set up reflect
          4. Offensive GPs - Mjolnir, Fenrir, Skadi, Surtr, Loki, Tyr (damage)
             - Damage reduced by Aegis shields, reflected by Vidar
          5. Healing - Eir's Mercy, Freyja (heal), Hel's Purge (cleanse + heal)
          6. Tokens - Freyja (token gain), Odin (token gain), Hel's Purge T3 (tokens)
          7. Njordr's Tide - post-combat reroll (affects token phase)
          8. Heimdallr - already resolved in _phase_combat
          9. Bragi's Song - deferred (no archetype uses it)
        """
        p1 = state.p1
        p2 = state.p2

        if p1.gp_choice is None and p2.gp_choice is None:
            return replace(state, phase=GamePhase.TOKENS, p1=replace(p1, gp_choice=None), p2=replace(p2, gp_choice=None)), []

        events: list[GameEvent] = []

        def _get_gp_tier(player: PlayerState):
            if player.gp_choice is None:
                return None, None, None
            gp_id, tier_idx = player.gp_choice
            gp = self._god_powers.get(gp_id)
            if gp is None:
                return gp_id, tier_idx, None
            return gp_id, tier_idx, gp.tiers[tier_idx]

        p1_gp_id, p1_tier_idx, p1_tier = _get_gp_tier(p1)
        p2_gp_id, p2_tier_idx, p2_tier = _get_gp_tier(p2)

        # --- 1. Frigg's Veil: cancel opponent's GP ---
        p1_cancelled = False
        p2_cancelled = False
        p1_tokens = p1.tokens
        p2_tokens = p2.tokens

        if p1_gp_id == "GP_FRIGGS_VEIL" and p1_tier is not None and p2.gp_choice is not None:
            p2_cancelled = True
            if p1_tier.steal_tokens and p2_tier is not None:
                p1_tokens += p2_tier.cost
            elif p2_tier is not None:
                p2_tokens += int(p2_tier.cost * p1_tier.refund_pct)
            events.append(GameEvent("gp_cancel", {"player": 1, "cancelled_player": 2, "steal": p1_tier.steal_tokens}))

        if p2_gp_id == "GP_FRIGGS_VEIL" and p2_tier is not None and p1.gp_choice is not None and not p1_cancelled:
            p1_cancelled = True
            if p2_tier.steal_tokens and p1_tier is not None:
                p2_tokens += p1_tier.cost
            elif p1_tier is not None:
                p1_tokens += int(p1_tier.cost * p2_tier.refund_pct)
            events.append(GameEvent("gp_cancel", {"player": 2, "cancelled_player": 1, "steal": p2_tier.steal_tokens}))

        if p1_gp_id == "GP_FRIGGS_VEIL":
            p1_cancelled = True  # Frigg itself doesn't do offense/defense after cancel

        if p2_gp_id == "GP_FRIGGS_VEIL":
            p2_cancelled = True

        # --- 2. Defensive shields (Aegis, Tyr) ---
        p1_shield = 0
        p2_shield = 0
        if not p1_cancelled and p1_tier is not None:
            p1_shield = p1_tier.block_amount
        if not p2_cancelled and p2_tier is not None:
            p2_shield = p2_tier.block_amount

        # --- 3. Vidar's Reflection ---
        p1_reflect_pct = 0.0
        p1_reflect_bonus = 0
        p2_reflect_pct = 0.0
        p2_reflect_bonus = 0
        if not p1_cancelled and p1_gp_id == "GP_VIDARS_REFLECTION" and p1_tier is not None:
            p1_reflect_pct = p1_tier.reflect_pct
            p1_reflect_bonus = p1_tier.reflect_bonus
        if not p2_cancelled and p2_gp_id == "GP_VIDARS_REFLECTION" and p2_tier is not None:
            p2_reflect_pct = p2_tier.reflect_pct
            p2_reflect_bonus = p2_tier.reflect_bonus

        # --- 4. Offensive GPs ---
        raw_dmg_to_p2 = 0
        raw_dmg_to_p1 = 0
        self_dmg_to_p1 = 0
        self_dmg_to_p2 = 0
        p1_bleed_add = 0
        p2_bleed_add = 0

        if not p1_cancelled and p1_tier is not None:
            d, sd, bleed = self._calc_offensive_gp(p1, p2, p1_gp_id, p1_tier)
            raw_dmg_to_p2 += d
            self_dmg_to_p1 += sd
            p2_bleed_add += bleed
            if d > 0 or sd > 0 or bleed > 0:
                events.append(GameEvent("gp_resolved", {"player": 1, "gp_id": p1_gp_id, "tier": p1_tier_idx, "dmg_to_opponent": d, "self_damage": sd, "bleed": bleed}))

        if not p2_cancelled and p2_tier is not None:
            d, sd, bleed = self._calc_offensive_gp(p2, p1, p2_gp_id, p2_tier)
            raw_dmg_to_p1 += d
            self_dmg_to_p2 += sd
            p1_bleed_add += bleed
            if d > 0 or sd > 0 or bleed > 0:
                events.append(GameEvent("gp_resolved", {"player": 2, "gp_id": p2_gp_id, "tier": p2_tier_idx, "dmg_to_opponent": d, "self_damage": sd, "bleed": bleed}))

        # Apply shields: reduce incoming GP damage.
        shielded_dmg_to_p1 = max(0, raw_dmg_to_p1 - p1_shield)
        shielded_dmg_to_p2 = max(0, raw_dmg_to_p2 - p2_shield)

        # Apply reflect: damage reflected back to attacker.
        reflect_dmg_to_p2 = 0
        reflect_dmg_to_p1 = 0
        if p1_reflect_pct > 0 and raw_dmg_to_p1 > 0:
            reflect_dmg_to_p2 = int(raw_dmg_to_p1 * p1_reflect_pct) + p1_reflect_bonus
            events.append(GameEvent("gp_reflect", {"player": 1, "reflected": reflect_dmg_to_p2}))
        if p2_reflect_pct > 0 and raw_dmg_to_p2 > 0:
            reflect_dmg_to_p1 = int(raw_dmg_to_p2 * p2_reflect_pct) + p2_reflect_bonus
            events.append(GameEvent("gp_reflect", {"player": 2, "reflected": reflect_dmg_to_p1}))

        final_dmg_to_p1 = shielded_dmg_to_p1 + self_dmg_to_p1 + reflect_dmg_to_p1
        final_dmg_to_p2 = shielded_dmg_to_p2 + self_dmg_to_p2 + reflect_dmg_to_p2

        # --- 5. Healing ---
        p1_heal = 0
        p2_heal = 0
        if not p1_cancelled and p1_tier is not None:
            p1_heal = p1_tier.heal
            if p1_tier.cleanse:
                p1_bleed_add = -999  # sentinel: clear all bleed
        if not p2_cancelled and p2_tier is not None:
            p2_heal = p2_tier.heal
            if p2_tier.cleanse:
                p2_bleed_add = -999

        # --- 6. Token gain ---
        if not p1_cancelled and p1_tier is not None:
            p1_tokens += p1_tier.token_gain
        if not p2_cancelled and p2_tier is not None:
            p2_tokens += p2_tier.token_gain

        # --- 7. Njordr's Tide: reroll dice for token phase ---
        new_p1_faces = p1.dice_faces
        new_p2_faces = p2.dice_faces
        if not p1_cancelled and p1_gp_id == "GP_NJORDS_TIDE" and p1_tier is not None:
            new_p1_faces = self._njordr_reroll(p1.dice_faces, p1_tier.reroll_count, self.p1_die_types)
            events.append(GameEvent("njordr_reroll", {"player": 1, "count": p1_tier.reroll_count}))
        if not p2_cancelled and p2_gp_id == "GP_NJORDS_TIDE" and p2_tier is not None:
            new_p2_faces = self._njordr_reroll(p2.dice_faces, p2_tier.reroll_count, self.p2_die_types)
            events.append(GameEvent("njordr_reroll", {"player": 2, "count": p2_tier.reroll_count}))

        # --- Apply all changes ---
        p1_new_hp = max(0, p1.hp - final_dmg_to_p1 + p1_heal)
        p2_new_hp = max(0, p2.hp - final_dmg_to_p2 + p2_heal)
        # Cap HP at STARTING_HP (no overhealing).
        p1_new_hp = min(p1_new_hp, STARTING_HP)
        p2_new_hp = min(p2_new_hp, STARTING_HP)

        p1_new_bleed = p1.bleed_stacks + p1_bleed_add if p1_bleed_add != -999 else 0
        p2_new_bleed = p2.bleed_stacks + p2_bleed_add if p2_bleed_add != -999 else 0

        new_state = replace(
            state,
            phase=GamePhase.TOKENS,
            p1=replace(p1, hp=p1_new_hp, tokens=p1_tokens, bleed_stacks=max(0, p1_new_bleed),
                       dice_faces=new_p1_faces, gp_choice=None),
            p2=replace(p2, hp=p2_new_hp, tokens=p2_tokens, bleed_stacks=max(0, p2_new_bleed),
                       dice_faces=new_p2_faces, gp_choice=None),
        )
        return new_state, events

    def _calc_offensive_gp(self, attacker, defender, gp_id, tier) -> tuple[int, int, int]:
        """Return (damage, self_damage, bleed_stacks) for an offensive GP."""
        if gp_id == "GP_MJOLNIRS_WRATH":
            return int(tier.damage), 0, 0
        if gp_id == "GP_SURTRS_FLAME":
            return int(tier.damage), tier.self_damage, 0
        if gp_id == "GP_LOKIS_GAMBIT":
            dmg = int(self.rng.integers(tier.dmg_min, tier.dmg_max + 1))
            return dmg, 0, 0
        if gp_id == "GP_SKADIS_VOLLEY":
            attacker_arrows = attacker.dice_faces.count("FACE_ARROW")
            defender_shields = defender.dice_faces.count("FACE_SHIELD")
            unblocked = max(0, attacker_arrows - defender_shields)
            return unblocked * tier.arrow_bonus, 0, 0
        if gp_id == "GP_FENRIRS_BITE":
            return int(tier.damage), 0, tier.bleed_stacks
        if gp_id == "GP_TYRS_JUDGMENT":
            return int(tier.damage), 0, 0
        return 0, 0, 0

    def _njordr_reroll(self, faces: tuple[str, ...], count: int, die_types: list[DieType]) -> tuple[str, ...]:
        """Reroll up to `count` random dice (for Njordr's Tide post-combat reroll)."""
        if count >= NUM_DICE:
            return _roll_all(die_types, self.rng)
        indices = self.rng.choice(NUM_DICE, size=min(count, NUM_DICE), replace=False)
        new_faces = list(faces)
        for i in indices:
            new_faces[i] = _roll_die(die_types[i], self.rng)
        return tuple(new_faces)

    def _phase_tokens(self, state: GameState) -> tuple[GameState, list[GameEvent]]:
        """
        Resolution order steps 7-8:
          7. Bordered Hands generate 1 token each (both players simultaneously).
          8. Bordered Hands + Tithing Hands each steal 1 token from opponent
             (amounts capped at opponent's post-generation total, resolved simultaneously).
        """
        p1 = state.p1
        p2 = state.p2

        p1_bordered = p1.dice_faces.count("FACE_HAND_BORDERED")
        p2_bordered = p2.dice_faces.count("FACE_HAND_BORDERED")
        p1_plain    = p1.dice_faces.count("FACE_HAND")
        p2_plain    = p2.dice_faces.count("FACE_HAND")

        # Step 7: simultaneous generation.
        p1_after_gen = p1.tokens + p1_bordered
        p2_after_gen = p2.tokens + p2_bordered

        # Step 8: simultaneous theft (capped at what the opponent had post-generation).
        p1_steal = min(p1_bordered + p1_plain, p2_after_gen)
        p2_steal = min(p2_bordered + p2_plain, p1_after_gen)

        # Plain Hand no-steal bonus: COMMENTED OUT for isolated token-threshold test.
        # p1_bordered_steal = min(p1_bordered, p2_after_gen)
        # p2_bordered_steal = min(p2_bordered, p1_after_gen)
        # p1_plain_steal = min(p1_plain, p2_after_gen - p1_bordered_steal)
        # p2_plain_steal = min(p2_plain, p1_after_gen - p2_bordered_steal)
        # p1_plain_bonus = p1_plain - p1_plain_steal
        # p2_plain_bonus = p2_plain - p2_plain_steal
        # p1_steal = p1_bordered_steal + p1_plain_steal
        # p2_steal = p2_bordered_steal + p2_plain_steal

        p1_final = max(0, p1_after_gen + p1_steal - p2_steal)
        p2_final = max(0, p2_after_gen + p2_steal - p1_steal)

        new_state = replace(
            state,
            phase=GamePhase.END_CHECK,
            p1=replace(p1, tokens=p1_final),
            p2=replace(p2, tokens=p2_final),
        )
        return new_state, [
            GameEvent("tokens", {
                "p1_generated": p1_bordered, "p2_generated": p2_bordered,
                "p1_stole": p1_steal,        "p2_stole": p2_steal,
                "p1_final": p1_final,        "p2_final": p2_final,
            })
        ]

    def _phase_end_check(self, state: GameState) -> tuple[GameState, list[GameEvent]]:
        """
        Win condition: player(s) at or below 0 HP lose.
        Both dropping simultaneously -> draw (winner = 0).
        """
        p1_dead = state.p1.hp <= 0
        p2_dead = state.p2.hp <= 0

        if p1_dead and p2_dead:
            winner: int | None = 0
        elif p1_dead:
            winner = 2
        elif p2_dead:
            winner = 1
        else:
            winner = None

        if winner is not None:
            return replace(state, phase=GamePhase.GAME_OVER, winner=winner), [
                GameEvent("game_over", {
                    "winner": winner,
                    "round": state.round_num,
                    "p1_hp": state.p1.hp,
                    "p2_hp": state.p2.hp,
                })
            ]

        # No winner yet - start next round.
        new_state = replace(
            state,
            round_num=state.round_num + 1,
            phase=GamePhase.REVEAL,
            p1=replace(state.p1, dice_faces=_BLANK_FACES, dice_kept=_ALL_FREE, gp_choice=None),
            p2=replace(state.p2, dice_faces=_BLANK_FACES, dice_kept=_ALL_FREE, gp_choice=None),
        )
        return new_state, [GameEvent("round_end", {"round": state.round_num})]
