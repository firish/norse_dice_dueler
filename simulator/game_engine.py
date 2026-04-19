"""
game_engine.py
--------------
Pure game logic. Holds only an RNG as mutable state; everything else is
derived from the immutable GameState passed in.

Pattern:
    state, events = engine.step(state, p1_action, p2_action)

Agents only need to supply actions for KEEP_1, KEEP_2, and GOD_POWER phases.
All other phases advance automatically (no agent input required).

L2 three-archetype scope:
    - 9 God Powers (Surtr, Fenrir, Aegis, Eir, Bragi, Gullveig, Tyr, Frigg, Mjolnir).
    - T1 tiers only.
    - Combat thorns enabled: every 3 blocked damage reflects 1.
    - Bordered hands bank tokens before GP choice; plain hands still steal at round end.
    - Bragi can prevent some dice damage and reflect part of it back.
    - Optional single Battlefield Condition support for L4 harnessing.
    - No Runes (L5).
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
# Internal die-rolling helpers
# ---------------------------------------------------------------------------

def _roll_die(die: DieType, rng: np.random.Generator) -> str:
    return die.faces[rng.integers(0, NUM_DICE)]


def _roll_all(die_types: list[DieType], rng: np.random.Generator) -> tuple[str, ...]:
    return tuple(_roll_die(d, rng) for d in die_types)


def _reroll_unkept(
    faces: tuple[str, ...],
    kept: tuple[bool, ...],
    die_types: list[DieType],
    rng: np.random.Generator,
) -> tuple[str, ...]:
    new = list(faces)
    for i, (k, die) in enumerate(zip(kept, die_types)):
        if not k:
            new[i] = _roll_die(die, rng)
    return tuple(new)


def _apply_keep(
    prev_kept: tuple[bool, ...],
    new_indices: frozenset[int],
) -> tuple[bool, ...]:
    return tuple(prev_kept[i] or (i in new_indices) for i in range(NUM_DICE))


# ---------------------------------------------------------------------------
# GameEngine
# ---------------------------------------------------------------------------

class GameEngine:
    """
    Stateless game-rule machine (except for the RNG).
    """

    def __init__(
        self,
        p1_die_types: list[DieType],
        p2_die_types: list[DieType],
        rng: np.random.Generator | None = None,
        p1_gp_ids: tuple[str, ...] = (),
        p2_gp_ids: tuple[str, ...] = (),
        god_powers: dict[str, GodPower] | None = None,
        condition_id: str | None = None,
    ) -> None:
        assert len(p1_die_types) == NUM_DICE, f"P1 loadout must have {NUM_DICE} dice"
        assert len(p2_die_types) == NUM_DICE, f"P2 loadout must have {NUM_DICE} dice"
        self.p1_die_types = p1_die_types
        self.p2_die_types = p2_die_types
        self.rng = rng or np.random.default_rng()
        self.p1_gp_ids = p1_gp_ids
        self.p2_gp_ids = p2_gp_ids
        self.condition_id = condition_id
        if god_powers is not None:
            self._god_powers = god_powers
        elif p1_gp_ids or p2_gp_ids:
            self._god_powers = load_god_powers()
        else:
            self._god_powers: dict = {}

        self._starting_hp = STARTING_HP + 2 if self.condition_id == "COND_YGGDRASIL_ROOTS" else STARTING_HP

    def _has_condition(self, condition_id: str) -> bool:
        return self.condition_id == condition_id

    def _gp_cost(self, base_cost: int, round_num: int) -> int:
        if self._has_condition("COND_JOTUN_MIGHT") and base_cost >= 7:
            return max(1, base_cost - 1)
        return base_cost

    def _choice_cost(self, choice: tuple[str, int] | None) -> int:
        if choice is None:
            return 0
        gp_id, tier_idx = choice
        gp = self._god_powers.get(gp_id)
        if gp is None:
            return 0
        return self._gp_cost(gp.tiers[tier_idx].cost)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def new_game(self) -> GameState:
        return GameState(
            round_num=1,
            phase=GamePhase.REVEAL,
            p1=PlayerState(
                hp=self._starting_hp,
                tokens=STARTING_TOKENS,
                dice_faces=_BLANK_FACES,
                dice_kept=_ALL_FREE,
                gp_loadout=self.p1_gp_ids,
            ),
            p2=PlayerState(
                hp=self._starting_hp,
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
        all_events: list[GameEvent] = []

        def tick(p1_act=None, p2_act=None):
            nonlocal state
            state, evts = self.step(state, p1_act, p2_act)
            all_events.extend(evts)

        tick()
        tick()
        tick(p1_agent.choose_keep(state, 1), p2_agent.choose_keep(state, 2))
        tick()
        tick(p1_agent.choose_keep(state, 1), p2_agent.choose_keep(state, 2))
        tick()
        tick(p1_agent.choose_god_power(state, 1), p2_agent.choose_god_power(state, 2))
        tick()
        tick()
        tick()
        tick()

        return state, all_events

    def run_game(
        self,
        p1_agent: "Agent",
        p2_agent: "Agent",
        max_rounds: int = 100,
    ) -> tuple[GameState, list[GameEvent]]:
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
    # Phase implementations
    # ------------------------------------------------------------------

    def _phase_reveal(self, state: GameState) -> tuple[GameState, list[GameEvent]]:
        if self.condition_id is None:
            return replace(state, phase=GamePhase.ROLL), []
        return replace(state, phase=GamePhase.ROLL), [
            GameEvent("condition_active", {"condition_id": self.condition_id, "round": state.round_num})
        ]

    def _phase_roll(self, state: GameState) -> tuple[GameState, list[GameEvent]]:
        p1_faces = _roll_all(self.p1_die_types, self.rng)
        p2_faces = _roll_all(self.p2_die_types, self.rng)
        p1_kept = _ALL_FREE
        p2_kept = _ALL_FREE

        if self._has_condition("COND_LOKI_MISCHIEF") and state.round_num <= 3:
            p1_lock = int(self.rng.integers(0, NUM_DICE))
            p2_lock = int(self.rng.integers(0, NUM_DICE))
            p1_kept = tuple(i == p1_lock for i in range(NUM_DICE))
            p2_kept = tuple(i == p2_lock for i in range(NUM_DICE))

        new_state = replace(
            state,
            phase=GamePhase.KEEP_1,
            p1=replace(state.p1, dice_faces=p1_faces, dice_kept=p1_kept),
            p2=replace(state.p2, dice_faces=p2_faces, dice_kept=p2_kept),
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
        p1_kept = state.p1.dice_kept
        p2_kept = state.p2.dice_kept
        p1_tokens = state.p1.tokens
        p2_tokens = state.p2.tokens
        events: list[GameEvent] = []

        if self._has_condition("COND_ODIN_GAZE") and next_phase == GamePhase.GOD_POWER and state.round_num <= 3:
            p1_kept = (True,) * NUM_DICE
            p2_kept = (True,) * NUM_DICE

        p1_faces = _reroll_unkept(
            state.p1.dice_faces, p1_kept, self.p1_die_types, self.rng
        )
        p2_faces = _reroll_unkept(
            state.p2.dice_faces, p2_kept, self.p2_die_types, self.rng
        )
        new_state = replace(
            state,
            phase=next_phase,
            p1=replace(state.p1, dice_faces=p1_faces, dice_kept=p1_kept, tokens=p1_tokens),
            p2=replace(state.p2, dice_faces=p2_faces, dice_kept=p2_kept, tokens=p2_tokens),
        )
        return new_state, events

    def _phase_god_power(
        self,
        state: GameState,
        p1_action: tuple[str, int] | None,
        p2_action: tuple[str, int] | None,
    ) -> tuple[GameState, list[GameEvent]]:
        """Bank bordered hands, then validate GP choices and deduct costs."""
        p1_bordered = state.p1.dice_faces.count("FACE_HAND_BORDERED")
        p2_bordered = state.p2.dice_faces.count("FACE_HAND_BORDERED")
        p1_banked = p1_bordered
        p2_banked = p2_bordered
        if self._has_condition("COND_FREYA_BLESSING"):
            if state.round_num >= 5:
                p1_banked += 1 if p1_bordered >= 2 else 0
                p2_banked += 1 if p2_bordered >= 2 else 0
        p1 = replace(state.p1, tokens=state.p1.tokens + p1_banked)
        p2 = replace(state.p2, tokens=state.p2.tokens + p2_banked)
        events: list[GameEvent] = []

        if p1_banked or p2_banked:
            events.append(GameEvent("early_bank", {
                "p1_banked": p1_banked,
                "p2_banked": p2_banked,
                "p1_tokens": p1.tokens,
                "p2_tokens": p2.tokens,
            }))

        def _validate(
            player: PlayerState,
            action: tuple[str, int] | None,
            player_num: int,
        ) -> PlayerState:
            if action is None:
                return player
            gp_id, tier_idx = action
            if self._has_condition("COND_TYR_ARENA") and tier_idx >= 1:
                return player
            if gp_id not in player.gp_loadout:
                return player
            if tier_idx not in (0, 1, 2):
                return player
            gp = self._god_powers.get(gp_id)
            if gp is None:
                return player
            tier = gp.tiers[tier_idx]
            effective_cost = self._gp_cost(tier.cost, state.round_num)
            if player.tokens < effective_cost:
                return player
            events.append(GameEvent("gp_chosen", {
                "player": player_num, "gp_id": gp_id,
                "tier": tier_idx, "cost": effective_cost,
            }))
            return replace(
                player,
                tokens=player.tokens - effective_cost,
                gp_choice=(gp_id, tier_idx),
            )

        p1 = _validate(p1, p1_action, 1)
        p2 = _validate(p2, p2_action, 2)

        return replace(state, phase=GamePhase.COMBAT, p1=p1, p2=p2), events

    def _phase_combat(self, state: GameState) -> tuple[GameState, list[GameEvent]]:
        """Simultaneous attack resolution. Axes vs helmets, arrows vs shields.

        Thorns: every 3 damage a player blocks deals 1 back to the attacker.
        Encourages defensive builds to have an intrinsic damage path.
        """
        p1 = state.p1
        p2 = state.p2

        p1_axes    = p1.dice_faces.count("FACE_AXE")
        p1_arrows  = p1.dice_faces.count("FACE_ARROW")
        p2_axes    = p2.dice_faces.count("FACE_AXE")
        p2_arrows  = p2.dice_faces.count("FACE_ARROW")
        p1_helmets = p1.dice_faces.count("FACE_HELMET")
        p1_shields = p1.dice_faces.count("FACE_SHIELD")
        p2_helmets = p2.dice_faces.count("FACE_HELMET")
        p2_shields = p2.dice_faces.count("FACE_SHIELD")

        p1_blocks = min(p2_axes, p1_helmets) + min(p2_arrows, p1_shields)
        p2_blocks = min(p1_axes, p2_helmets) + min(p1_arrows, p2_shields)
        p1_thorns = p1_blocks // 3   # damage P1 sends back to P2 from blocking
        p2_thorns = p2_blocks // 3

        dmg_to_p2 = (p1_axes + p1_arrows) - p2_blocks + p1_thorns
        dmg_to_p1 = (p2_axes + p2_arrows) - p1_blocks + p2_thorns

        if self._has_condition("COND_FENRIR_HUNT") and state.round_num >= 4:
            if (p1_axes + p1_arrows) > 0 and (p1_axes + p1_arrows) - p2_blocks == 0:
                dmg_to_p2 += 1
            if (p2_axes + p2_arrows) > 0 and (p2_axes + p2_arrows) - p1_blocks == 0:
                dmg_to_p1 += 1

        p1_bragi_reflect = 0
        p2_bragi_reflect = 0
        if p1.gp_choice is not None and p1.gp_choice[0] == "GP_BRAGIS_SONG":
            p1_tier = self._god_powers["GP_BRAGIS_SONG"].tiers[p1.gp_choice[1]]
            prevented = min(p1_tier.damage_reduction, max(0, dmg_to_p1))
            dmg_to_p1 -= prevented
            p1_bragi_reflect = int(round(prevented * p1_tier.reflect_pct))
        if p2.gp_choice is not None and p2.gp_choice[0] == "GP_BRAGIS_SONG":
            p2_tier = self._god_powers["GP_BRAGIS_SONG"].tiers[p2.gp_choice[1]]
            prevented = min(p2_tier.damage_reduction, max(0, dmg_to_p2))
            dmg_to_p2 -= prevented
            p2_bragi_reflect = int(round(prevented * p2_tier.reflect_pct))

        dmg_to_p1 += p2_bragi_reflect
        dmg_to_p2 += p1_bragi_reflect

        p1_tokens = p1.tokens
        p2_tokens = p2.tokens
        if self._has_condition("COND_NIFLHEIM_CHILL"):
            p1_tokens += 1 if p1_blocks >= 3 else 0
            p2_tokens += 1 if p2_blocks >= 3 else 0

        new_state = replace(
            state,
            phase=GamePhase.GOD_RESOLVE,
            p1=replace(p1, hp=p1.hp - dmg_to_p1, tokens=p1_tokens),
            p2=replace(p2, hp=p2.hp - dmg_to_p2, tokens=p2_tokens),
        )
        return new_state, [
            GameEvent("combat", {
                "dmg_to_p1": dmg_to_p1, "dmg_to_p2": dmg_to_p2,
                "p1_thorns": p1_thorns, "p2_thorns": p2_thorns,
                "p1_bragi_reflect": p1_bragi_reflect,
                "p2_bragi_reflect": p2_bragi_reflect,
                "p1_blocks": p1_blocks, "p2_blocks": p2_blocks,
            })
        ]

    def _phase_god_resolve(self, state: GameState) -> tuple[GameState, list[GameEvent]]:
        """
        GP resolution order:
          1. Frigg's Veil cancel
          2. Defensive shields from Aegis / Tyr
          3. Offensive GPs (Surtr, Fenrir, Tyr damage, Mjolnir)
          4. Healing (Eir)
          5. Token gain (Gullveig)
        """
        p1 = state.p1
        p2 = state.p2

        if p1.gp_choice is None and p2.gp_choice is None:
            return replace(
                state, phase=GamePhase.TOKENS,
                p1=replace(p1, gp_choice=None),
                p2=replace(p2, gp_choice=None),
            ), []

        events: list[GameEvent] = []

        def _tier(player: PlayerState):
            if player.gp_choice is None:
                return None, None
            gp_id, tier_idx = player.gp_choice
            gp = self._god_powers.get(gp_id)
            return gp_id, (gp.tiers[tier_idx] if gp is not None else None)

        p1_gp_id, p1_tier = _tier(p1)
        p2_gp_id, p2_tier = _tier(p2)

        # --- 1. Frigg's Veil: cancel opponent's GP ---
        p1_cancelled = False
        p2_cancelled = False
        p1_tokens = p1.tokens
        p2_tokens = p2.tokens

        if p1_gp_id == "GP_FRIGGS_VEIL" and p1_tier is not None:
            if p2.gp_choice is not None and p2_tier is not None:
                p2_cancelled = True
                if p1_tier.steal_tokens:
                    p1_tokens += self._choice_cost(p2.gp_choice)
                else:
                    p2_tokens += int(self._choice_cost(p2.gp_choice) * p1_tier.refund_pct)
                events.append(GameEvent("gp_cancel", {"player": 1}))
            p1_cancelled = True  # Frigg has no offense/defense payload

        if p2_gp_id == "GP_FRIGGS_VEIL" and p2_tier is not None and not p1_cancelled:
            if p1.gp_choice is not None and p1_tier is not None:
                p1_cancelled = True
                if p2_tier.steal_tokens:
                    p2_tokens += self._choice_cost(p1.gp_choice)
                else:
                    p1_tokens += int(self._choice_cost(p1.gp_choice) * p2_tier.refund_pct)
                events.append(GameEvent("gp_cancel", {"player": 2}))
            p2_cancelled = True

        # --- 2. Defensive shields from Aegis / Tyr ---
        p1_shield = p1_tier.block_amount if (not p1_cancelled and p1_tier is not None) else 0
        p2_shield = p2_tier.block_amount if (not p2_cancelled and p2_tier is not None) else 0

        # --- 3. Offensive GPs ---
        raw_dmg_to_p2 = 0
        raw_dmg_to_p1 = 0
        self_dmg_to_p1 = 0
        self_dmg_to_p2 = 0

        if not p1_cancelled and p1_tier is not None:
            d, sd = self._offensive_damage(p1_gp_id, p1_tier)
            raw_dmg_to_p2 += d
            self_dmg_to_p1 += sd

        if not p2_cancelled and p2_tier is not None:
            d, sd = self._offensive_damage(p2_gp_id, p2_tier)
            raw_dmg_to_p1 += d
            self_dmg_to_p2 += sd

        final_dmg_to_p1 = max(0, raw_dmg_to_p1 - p1_shield) + self_dmg_to_p1
        final_dmg_to_p2 = max(0, raw_dmg_to_p2 - p2_shield) + self_dmg_to_p2

        # --- 4. Healing ---
        p1_heal = p1_tier.heal if (not p1_cancelled and p1_tier is not None) else 0
        p2_heal = p2_tier.heal if (not p2_cancelled and p2_tier is not None) else 0
        if self._has_condition("COND_MIDGARD_HEARTH"):
            p1_heal += 1 if p1_heal > 0 else 0
            p2_heal += 1 if p2_heal > 0 else 0

        # --- 5. Token gain ---
        if not p1_cancelled and p1_tier is not None:
            p1_tokens += p1_tier.token_gain
        if not p2_cancelled and p2_tier is not None:
            p2_tokens += p2_tier.token_gain

        p1_new_hp = min(self._starting_hp, max(0, p1.hp - final_dmg_to_p1 + p1_heal))
        p2_new_hp = min(self._starting_hp, max(0, p2.hp - final_dmg_to_p2 + p2_heal))

        new_state = replace(
            state,
            phase=GamePhase.TOKENS,
            p1=replace(p1, hp=p1_new_hp, tokens=p1_tokens, gp_choice=None),
            p2=replace(p2, hp=p2_new_hp, tokens=p2_tokens, gp_choice=None),
        )
        return new_state, events

    @staticmethod
    def _offensive_damage(gp_id: str, tier) -> tuple[int, int]:
        """Return (damage_to_opponent, self_damage) for an offensive GP."""
        if gp_id == "GP_MJOLNIRS_WRATH":
            return int(tier.damage), 0
        if gp_id == "GP_SURTRS_FLAME":
            return int(tier.damage), tier.self_damage
        if gp_id == "GP_FENRIRS_BITE":
            return int(tier.damage), 0
        if gp_id == "GP_TYRS_JUDGMENT":
            return int(tier.damage), 0
        return 0, 0

    def _phase_tokens(self, state: GameState) -> tuple[GameState, list[GameEvent]]:
        """
        End-of-round token phase only handles plain-hand stealing.
        Bordered hands already banked tokens before GP choice.
        """
        p1 = state.p1
        p2 = state.p2

        p1_plain = p1.dice_faces.count("FACE_HAND")
        p2_plain = p2.dice_faces.count("FACE_HAND")

        p1_steal = min(p1_plain, p2.tokens)
        p2_steal = min(p2_plain, p1.tokens)

        p1_final = max(0, p1.tokens + p1_steal - p2_steal)
        p2_final = max(0, p2.tokens + p2_steal - p1_steal)

        new_state = replace(
            state,
            phase=GamePhase.END_CHECK,
            p1=replace(p1, tokens=p1_final),
            p2=replace(p2, tokens=p2_final),
        )
        return new_state, [
            GameEvent("tokens", {
                "p1_generated": 0, "p2_generated": 0,
                "p1_stole": p1_steal, "p2_stole": p2_steal,
                "p1_final": p1_final, "p2_final": p2_final,
            })
        ]

    def _phase_end_check(self, state: GameState) -> tuple[GameState, list[GameEvent]]:
        p1 = state.p1
        p2 = state.p2
        events: list[GameEvent] = []

        if self._has_condition("COND_RAGNAROK") and state.round_num >= 5:
            p1 = replace(p1, hp=max(0, p1.hp - 1))
            p2 = replace(p2, hp=max(0, p2.hp - 1))
            events.append(GameEvent("condition_tick", {
                "condition_id": self.condition_id,
                "round": state.round_num,
                "p1_hp": p1.hp,
                "p2_hp": p2.hp,
            }))

        p1_dead = p1.hp <= 0
        p2_dead = p2.hp <= 0

        if p1_dead and p2_dead:
            winner: int | None = 0
        elif p1_dead:
            winner = 2
        elif p2_dead:
            winner = 1
        else:
            winner = None

        if winner is not None:
            events.append(GameEvent("game_over", {
                    "winner": winner, "round": state.round_num,
                    "p1_hp": p1.hp, "p2_hp": p2.hp,
                }))
            return replace(state, phase=GamePhase.GAME_OVER, winner=winner, p1=p1, p2=p2), events

        new_state = replace(
            state,
            round_num=state.round_num + 1,
            phase=GamePhase.REVEAL,
            p1=replace(
                p1,
                dice_faces=_BLANK_FACES,
                dice_kept=_ALL_FREE,
                gp_choice=None,
            ),
            p2=replace(
                p2,
                dice_faces=_BLANK_FACES,
                dice_kept=_ALL_FREE,
                gp_choice=None,
            ),
        )
        events.append(GameEvent("round_end", {"round": state.round_num}))
        return new_state, events
