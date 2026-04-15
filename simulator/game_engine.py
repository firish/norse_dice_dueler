"""
game_engine.py
--------------
Pure game logic. Holds only an RNG as mutable state; everything else is
derived from the immutable GameState passed in.

Pattern:
    state, events = engine.step(state, p1_action, p2_action)

Agents only need to supply actions for KEEP_1, KEEP_2, and GOD_POWER phases.
All other phases advance automatically (no agent input required).

L0 scope:
    - No God Powers (GOD_POWER and GOD_RESOLVE are no-ops).
    - No Battlefield Conditions (REVEAL is a no-op).
    - No Runes, no status effects (Bleed / Poison).
    - Full dice rolling, keep/reroll cycle, combat, and token resolution.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import numpy as np

from simulator.game_state import GameEvent, GamePhase, GameState, PlayerState
from simulator.die_types import DieType

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
    """Merge a keep-action into the existing kept mask. Kept dice cannot be un-kept."""
    return tuple(prev_kept[i] or (i in new_indices) for i in range(NUM_DICE))


# ---------------------------------------------------------------------------
# GameEngine
# ---------------------------------------------------------------------------

class GameEngine:
    """
    Stateless game-rule machine (except for the RNG).

    Args:
        p1_die_types: Ordered list of 6 DieType objects for player 1's loadout.
        p2_die_types: Ordered list of 6 DieType objects for player 2's loadout.
        rng:          numpy Generator. Pass a seeded rng for reproducibility.
    """

    def __init__(
        self,
        p1_die_types: list[DieType],
        p2_die_types: list[DieType],
        rng: np.random.Generator | None = None,
    ) -> None:
        assert len(p1_die_types) == NUM_DICE, f"P1 loadout must have {NUM_DICE} dice"
        assert len(p2_die_types) == NUM_DICE, f"P2 loadout must have {NUM_DICE} dice"
        self.p1_die_types = p1_die_types
        self.p2_die_types = p2_die_types
        self.rng = rng or np.random.default_rng()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def new_game(self) -> GameState:
        """Return the initial GameState at the start of round 1."""
        blank = PlayerState(
            hp=STARTING_HP,
            tokens=STARTING_TOKENS,
            dice_faces=_BLANK_FACES,
            dice_kept=_ALL_FREE,
        )
        return GameState(
            round_num=1,
            phase=GamePhase.REVEAL,
            p1=blank,
            p2=blank,
            winner=None,
        )

    def step(
        self,
        state: GameState,
        p1_action: frozenset[int] | None = None,
        p2_action: frozenset[int] | None = None,
    ) -> tuple[GameState, list[GameEvent]]:
        """
        Advance the game by one phase.

        Actions are only used by KEEP_1 and KEEP_2 phases (frozenset of die
        indices to keep). All other phases ignore the action arguments.
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
            return self._phase_god_power(state)
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

        tick()                                              # REVEAL → ROLL
        tick()                                              # ROLL   → KEEP_1
        tick(p1_agent.choose_keep(state, 1),               # KEEP_1 → REROLL_1
             p2_agent.choose_keep(state, 2))
        tick()                                              # REROLL_1 → KEEP_2
        tick(p1_agent.choose_keep(state, 1),               # KEEP_2 → REROLL_2
             p2_agent.choose_keep(state, 2))
        tick()                                              # REROLL_2 → GOD_POWER
        tick()                                              # GOD_POWER → COMBAT
        tick()                                              # COMBAT → GOD_RESOLVE
        tick()                                              # GOD_RESOLVE → TOKENS
        tick()                                              # TOKENS → END_CHECK
        tick()                                              # END_CHECK → REVEAL / GAME_OVER

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
        # L0: no battlefield conditions → immediate pass-through to ROLL.
        return replace(state, phase=GamePhase.ROLL), []

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

    def _phase_god_power(self, state: GameState) -> tuple[GameState, list[GameEvent]]:
        # L0: no God Powers → skip to COMBAT.
        return replace(state, phase=GamePhase.COMBAT), []

    def _phase_combat(self, state: GameState) -> tuple[GameState, list[GameEvent]]:
        """
        Simultaneous attack resolution (Constitution resolution order step 3).
        Axes blocked by opponent Helmets; Arrows blocked by opponent Shields.
        Both players deal damage at the same time.
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

        # Net damage: attacker's unblocked faces each deal 1 HP.
        dmg_to_p2 = max(0, p1_axes - p2_helmets) + max(0, p1_arrows - p2_shields)
        dmg_to_p1 = max(0, p2_axes - p1_helmets) + max(0, p2_arrows - p1_shields)

        new_state = replace(
            state,
            phase=GamePhase.GOD_RESOLVE,
            p1=replace(p1, hp=p1.hp - dmg_to_p1),
            p2=replace(p2, hp=p2.hp - dmg_to_p2),
        )
        return new_state, [
            GameEvent("combat", {"dmg_to_p1": dmg_to_p1, "dmg_to_p2": dmg_to_p2})
        ]

    def _phase_god_resolve(self, state: GameState) -> tuple[GameState, list[GameEvent]]:
        # L0: no God Powers → skip to TOKENS.
        return replace(state, phase=GamePhase.TOKENS), []

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
        Both dropping simultaneously → draw (winner = 0).
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

        # No winner yet — start next round.
        new_state = replace(
            state,
            round_num=state.round_num + 1,
            phase=GamePhase.REVEAL,
            p1=replace(state.p1, dice_faces=_BLANK_FACES, dice_kept=_ALL_FREE),
            p2=replace(state.p2, dice_faces=_BLANK_FACES, dice_kept=_ALL_FREE),
        )
        return new_state, [GameEvent("round_end", {"round": state.round_num})]
